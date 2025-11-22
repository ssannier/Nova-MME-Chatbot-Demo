"""
Lambda 1: Nova MME Processor

Triggered by S3 upload via Step Functions.
- Extracts metadata from S3 object
- Formats request for Nova MME async invocation at 3072 dimensions
- Starts async job
- Returns invocation ARN and metadata for Step Functions
"""

import json
import os
import boto3
from datetime import datetime
from typing import Dict, Any, List
from urllib.parse import unquote_plus
import tempfile

# PyMuPDF import (optional for testing)
try:
    import fitz  # PyMuPDF
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("Warning: PyMuPDF not installed, PDF support disabled")

# Initialize clients
s3_client = boto3.client('s3')
bedrock_runtime = boto3.client('bedrock-runtime')

# Environment variables
EMBEDDING_DIMENSION = int(os.environ.get('EMBEDDING_DIMENSION', '3072'))
MODEL_ID = os.environ.get('MODEL_ID', 'amazon.nova-2-multimodal-embeddings-v1:0')
OUTPUT_BUCKET = os.environ['OUTPUT_BUCKET']

# File type mappings
IMAGE_FORMATS = {
    '.png': 'png', '.jpg': 'jpeg', '.jpeg': 'jpeg',
    '.gif': 'gif', '.webp': 'webp'
}
VIDEO_FORMATS = {
    '.mp4': 'mp4', '.mov': 'mov', '.mkv': 'mkv', '.webm': 'webm',
    '.flv': 'flv', '.mpeg': 'mpeg', '.mpg': 'mpg', '.wmv': 'wmv', '.3gp': '3gp'
}
AUDIO_FORMATS = {
    '.mp3': 'mp3', '.wav': 'wav', '.ogg': 'ogg'
}
TEXT_FORMATS = ['.txt', '.md', '.json', '.csv']
# PDFs are handled separately - converted to images then processed with DOCUMENT_IMAGE


def handler(event, context):
    """
    Main handler for Nova MME Processor Lambda
    
    Args:
        event: Contains 'bucket' and 'key' from Step Functions
        context: Lambda context
    
    Returns:
        Dict with invocationArn and metadata for next Lambda
    """
    try:
        # Extract S3 info from event
        bucket = event['bucket']
        key = event['key']
        
        # URL-decode the key if needed (defense in depth)
        key = unquote_plus(key)
        
        print(f"Processing file: s3://{bucket}/{key}")
        
        # Extract metadata from S3 object
        metadata = extract_s3_metadata(bucket, key)
        print(f"Extracted metadata: {json.dumps(metadata)}")
        
        # Determine file type
        file_extension = os.path.splitext(key)[1].lower()
        
        # Special handling for PDFs - convert to images first
        if file_extension == '.pdf':
            print(f"Converting PDF to images...")
            image_uris = convert_pdf_to_images(bucket, key, metadata['objectId'])
            print(f"Converted PDF to {len(image_uris)} images")
            
            # Process first page as document image
            # Note: Multi-page PDFs will need multiple invocations or batch processing
            # For now, we'll process the first page
            model_input = create_model_input(bucket, image_uris[0].replace(f"s3://{bucket}/", ""), '.png')
            model_input['segmentedEmbeddingParams']['image']['detailLevel'] = 'DOCUMENT_IMAGE'
            
            # Store PDF page info in metadata
            metadata['isPdf'] = True
            metadata['totalPages'] = len(image_uris)
            metadata['processedPage'] = 1
        else:
            # Regular file processing
            model_input = create_model_input(bucket, key, file_extension)
            print(f"Created model input for type: {metadata['fileType']}")
        
        # Start async invocation
        # Output URI must point to a directory (end with /)
        output_s3_uri = f"s3://{OUTPUT_BUCKET}/{metadata['objectId']}/"
        invocation_arn = start_async_invocation(model_input, output_s3_uri)
        print(f"Started async invocation: {invocation_arn}")
        
        # Return data for Step Functions
        return {
            'statusCode': 200,
            'invocationArn': invocation_arn,
            'outputS3Uri': output_s3_uri,
            'metadata': metadata,
            'status': 'IN_PROGRESS'
        }
        
    except Exception as e:
        print(f"Error processing file: {str(e)}")
        return {
            'statusCode': 500,
            'error': str(e),
            'status': 'FAILED'
        }


