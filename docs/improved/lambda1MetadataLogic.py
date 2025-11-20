# Lambda 1: Nova MME Processor
def lambda_handler(event, context):
    # Get S3 object info from trigger
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']
    
    # Gather metadata
    s3_client = boto3.client('s3')
    obj_metadata = s3_client.head_object(Bucket=bucket, Key=key)
    
    metadata = {
        'sourceS3Uri': f"s3://{bucket}/{key}",
        'fileName': key.split('/')[-1],
        'fileType': key.split('.')[-1],
        'fileSize': obj_metadata['ContentLength'],
        'uploadTimestamp': obj_metadata['LastModified'].isoformat(),
        'contentType': obj_metadata.get('ContentType', 'unknown')
    }
    
    # Start async invocation
    response = bedrock_runtime.start_async_invoke(...)
    
    # Return metadata + invocation ARN for Step Functions
    return {
        'invocationArn': response['invocationArn'],
        'metadata': metadata
    }
