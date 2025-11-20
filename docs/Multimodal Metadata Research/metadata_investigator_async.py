import boto3
import json
import time
from urllib.parse import urlparse

S3_BUCKET = "cic-multimedia-test"
# Where preprocessed objects are stored
DATA_DIR = "data"
# Where embeddings will be stored
S3_OUTPUT_DIR = "embeddings-output"
MODEL_ID = "amazon.nova-2-multimodal-embeddings-v1:0"
REGION = "us-east-1"
EMBEDDING_DIMENSION = 256

def get_object_info(s3_key):
    """Get object type and file extension"""
    ext = s3_key.lower().split('.')[-1]
    if ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']:
        return 'image', ext
    elif ext in ['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv', 'mpeg', 'mpg', '3gp']:
        return 'video', ext
    elif ext in ['mp3', 'wav', 'ogg']:
        return 'audio', ext
    elif ext in ['txt', 'md', 'json', 'csv']:
        return 'text', ext
    elif ext in ['pdf', 'docx']:
        return 'document', ext
    else:
        return 'image', 'jpeg'  # Default fallback

def get_base_request():
    """Get the common part of the request"""
    return {
        "schemaVersion": "nova-multimodal-embed-v1",
        "taskType": "SEGMENTED_EMBEDDING",
        "segmentedEmbeddingParams": {
            "embeddingPurpose": "GENERIC_INDEX",
            "embeddingDimension": EMBEDDING_DIMENSION
        }
    }

def get_type_specific_config(s3_uri, object_type, file_ext):
    """Get type-specific configuration based on object type and extension"""
    source_obj = {
        "s3Location": {
            "uri": s3_uri
        }
    }
    
    if object_type == 'video':
        format_map = {'mp4': 'mp4', 'mov': 'mov', 'mkv': 'mkv', 'webm': 'webm', 
                     'flv': 'flv', 'mpeg': 'mpeg', 'mpg': 'mpg', 'wmv': 'wmv', '3gp': '3gp'}
        return {
            "video": {
                "format": format_map.get(file_ext, 'mp4'),
                "source": source_obj,
                "embeddingMode": "AUDIO_VIDEO_COMBINED",
                "segmentationConfig": {
                    "durationSeconds": 30
                }
            }
        }
    elif object_type == 'audio':
        return {
            "audio": {
                "format": file_ext,
                "source": source_obj,
                "segmentationConfig": {
                    "durationSeconds": 30
                }
            }
        }
    elif object_type == 'image':
        format_map = {'jpg': 'jpeg', 'jpeg': 'jpeg', 'png': 'png', 'gif': 'gif', 'webp': 'webp'}
        return {
            "image": {
                "format": format_map.get(file_ext, 'jpeg'),
                "source": source_obj,
                "detailLevel": "STANDARD_IMAGE"
            }
        }
    elif object_type == 'document':
        # Documents are processed as images with DOCUMENT_IMAGE detail level
        # Format should be an image format, as documents are converted to images internally
        return {
            "image": {
                "format": "jpeg",  # Use jpeg format for document processing
                "source": source_obj,
                "detailLevel": "DOCUMENT_IMAGE"
            }
        }

    elif object_type == 'text':
        return {
            "text": {
                "source": source_obj,
                "truncationMode": "NONE",
                "segmentationConfig": {
                    "maxLengthChars": 8000
                }
            }
        }
    else:
        return {object_type: {"source": source_obj}}

def create_async_request(s3_uri, object_type, file_ext):
    """Create the complete request payload"""
    request = get_base_request()
    type_config = get_type_specific_config(s3_uri, object_type, file_ext)
    request["segmentedEmbeddingParams"].update(type_config)
    return request