def extract_s3_metadata(bucket: str, key: str) -> Dict[str, Any]:
    """
    Extract metadata from S3 object
    
    Returns:
        Dict with sourceS3Uri, fileName, fileType, fileSize, uploadTimestamp, etc.
    """
    # Get object metadata
    response = s3_client.head_object(Bucket=bucket, Key=key)
    
    # Generate unique object ID
    object_id = key.replace('/', '_').replace('.', '_') + '_' + datetime.now().strftime('%Y%m%d%H%M%S')
    
    metadata = {
        'sourceS3Uri': f"s3://{bucket}/{key}",
        'fileName': os.path.basename(key),
        'fileType': os.path.splitext(key)[1].lower(),
        'fileSize': response['ContentLength'],
        'uploadTimestamp': response['LastModified'].isoformat(),
        'contentType': response.get('ContentType', 'unknown'),
        'objectId': object_id
    }
    
    return metadata


def create_model_input(bucket: str, key: str, file_extension: str) -> Dict[str, Any]:
    """
    Create model input JSON based on file type
    
    Returns:
        Dict with properly formatted Nova MME async request
    """
    s3_uri = f"s3://{bucket}/{key}"
    
    # Base structure
    model_input = {
        "schemaVersion": "nova-multimodal-embed-v1",
        "taskType": "SEGMENTED_EMBEDDING",
        "segmentedEmbeddingParams": {
            "embeddingPurpose": "GENERIC_INDEX",
            "embeddingDimension": EMBEDDING_DIMENSION
        }
    }
    
    # Add modality-specific configuration
    if file_extension in IMAGE_FORMATS:
        model_input["segmentedEmbeddingParams"]["image"] = {
            "format": IMAGE_FORMATS[file_extension],
            "source": {
                "s3Location": {"uri": s3_uri}
            },
            # Use DOCUMENT_IMAGE for better text/diagram interpretation
            "detailLevel": "DOCUMENT_IMAGE"
        }
    
    elif file_extension in VIDEO_FORMATS:
        model_input["segmentedEmbeddingParams"]["video"] = {
            "format": VIDEO_FORMATS[file_extension],
            "source": {
                "s3Location": {"uri": s3_uri}
            },
            "embeddingMode": "AUDIO_VIDEO_COMBINED",
            "segmentationConfig": {
                "durationSeconds": 5
            }
        }
    
    elif file_extension in AUDIO_FORMATS:
        model_input["segmentedEmbeddingParams"]["audio"] = {
            "format": AUDIO_FORMATS[file_extension],
            "source": {
                "s3Location": {"uri": s3_uri}
            },
            "segmentationConfig": {
                "durationSeconds": 5
            }
        }
    
    elif file_extension in TEXT_FORMATS:
        model_input["segmentedEmbeddingParams"]["text"] = {
            "truncationMode": "END",
            "source": {
                "s3Location": {"uri": s3_uri}
            },
            "segmentationConfig": {
                "maxLengthChars": 32000
            }
        }
    
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")
    
    return model_input


def convert_pdf_to_images(bucket: str, key: str, object_id: str) -> List[str]:
    """
    Convert PDF pages to images and upload to S3
    
    Returns:
        List of S3 URIs for the converted images
    """
    if not PDF_SUPPORT:
        raise RuntimeError("PDF support not available - PyMuPDF not installed")
    
    # Download PDF from S3
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_pdf:
        s3_client.download_fileobj(bucket, key, tmp_pdf)
        pdf_path = tmp_pdf.name
    
    try:
        # Open PDF with PyMuPDF
        pdf_document = fitz.open(pdf_path)
        image_uris = []
        
        # Convert each page to image
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            
            # Render page to image at high resolution (300 DPI for DOCUMENT_IMAGE)
            pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
            
            # Convert to PNG bytes
            img_bytes = pix.tobytes("png")
            
            # Upload to S3 in a temp location
            image_key = f"pdf-temp/{object_id}/page_{page_num + 1}.png"
            s3_client.put_object(
                Bucket=bucket,
                Key=image_key,
                Body=img_bytes,
                ContentType='image/png'
            )
            
            image_uris.append(f"s3://{bucket}/{image_key}")
            print(f"Converted PDF page {page_num + 1} to {image_key}")
        
        pdf_document.close()
        return image_uris
        
    finally:
        # Clean up temp file
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)


def start_async_invocation(model_input: Dict[str, Any], output_s3_uri: str) -> str:
    """
    Start async invocation with Bedrock
    
    Returns:
        Invocation ARN for status checking
    """
    response = bedrock_runtime.start_async_invoke(
        modelId=MODEL_ID,
        modelInput=model_input,
        outputDataConfig={
            "s3OutputDataConfig": {
                "s3Uri": output_s3_uri
            }
        }
    )
    
    return response['invocationArn']
