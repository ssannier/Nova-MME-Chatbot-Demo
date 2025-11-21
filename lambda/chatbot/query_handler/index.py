"""
Lambda: Query Handler

Handles user queries for the Nova MME chatbot:
1. Embeds user query using Nova MME (synchronous)
2. Searches S3 Vector indexes (with optional hierarchical search)
3. Formats prompt with retrieved context
4. Calls Claude for response generation
5. Returns formatted response to frontend
"""

import json
import os
import boto3
from typing import Dict, Any, List
from datetime import datetime

# Initialize clients
bedrock_runtime = boto3.client('bedrock-runtime')
s3_client = boto3.client('s3')

# Environment variables
VECTOR_BUCKET = os.environ['VECTOR_BUCKET']
EMBEDDING_MODEL_ID = os.environ['EMBEDDING_MODEL_ID']
LLM_MODEL_ID = os.environ['LLM_MODEL_ID']
LLM_REGION = os.environ.get('LLM_REGION', os.environ.get('AWS_REGION', 'us-east-1'))
DEFAULT_DIMENSION = int(os.environ.get('DEFAULT_DIMENSION', '1024'))
DEFAULT_K = int(os.environ.get('DEFAULT_K', '5'))
HIERARCHICAL_ENABLED = os.environ.get('HIERARCHICAL_ENABLED', 'true').lower() == 'true'
HIERARCHICAL_CONFIG = json.loads(os.environ.get('HIERARCHICAL_CONFIG', '{}'))
VECTOR_INDEXES = json.loads(os.environ.get('VECTOR_INDEXES', '{}'))

# Create region-specific Bedrock client for LLM if needed
bedrock_runtime_llm = boto3.client('bedrock-runtime', region_name=LLM_REGION) if LLM_REGION != os.environ.get('AWS_REGION') else bedrock_runtime