def main():
    # Initialize boto3 clients
    s3_client = boto3.client('s3', region_name=REGION)
    bedrock_client = boto3.client('bedrock-runtime', region_name=REGION)
    
    # S3 object configuration
    object_name = input("Enter S3 object filename: ")
    s3_uri = f"s3://{S3_BUCKET}/{DATA_DIR}/{object_name}"
    
    # Determine object type and extension
    object_type, file_ext = get_object_info(object_name)
    print(f"Detected object type: {object_type}, format: {file_ext}")
    
    # Create async request
    request_body = create_async_request(s3_uri, object_type, file_ext)
    output_s3_uri = f"s3://{S3_BUCKET}/{S3_OUTPUT_DIR}/"
    
    print(f"Request body: {json.dumps(request_body, indent=2)}")
    
    # Start async invocation
    response = bedrock_client.start_async_invoke(
        modelId=MODEL_ID,
        modelInput=request_body,
        outputDataConfig={
            "s3OutputDataConfig": {
                "s3Uri": output_s3_uri
            }
        }
    )
    
    invocation_arn = response['invocationArn']
    print(f"Started async invocation: {invocation_arn}")
    
    # Poll for completion
    while True:
        status_response = bedrock_client.get_async_invoke(invocationArn=invocation_arn)
        status = status_response['status']
        print(f"Status: {status}")
        
        if status == 'Completed':
            output_uri = status_response['outputDataConfig']['s3OutputDataConfig']['s3Uri']
            print(f"Completed. Output location: {output_uri}")
            
            # Parse output URI and read results
            parsed_uri = urlparse(output_uri)
            output_bucket = parsed_uri.netloc
            output_prefix = parsed_uri.path.lstrip('/')
            
            # List and read output files
            response = s3_client.list_objects_v2(
                Bucket=output_bucket,
                Prefix=output_prefix
            )
            
            for obj in response.get('Contents', []):
                result = s3_client.get_object(Bucket=output_bucket, Key=obj['Key'])
                content = result['Body'].read().decode('utf-8')
                
                if obj['Key'].endswith('.jsonl'):
                    # Process JSONL embedding files
                    print(f"\nEmbedding file: {obj['Key']}")
                    for line_num, line in enumerate(content.strip().split('\n'), 1):
                        if line:
                            embedding_data = json.loads(line)
                            if 'metadata' in embedding_data:
                                print(f"Chunk {line_num} Metadata:")
                                print(json.dumps(embedding_data['metadata'], indent=2))
                            else:
                                print(f"Chunk {line_num} (no metadata field):")
                                # Show structure without the large embedding vector
                                display_data = {k: v for k, v in embedding_data.items() if k != 'embedding'}
                                if 'embedding' in embedding_data:
                                    display_data['embedding'] = f"[{len(embedding_data['embedding'])} dimensions]"
                                print(json.dumps(display_data, indent=2))
                elif obj['Key'].endswith('.json'):
                    # Process JSON status/manifest files
                    print(f"\nStatus file: {obj['Key']}")
                    try:
                        parsed_content = json.loads(content)
                        print(json.dumps(parsed_content, indent=2))
                    except json.JSONDecodeError:
                        print(content)
            break
            
        elif status == 'Failed':
            print("Invocation failed")
            if 'failureMessage' in status_response:
                print(f"Error: {status_response['failureMessage']}")
            
            # Try to read the status file for detailed error info
            output_uri = status_response['outputDataConfig']['s3OutputDataConfig']['s3Uri']
            parsed_uri = urlparse(output_uri)
            output_bucket = parsed_uri.netloc
            output_prefix = parsed_uri.path.lstrip('/')
            
            print(f"Looking for status files in: s3://{output_bucket}/{output_prefix}")
            
            try:
                response = s3_client.list_objects_v2(
                    Bucket=output_bucket,
                    Prefix=output_prefix
                )
                
                if 'Contents' in response:
                    print(f"Found {len(response['Contents'])} files:")
                    for obj in response['Contents']:
                        print(f"  - {obj['Key']}")
                        
                        # Read all files to understand the output structure
                        result = s3_client.get_object(Bucket=output_bucket, Key=obj['Key'])
                        content = result['Body'].read().decode('utf-8')
                        print(f"\nContent of {obj['Key']}:")
                        try:
                            parsed_content = json.loads(content)
                            print(json.dumps(parsed_content, indent=2))
                        except json.JSONDecodeError:
                            print(content)
                else:
                    print("No files found in output location")
                    
            except Exception as e:
                print(f"Could not read status files: {e}")
                print(f"Exception type: {type(e).__name__}")
            break
        
        time.sleep(30)

if __name__ == "__main__":
    main()