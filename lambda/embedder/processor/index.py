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
from typing import Dict, Any
from urllib.parse import unquote_plus

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
        
        # URL-decode the key (S3 events URL-encode special characters)
        key = unquote_plus(key)
        
        print(f"Processing file: s3://{bucket}/{key}")
        
        # Extract metadata from S3 object
        metadata = extract_s3_metadata(bucket, key)
        print(f"Extracted metadata: {json.dumps(metadata)}")
        
        # Determine file type and create model input
        file_extension = os.path.splitext(key)[1].lower()
        model_input = create_model_input(bucket, key, file_extension)
        print(f"Created model input for type: {metadata['fileType']}")
        
        # Start async invocation
        output_s3_uri = f"s3://{OUTPUT_BUCKET}/{metadata['objectId']}"
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
            "detailLevel": "STANDARD_IMAGE"
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