def handler(event, context):
    """
    Main handler for Query Handler Lambda
    
    Expected input (from API Gateway):
    {
        "body": "{\"query\": \"user question\", \"dimension\": 1024, \"hierarchical\": true}"
    }
    
    Returns:
    {
        "statusCode": 200,
        "headers": {...},
        "body": "{\"answer\": \"...\", \"sources\": [...], \"model\": \"...\"}"
    }
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        query = body.get('query', '')
        dimension = body.get('dimension', DEFAULT_DIMENSION)
        use_hierarchical = body.get('hierarchical', HIERARCHICAL_ENABLED)
        k = body.get('k', DEFAULT_K)
        
        if not query:
            return create_response(400, {'error': 'Query is required'})
        
        print(f"Processing query: {query[:100]}... (dimension={dimension}, hierarchical={use_hierarchical})")
        
        # Step 1: Embed the query
        query_embedding = embed_query(query, dimension)
        
        # Step 2: Search for relevant documents
        if use_hierarchical and HIERARCHICAL_CONFIG:
            sources = hierarchical_search(query_embedding, k)
        else:
            sources = simple_search(query_embedding, dimension, k)
        
        print(f"Found {len(sources)} relevant sources")
        
        # Step 3: Format prompt with context
        prompt = format_prompt(query, sources)
        
        # Step 4: Get response from Claude
        answer = call_claude(prompt)
        
        # Step 5: Format response for frontend
        response_data = {
            'answer': answer,
            'sources': format_sources(sources),
            'model': LLM_MODEL_ID,
            'query': query,
            'dimension': dimension,
            'resultsFound': len(sources)
        }
        
        return create_response(200, response_data)
        
    except Exception as e:
        print(f"Error processing query: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_response(500, {
            'error': 'Internal server error',
            'message': str(e)
        })


def embed_query(query: str, dimension: int) -> List[float]:
    """
    Embed user query using Nova MME synchronous API
    
    Returns:
        List of floats representing the embedding vector
    """
    model_input = {
        "schemaVersion": "nova-multimodal-embed-v1",
        "taskType": "SINGLE_EMBEDDING",
        "singleEmbeddingParams": {
            "embeddingPurpose": "GENERIC_RETRIEVAL",
            "embeddingDimension": dimension,
            "text": {
                "truncationMode": "END",
                "value": query
            }
        }
    }
    
    response = bedrock_runtime.invoke_model(
        modelId=EMBEDDING_MODEL_ID,
        body=json.dumps(model_input)
    )
    
    result = json.loads(response['body'].read())
    embedding = result['embeddings'][0]['embedding']
    
    return embedding


def simple_search(query_embedding: List[float], dimension: int, k: int) -> List[Dict[str, Any]]:
    """
    Simple vector search at specified dimension
    
    Returns:
        List of source documents with metadata
    """
    index_name = f"embeddings-{dimension}d"
    
    # TODO: Replace with actual S3 Vector API call
    # For now, this is a placeholder that reads from S3 structure
    sources = search_s3_vector_index(index_name, query_embedding, k)
    
    return sources


def hierarchical_search(query_embedding: List[float], final_k: int) -> List[Dict[str, Any]]:
    """
    Hierarchical search: fast coarse search followed by precise refinement
    
    1. First pass: Search at 256-dim for broad recall (top 20)
    2. Second pass: Re-rank top results using 1024-dim for precision (top 5)
    
    Returns:
        List of refined source documents
    """
    # First pass: Fast, broad search
    first_dim = HIERARCHICAL_CONFIG.get('first_pass_dimension', 256)
    first_k = HIERARCHICAL_CONFIG.get('first_pass_k', 20)
    
    print(f"Hierarchical search - First pass: {first_dim}d, k={first_k}")
    
    # Truncate query embedding to first pass dimension
    first_embedding = query_embedding[:first_dim]
    first_results = simple_search(first_embedding, first_dim, first_k)
    
    # Second pass: Precise re-ranking
    second_dim = HIERARCHICAL_CONFIG.get('second_pass_dimension', 1024)
    second_k = HIERARCHICAL_CONFIG.get('second_pass_k', final_k)
    
    print(f"Hierarchical search - Second pass: {second_dim}d, k={second_k}")
    
    # Re-rank first pass results using higher dimension
    second_embedding = query_embedding[:second_dim]
    refined_results = rerank_results(first_results, second_embedding, second_k)
    
    return refined_results


def search_s3_vector_index(index_name: str, embedding: List[float], k: int) -> List[Dict[str, Any]]:
    """
    Search S3 Vector index for similar embeddings using native S3 Vectors API
    
    S3 Vectors supports all 4 MRL dimensions (256, 384, 1024, 3072)
    """
    results = []
    
    try:
        # Query S3 Vectors index using native similarity search
        response = s3_client.query_vectors(
            Bucket=VECTOR_BUCKET,
            IndexName=index_name,
            QueryVector=embedding,
            MaxResults=k,
            DistanceMetric='cosine'
        )
        
        print(f"S3 Vectors query returned {len(response.get('Vectors', []))} results")
        
        # Process results
        for vector_result in response.get('Vectors', []):
            try:
                # Read full object to get metadata
                # S3 Vectors returns the key, we need to fetch the full object
                obj_response = s3_client.get_object(
                    Bucket=VECTOR_BUCKET,
                    Key=vector_result['Key']
                )
                data = json.loads(obj_response['Body'].read())
                
                # Convert distance to similarity
                # S3 Vectors returns cosine distance (0 = identical)
                # We want similarity (1 = identical)
                distance = vector_result.get('Distance', 0)
                similarity = 1 - distance
                
                results.append({
                    'similarity': similarity,
                    'metadata': data['metadata'],
                    'embedding': data['vector']
                })
                
            except Exception as e:
                print(f"Error reading vector object {vector_result.get('Key')}: {e}")
                continue
        
        print(f"Successfully processed {len(results)} results from S3 Vectors")
        
    except Exception as e:
        print(f"Error querying S3 Vectors index {index_name}: {e}")
        import traceback
        traceback.print_exc()
    
    return results


def rerank_results(results: List[Dict[str, Any]], embedding: List[float], k: int) -> List[Dict[str, Any]]:
    """
    Re-rank results using a higher-dimension embedding
    """
    scored = []
    for result in results:
        # Truncate stored embedding to match query dimension
        stored_embedding = result['embedding'][:len(embedding)]
        similarity = cosine_similarity(embedding, stored_embedding)
        
        scored.append({
            'similarity': similarity,
            'metadata': result['metadata']
        })
    
    # Sort by new similarity scores
    scored.sort(key=lambda x: x['similarity'], reverse=True)
    return scored[:k]


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    import math
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)


def format_prompt(query: str, sources: List[Dict[str, Any]]) -> str:
    """
    Format prompt for Claude with retrieved context
    
    For text: Includes actual content
    For media: Includes descriptive metadata and S3 URI for reference
    """
    # Build context from sources
    context_parts = []
    for i, source in enumerate(sources, 1):
        metadata = source.get('metadata', {})
        filename = metadata.get('fileName', 'Unknown')
        modality = metadata.get('modalityType', 'Unknown')
        source_uri = metadata.get('sourceS3Uri', '')
        
        # Build source context based on modality
        source_context = f"Source {i} - {filename} ({modality})"
        
        # For text, try to get actual content
        if modality == 'TEXT':
            content = get_text_content(source_uri, metadata)
            if content:
                source_context += f"\nContent:\n{content}"
            else:
                source_context += f"\n[Text file: {filename}]"
        
        # For images, provide description
        elif modality == 'IMAGE':
            source_context += f"\n[Image file: {filename}]"
            source_context += f"\nLocation: {source_uri}"
        
        # For video, provide segment info
        elif modality == 'VIDEO':
            segment_idx = metadata.get('segmentIndex', 0)
            start_time = metadata.get('segmentStartSeconds', 0)
            end_time = metadata.get('segmentEndSeconds', 0)
            source_context += f"\n[Video segment {segment_idx}: {start_time:.1f}s - {end_time:.1f}s]"
            source_context += f"\nLocation: {source_uri}"
        
        # For audio, provide segment info
        elif modality == 'AUDIO':
            segment_idx = metadata.get('segmentIndex', 0)
            start_time = metadata.get('segmentStartSeconds', 0)
            end_time = metadata.get('segmentEndSeconds', 0)
            source_context += f"\n[Audio segment {segment_idx}: {start_time:.1f}s - {end_time:.1f}s]"
            source_context += f"\nLocation: {source_uri}"
        
        context_parts.append(source_context)
    
    context = "\n\n".join(context_parts)
    
    # Format prompt
    prompt = f"""You are a helpful assistant answering questions based on a multimodal knowledge base.

