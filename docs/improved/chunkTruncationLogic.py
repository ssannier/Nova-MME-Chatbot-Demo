import json
import numpy as np
import boto3

s3 = boto3.client('s3')

def truncate_and_normalize(embedding, target_dim):
    """Truncate embedding to target dimension and renormalize."""
    truncated = np.array(embedding[:target_dim])
    normalized = truncated / np.linalg.norm(truncated)
    return normalized.tolist()

def process_embedding_file(s3_uri, output_bucket, object_id):
    """Process a single embedding JSONL file and create multi-dimensional variants."""
    # Parse S3 URI
    bucket = s3_uri.split('/')[2]
    key = '/'.join(s3_uri.split('/')[3:])
    
    # Download and read JSONL file
    response = s3.get_object(Bucket=bucket, Key=key)
    content = response['Body'].read().decode('utf-8')
    
    # Process each line (each chunk/segment)
    embeddings_by_dimension = {256: [], 384: [], 1024: [], 3072: []}
    
    for line in content.strip().split('\n'):
        chunk_data = json.loads(line)
        
        if chunk_data.get('status') == 'SUCCESS':
            embedding_3072 = chunk_data['embedding']
            segment_metadata = chunk_data.get('segmentMetadata', {})
            
            # Create all dimension variants
            for dim in [256, 384, 1024]:
                truncated = truncate_and_normalize(embedding_3072, dim)
                embeddings_by_dimension[dim].append({
                    'embedding': truncated,
                    'metadata': segment_metadata,
                    'objectId': object_id,
                    'dimension': dim
                })
            
            # Store full 3072-dim version
            embeddings_by_dimension[3072].append({
                'embedding': embedding_3072,
                'metadata': segment_metadata,
                'objectId': object_id,
                'dimension': 3072
            })
    
    return embeddings_by_dimension

def lambda_handler(event, context):
    """Lambda 3: Store Embeddings with multi-dimensional indexing."""
    
    # Get the async job output location from event
    job_output_s3_uri = event['outputS3Uri']  # e.g., s3://bucket/job-id/
    
    # Read the segmented-embedding-result.json
    result_file = f"{job_output_s3_uri}/segmented-embedding-result.json"
    # ... parse result file to get outputFileUri for each modality
    
    # For each modality's embedding file (e.g., embedding-text.jsonl, embedding-video.jsonl)
    for modality_result in embedding_results:
        if modality_result['status'] in ['SUCCESS', 'PARTIAL_SUCCESS']:
            output_file_uri = modality_result['outputFileUri']
            object_id = event['objectId']  # Original S3 object identifier
            
            # Process the JSONL file and get all dimension variants
            embeddings_by_dim = process_embedding_file(
                output_file_uri, 
                output_bucket='nova-mme-demo-embeddings',
                object_id=object_id
            )
            
            # Store each dimension variant in its respective S3 Vector index
            for dim, embeddings_list in embeddings_by_dim.items():
                index_name = f"embeddings-{dim}d"
                
                # Batch insert into S3 Vector index
                # (Pseudo-code - actual S3 Vector API calls would go here)
                for embedding_data in embeddings_list:
                    store_in_s3_vector_index(
                        index_name=index_name,
                        embedding=embedding_data['embedding'],
                        metadata=embedding_data['metadata'],
                        object_id=embedding_data['objectId']
                    )
    
    return {
        'statusCode': 200,
        'message': f'Stored embeddings across all dimensions'
    }
