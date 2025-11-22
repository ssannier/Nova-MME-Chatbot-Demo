"""
Lambda 3: Store Embeddings

Processes completed async job outputs:
- Parses embedding-*.jsonl files from S3
- Truncates 3072-dim embeddings to 256, 384, 1024 dimensions (MRL)
- Stores all dimension variants in S3 Vector indexes
- Combines metadata from Lambda 1 with segment metadata from job output
"""

import json
import os
import boto3
import sys
from datetime import datetime
from typing import Dict, Any, List

# Add shared utilities to path
sys.path.insert(0, '/opt/python')  # Lambda layer path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))

try:
    from embedding_utils import create_multi_dimensional_embeddings
except ImportError:
    # Fallback for local testing
    import numpy as np
    def create_multi_dimensional_embeddings(embedding_3072, dimensions=[256, 384, 1024, 3072]):
        result = {}
        for dim in dimensions:
            if dim == 3072:
                result[dim] = embedding_3072
            else:
                truncated = np.array(embedding_3072[:dim])
                normalized = truncated / np.linalg.norm(truncated)
                result[dim] = normalized.tolist()
        return result

# Import numpy for float32 conversion (required by S3 Vectors API)
import numpy as np

# Initialize clients
s3_client = boto3.client('s3')
s3vectors_client = boto3.client('s3vectors', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Environment variables
VECTOR_BUCKET = os.environ['VECTOR_BUCKET']
EMBEDDING_DIMENSIONS = [int(d) for d in os.environ.get('EMBEDDING_DIMENSIONS', '256,384,1024,3072').split(',')]

print(f"Lambda initialized - VECTOR_BUCKET: {VECTOR_BUCKET}")
print(f"Lambda initialized - EMBEDDING_DIMENSIONS: {EMBEDDING_DIMENSIONS}")


def handler(event, context):
    """
    Main handler for Store Embeddings Lambda
    
    Args:
        event: Contains outputS3Uri and metadata from previous Lambdas
        context: Lambda context
    
    Returns:
        Dict with success status and storage details
    """
    try:
        output_s3_uri = event['outputS3Uri']
        invocation_arn = event['invocationArn']
        source_metadata = event['metadata']
        
        print(f"Processing embeddings from: {output_s3_uri}")
        print(f"Invocation ARN: {invocation_arn}")
        print(f"Source metadata: {json.dumps(source_metadata)}")
        
        # Extract invocation ID from ARN (last part after /)
        invocation_id = invocation_arn.split('/')[-1]
        print(f"Invocation ID: {invocation_id}")
        
        # Parse S3 URI and append invocation ID
        bucket, prefix = parse_s3_uri(output_s3_uri)
        # Nova MME creates a subdirectory with the invocation ID
        full_prefix = f"{prefix}/{invocation_id}"
        print(f"Parsed - Bucket: {bucket}, Full Prefix: {full_prefix}")
        
        # Read the segmented-embedding-result.json
        result_file = read_result_file(bucket, full_prefix)
        
        # Process each modality's embeddings
        total_stored = 0
        for embedding_result in result_file.get('embeddingResults', []):
            if embedding_result['status'] in ['SUCCESS', 'PARTIAL_SUCCESS']:
                count = process_modality_embeddings(
                    embedding_result,
                    source_metadata,
                    bucket,
                    full_prefix
                )
                total_stored += count
        
        print(f"Successfully stored {total_stored} embedding variants")
        
        return {
            'statusCode': 200,
            'status': 'SUCCESS',
            'embeddingsStored': total_stored,
            'dimensions': EMBEDDING_DIMENSIONS,
            'metadata': source_metadata
        }
        
    except Exception as e:
        print(f"Error storing embeddings: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'status': 'FAILED',
            'error': str(e)
        }


def parse_s3_uri(s3_uri: str) -> tuple:
    """Parse S3 URI into bucket and prefix"""
    parts = s3_uri.replace('s3://', '').split('/', 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ''
    # Remove trailing slash if present
    prefix = prefix.rstrip('/')
    return bucket, prefix


def read_result_file(bucket: str, prefix: str) -> Dict[str, Any]:
    """Read the segmented-embedding-result.json file"""
    key = f"{prefix}/segmented-embedding-result.json"
    
    print(f"Reading result file: s3://{bucket}/{key}")
    
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except Exception as e:
        print(f"Error reading result file. Bucket: {bucket}, Key: {key}")
        print(f"Listing files in prefix to debug:")
        try:
            list_response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            if 'Contents' in list_response:
                for obj in list_response['Contents']:
                    print(f"  Found: {obj['Key']}")
            else:
                print(f"  No files found with prefix: {prefix}")
        except Exception as list_error:
            print(f"  Could not list files: {list_error}")
        raise


def process_modality_embeddings(
    embedding_result: Dict[str, Any],
    source_metadata: Dict[str, Any],
    bucket: str,
    prefix: str
) -> int:
    """
    Process embeddings for a single modality
    
    Returns:
        Number of embedding variants stored
    """
    output_file_uri = embedding_result['outputFileUri']
    embedding_type = embedding_result['embeddingType']
    
    print(f"Processing {embedding_type} embeddings from {output_file_uri}")
    
    # Parse output file URI
    output_bucket, output_key = parse_s3_uri(output_file_uri)
    
    # Read JSONL file
    response = s3_client.get_object(Bucket=output_bucket, Key=output_key)
    content = response['Body'].read().decode('utf-8')
    
    # Process each line (each segment)
    count = 0
    for line in content.strip().split('\n'):
        if not line:
            continue
            
        segment_data = json.loads(line)
        
        if segment_data.get('status') == 'SUCCESS':
            count += process_segment(segment_data, source_metadata, embedding_type)
    
    return count


def process_segment(
    segment_data: Dict[str, Any],
    source_metadata: Dict[str, Any],
    embedding_type: str
) -> int:
    """
    Process a single segment: truncate to all dimensions and store
    
    Returns:
        Number of variants stored (typically 4)
    """
    embedding_3072 = segment_data['embedding']
    segment_metadata = segment_data.get('segmentMetadata', {})
    
    # Create all dimension variants using MRL
    embeddings_by_dim = create_multi_dimensional_embeddings(
        embedding_3072,
        EMBEDDING_DIMENSIONS
    )
    
    # Store each dimension variant
    stored_count = 0
    for dim, embedding in embeddings_by_dim.items():
        # Combine all metadata
        combined_metadata = create_combined_metadata(
            source_metadata,
            segment_metadata,
            embedding_type,
            dim
        )
        
        # Store in S3 Vector index
        store_in_vector_index(dim, embedding, combined_metadata)
        stored_count += 1
    
    return stored_count


def create_combined_metadata(
    source_metadata: Dict[str, Any],
    segment_metadata: Dict[str, Any],
    embedding_type: str,
    dimension: int
) -> Dict[str, Any]:
    """
    Combine metadata from multiple sources
    
    Returns:
        Complete metadata dict for storage
    """
    metadata = {
        # From Lambda 1 (source file metadata)
        'sourceS3Uri': source_metadata.get('sourceS3Uri'),
        'fileName': source_metadata.get('fileName'),
        'fileType': source_metadata.get('fileType'),
        'fileSize': source_metadata.get('fileSize'),
        'uploadTimestamp': source_metadata.get('uploadTimestamp'),
        'contentType': source_metadata.get('contentType'),
        'objectId': source_metadata.get('objectId'),
        
        # From async job output (segment metadata)
        'segmentIndex': segment_metadata.get('segmentIndex'),
        'modalityType': embedding_type,
        
        # From Lambda 3 processing
        'embeddingDimension': dimension,
        'processingTimestamp': datetime.now().isoformat(),
    }
    
    # Add modality-specific segment metadata
    if 'segmentStartSeconds' in segment_metadata:
        metadata['segmentStartSeconds'] = segment_metadata['segmentStartSeconds']
        metadata['segmentEndSeconds'] = segment_metadata['segmentEndSeconds']
    
    if 'segmentStartCharPosition' in segment_metadata:
        metadata['segmentStartCharPosition'] = segment_metadata['segmentStartCharPosition']
        metadata['segmentEndCharPosition'] = segment_metadata['segmentEndCharPosition']
    
    if 'truncatedCharLength' in segment_metadata:
        metadata['truncatedCharLength'] = segment_metadata['truncatedCharLength']
    
    return metadata


def sanitize_metadata_for_s3vectors(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize metadata for S3 Vectors API
    - Only strings, numbers, booleans, and arrays are allowed
    - Convert None to empty string
    - Convert all values to simple types
    """
    sanitized = {}
    for key, value in metadata.items():
        if value is None:
            sanitized[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            sanitized[key] = str(value) if not isinstance(value, bool) else value
        elif isinstance(value, list):
            # Convert list items to strings
            sanitized[key] = [str(v) for v in value]
        elif isinstance(value, dict):
            # Skip nested dicts - S3 Vectors doesn't support them
            continue
        else:
            # Convert everything else to string
            sanitized[key] = str(value)
    return sanitized


def store_in_vector_index(
    dimension: int,
    embedding: List[float],
    metadata: Dict[str, Any]
):
    """
    Store embedding in S3 Vector index using S3 Vectors API
    """
    index_name = f"embeddings-{dimension}d"
    
    # Create a unique vector ID
    object_id = metadata['objectId']
    segment_index = metadata.get('segmentIndex', 0)
    vector_id = f"{object_id}_segment_{segment_index}"
    
    # Sanitize metadata for S3 Vectors
    clean_metadata = sanitize_metadata_for_s3vectors(metadata)
    
    # Prepare vector object for S3 Vectors API
    # The API expects 'key', 'data' with 'float32' array, and 'metadata'
    # IMPORTANT: Must convert to numpy.float32 as per S3 Vectors API requirements
    vector_obj = {
        'key': vector_id,
        'data': {
            'float32': np.array(embedding, dtype=np.float32).tolist()
        },
        'metadata': clean_metadata
    }
    
    # Use S3 Vectors put_vectors API (batch operation)
    s3vectors_client.put_vectors(
        vectorBucketName=VECTOR_BUCKET,
        indexName=index_name,
        vectors=[vector_obj]
    )
    
    print(f"Stored {dimension}d embedding in S3 Vector index {index_name}: {vector_id}")
    #     index=index_name,
    #     vector_id=f"{object_id}_segment_{segment_index}",
    #     vector=embedding,
    #     metadata=metadata
    # )