Context from relevant sources:
{context}

User Question: {query}

Instructions:
- Answer the question using ONLY the information provided in the sources above
- For text sources, use the actual content provided
- For media sources (images, videos, audio), reference them by filename and describe what type of content they are
- If the sources don't contain enough information to answer, say so clearly
- Cite which sources you used in your answer (e.g., "According to video.mp4...")
- Be concise but thorough

Answer:"""
    
    return prompt


def get_text_content(source_uri: str, metadata: Dict[str, Any]) -> str:
    """
    Retrieve actual text content from S3 for text sources
    
    Args:
        source_uri: S3 URI of the source file
        metadata: Metadata including segment information
    
    Returns:
        Text content (truncated if needed)
    """
    if not source_uri or not source_uri.startswith('s3://'):
        return ""
    
    try:
        # Parse S3 URI
        parts = source_uri.replace('s3://', '').split('/', 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ''
        
        # Download file
        response = s3_client.get_object(Bucket=bucket, Key=key)
        full_content = response['Body'].read().decode('utf-8', errors='ignore')
        
        # If this is a segment, extract the relevant portion
        start_char = metadata.get('segmentStartCharPosition')
        end_char = metadata.get('segmentEndCharPosition')
        
        if start_char is not None and end_char is not None:
            content = full_content[start_char:end_char]
        else:
            content = full_content
        
        # Truncate if too long (keep first 2000 chars for context)
        MAX_CHARS = 2000
        if len(content) > MAX_CHARS:
            content = content[:MAX_CHARS] + f"\n\n[Content truncated - showing first {MAX_CHARS} characters]"
        
        return content
        
    except Exception as e:
        print(f"Error retrieving text content from {source_uri}: {e}")
        return ""


def call_claude(prompt: str) -> str:
    """
    Call Claude for response generation
    """
    max_tokens = int(os.environ.get('LLM_MAX_TOKENS', '2048'))
    temperature = float(os.environ.get('LLM_TEMPERATURE', '0.7'))
    
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    
    response = bedrock_runtime_llm.invoke_model(
        modelId=LLM_MODEL_ID,
        body=json.dumps(request_body)
    )
    
    result = json.loads(response['body'].read())
    answer = result['content'][0]['text']
    
    return answer


def format_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Format sources for frontend display
    
    Returns format expected by ChatWindow.tsx:
    [
        {
            "key": "filename.mp4",
            "similarity": 0.95,
            "text_preview": "Preview text..."
        }
    ]
    """
    formatted = []
    
    for source in sources:
        metadata = source.get('metadata', {})
        similarity = source.get('similarity', 0.0)
        
        # Extract key information
        filename = metadata.get('fileName', 'Unknown')
        modality = metadata.get('modalityType', 'Unknown')
        source_uri = metadata.get('sourceS3Uri', '')
        
        # Create preview text
        preview_parts = [f"Type: {modality}"]
        
        if 'segmentIndex' in metadata:
            preview_parts.append(f"Segment: {metadata['segmentIndex']}")
        
        if 'segmentStartSeconds' in metadata:
            start = metadata['segmentStartSeconds']
            end = metadata.get('segmentEndSeconds', start)
            preview_parts.append(f"Time: {start:.1f}s - {end:.1f}s")
        
        if 'segmentStartCharPosition' in metadata:
            start = metadata['segmentStartCharPosition']
            end = metadata.get('segmentEndCharPosition', start)
            preview_parts.append(f"Chars: {start}-{end}")
        
        preview = " | ".join(preview_parts)
        
        formatted.append({
            'key': filename,
            'similarity': similarity,
            'text_preview': preview
        })
    
    return formatted


def create_response(status_code: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create API Gateway response with CORS headers
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        'body': json.dumps(data)
    }
