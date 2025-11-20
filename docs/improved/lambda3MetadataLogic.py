# Lambda 3: Store Embeddings
def lambda_handler(event, context):
    job_output_uri = event['outputS3Uri']
    source_metadata = event['metadata']  # From Lambda 1
    
    # Process embeddings...
    for embedding_data in embeddings_list:
        store_in_s3_vector_index(
            embedding=embedding_data['embedding'],
            metadata={
                # From Lambda 1
                'sourceS3Uri': source_metadata['sourceS3Uri'],
                'fileName': source_metadata['fileName'],
                'fileType': source_metadata['fileType'],
                'uploadTimestamp': source_metadata['uploadTimestamp'],
                
                # From async job output
                'segmentIndex': embedding_data['segmentMetadata']['segmentIndex'],
                'segmentStartSeconds': embedding_data['segmentMetadata'].get('segmentStartSeconds'),
                'segmentEndSeconds': embedding_data['segmentMetadata'].get('segmentEndSeconds'),
                'modalityType': embedding_data['embeddingType'],
                
                # From Lambda 3 processing
                'embeddingDimension': dim,
                'processingTimestamp': datetime.now().isoformat()
            }
        )
