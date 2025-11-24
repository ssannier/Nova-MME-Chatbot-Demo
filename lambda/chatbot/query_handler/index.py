"""
Lambda: Query Handler

Handles user queries for the Nova MME chatbot:
1. Embeds user query using Nova MME (synchronous)
2. Searches S3 Vector indexes (with optional hierarchical search)
3. Fetches actual media content (images, PDFs) from S3
4. Formats multimodal prompt with retrieved context
5. Calls Claude for response generation
6. Returns formatted response to frontend
"""

import json
import os
import boto3
import base64
from typing import Dict, Any, List
from datetime import datetime

# Initialize clients
bedrock_runtime = boto3.client('bedrock-runtime')
s3_client = boto3.client('s3')
s3vectors_client = boto3.client('s3vectors')

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
        
        # Track processing steps for transparency
        processing_steps = []
        
        # Step 1: Embed the query
        processing_steps.append(f"🔍 Embedding query at {dimension} dimensions using Nova MME...")
        query_embedding = embed_query(query, dimension)
        processing_steps.append(f"✓ Query embedded successfully")
        
        # Step 2: Search for relevant documents
        if use_hierarchical and HIERARCHICAL_CONFIG:
            first_dim = HIERARCHICAL_CONFIG.get('first_pass_dimension', 256)
            second_dim = HIERARCHICAL_CONFIG.get('second_pass_dimension', 1024)
            processing_steps.append(f"🔎 Hierarchical search: First pass at {first_dim}d (fast, broad)...")
            sources = hierarchical_search(query_embedding, k, processing_steps)
            processing_steps.append(f"🎯 Second pass at {second_dim}d (precise refinement)...")
        else:
            processing_steps.append(f"🔎 Searching {dimension}d vector index...")
            sources = simple_search(query_embedding, dimension, k)
            processing_steps.append(f"✓ Found {len(sources)} potential matches")
        
        # Filter sources by similarity threshold (remove low-relevance results)
        SIMILARITY_THRESHOLD = 0.60  # 60% minimum similarity
        filtered_sources = [s for s in sources if s.get('similarity', 0) >= SIMILARITY_THRESHOLD]
        
        print(f"Found {len(sources)} sources, {len(filtered_sources)} above {SIMILARITY_THRESHOLD:.0%} threshold")
        processing_steps.append(f"✓ Filtered to {len(filtered_sources)} highly relevant sources (>{SIMILARITY_THRESHOLD:.0%} similarity)")
        
        # Handle no results case
        if len(filtered_sources) == 0:
            processing_steps.append(f"⚠️ No relevant sources found above {SIMILARITY_THRESHOLD:.0%} similarity threshold")
            
            # Return helpful fallback response
            no_results_response = create_no_results_response(query, len(sources))
            
            return create_response(200, {
                'answer': no_results_response,
                'sources': [],
                'model': LLM_MODEL_ID,
                'query': query,
                'dimension': dimension,
                'resultsFound': 0,
                'processingSteps': processing_steps
            })
        
        # Step 3: Fetch media content and format prompt
        processing_steps.append(f"📝 Fetching media content and preparing context...")
        multimodal_content = prepare_multimodal_content(query, filtered_sources)
        
        # Step 4: Get response from Claude
        processing_steps.append(f"🤖 Generating response with Claude ({LLM_MODEL_ID})...")
        answer = call_claude_multimodal(multimodal_content)
        processing_steps.append(f"✓ Response generated successfully")
        
        # Step 5: Format response for frontend
        formatted_sources = format_sources(filtered_sources)
        
        # Debug: Log formatted sources
        print(f"Formatted sources: {formatted_sources}")
        
        response_data = {
            'answer': answer,
            'sources': formatted_sources,
            'model': LLM_MODEL_ID,
            'query': query,
            'dimension': dimension,
            'resultsFound': len(filtered_sources),
            'processingSteps': processing_steps  # Add processing transparency
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


def hierarchical_search(query_embedding: List[float], final_k: int, processing_steps: List[str] = None) -> List[Dict[str, Any]]:
    """
    Hierarchical search: fast coarse search followed by precise refinement
    
    Since S3 Vectors API doesn't return vector data, we do two separate searches:
    1. First pass: Search at 256-dim for broad recall (top 20)
    2. Second pass: Search at 1024-dim on the same query for precision (top 5)
    
    This demonstrates the MRL speed/accuracy tradeoff without manual reranking.
    
    Returns:
        List of refined source documents
    """
    # First pass: Fast, broad search at lower dimension
    first_dim = HIERARCHICAL_CONFIG.get('first_pass_dimension', 256)
    first_k = HIERARCHICAL_CONFIG.get('first_pass_k', 20)
    
    print(f"Hierarchical search - First pass: {first_dim}d, k={first_k}")
    if processing_steps is not None:
        processing_steps.append(f"  → Searching {first_dim}d index for top {first_k} candidates...")
    
    # Truncate query embedding to first pass dimension
    first_embedding = query_embedding[:first_dim]
    first_results = simple_search(first_embedding, first_dim, first_k)
    
    if processing_steps is not None:
        processing_steps.append(f"  ✓ Found {len(first_results)} candidates from fast search")
    
    # Second pass: Precise search at higher dimension
    # Note: We search again rather than rerank because S3 Vectors doesn't return vector data
    second_dim = HIERARCHICAL_CONFIG.get('second_pass_dimension', 1024)
    second_k = HIERARCHICAL_CONFIG.get('second_pass_k', final_k)
    
    print(f"Hierarchical search - Second pass: {second_dim}d, k={second_k}")
    if processing_steps is not None:
        processing_steps.append(f"  → Searching {second_dim}d index for top {second_k} precise matches...")
    
    # Search at higher dimension for better precision
    second_embedding = query_embedding[:second_dim]
    refined_results = simple_search(second_embedding, second_dim, second_k)
    
    if processing_steps is not None:
        processing_steps.append(f"  ✓ Refined to {len(refined_results)} highly relevant matches")
    
    return refined_results


def search_s3_vector_index(index_name: str, embedding: List[float], k: int) -> List[Dict[str, Any]]:
    """
    Search S3 Vector index for similar embeddings using native S3 Vectors API
    
    S3 Vectors supports all 4 MRL dimensions (256, 384, 1024, 3072)
    """
    results = []
    
    try:
        # Query S3 Vectors index using native similarity search
        # queryVector must be a dict with 'float32' key, not a list
        # Note: S3 Vectors API doesn't support returnData, so we can't get embeddings back for reranking
        response = s3vectors_client.query_vectors(
            vectorBucketName=VECTOR_BUCKET,
            indexName=index_name,
            queryVector={'float32': embedding},
            topK=k,
            returnMetadata=True,
            returnDistance=True
        )
        
        print(f"S3 Vectors query returned {len(response.get('vectors', []))} results")
        
        # Process results
        # S3 Vectors query_vectors returns key, data, metadata, and distance directly
        for vector_result in response.get('vectors', []):
            try:
                # Convert distance to similarity
                # S3 Vectors returns cosine distance (0 = identical, 2 = opposite)
                # We want similarity (1 = identical, 0 = opposite)
                distance = vector_result.get('distance', 0)
                similarity = 1 - (distance / 2)  # Normalize to 0-1 range
                
                # Extract metadata and embedding from response
                metadata = vector_result.get('metadata', {})
                embedding = vector_result.get('data', {}).get('float32', [])
                
                results.append({
                    'similarity': similarity,
                    'metadata': metadata,
                    'embedding': embedding
                })
                
                print(f"Found vector: {vector_result.get('key')} with distance {distance:.4f}")
                
            except Exception as e:
                print(f"Error processing vector result {vector_result.get('key')}: {e}")
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
        stored_embedding = result.get('embedding', [])
        
        # Debug: Check if embedding exists
        if not stored_embedding:
            print(f"WARNING: No embedding found in result, using original similarity")
            # Fall back to original similarity from S3 Vectors
            scored.append({
                'similarity': result.get('similarity', 0.0),
                'metadata': result['metadata']
            })
            continue
        
        stored_embedding_truncated = stored_embedding[:len(embedding)]
        similarity = cosine_similarity(embedding, stored_embedding_truncated)
        
        print(f"Rerank: query_dim={len(embedding)}, stored_dim={len(stored_embedding)}, similarity={similarity:.4f}")
        
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
            # Check if this is a PDF page (converted to image)
            is_pdf_str = metadata.get('isPdf', 'False')
            is_pdf = str(is_pdf_str).lower() == 'true'
            page_num = metadata.get('processedPage')
            
            if is_pdf and page_num is not None:
                page_num = int(page_num)
                source_context += f"\n[PDF document - Page {page_num}]"
                source_context += f"\nThis page was semantically matched to your query based on its visual and textual content."
                source_context += f"\nThe page likely contains relevant information about your question."
            else:
                source_context += f"\n[Image file: {filename}]"
            
            source_context += f"\nLocation: {source_uri}"
        
        # For video, provide segment info
        elif modality == 'VIDEO':
            segment_idx = int(metadata.get('segmentIndex', 0))
            start_time = float(metadata.get('segmentStartSeconds', 0))
            end_time = float(metadata.get('segmentEndSeconds', 0))
            source_context += f"\n[Video segment {segment_idx}: {start_time:.1f}s - {end_time:.1f}s]"
            source_context += f"\nLocation: {source_uri}"
        
        # For audio, provide segment info
        elif modality == 'AUDIO':
            segment_idx = int(metadata.get('segmentIndex', 0))
            start_time = float(metadata.get('segmentStartSeconds', 0))
            end_time = float(metadata.get('segmentEndSeconds', 0))
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
- Answer the question using the information from the sources above
- For text sources, use the actual content provided
- For PDF pages: These were semantically matched to the query, so they contain relevant information even though the full text isn't shown here. You can reference them confidently as containing information related to the query.
- For media sources (images, videos, audio), reference them by filename and type
- If you need more specific details than what's provided, acknowledge the limitation
- Cite which sources you used (e.g., "According to Page 1 of document.pdf...")
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
            # Convert to int (S3 Vectors stores metadata as strings)
            start_char = int(start_char)
            end_char = int(end_char)
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


def prepare_multimodal_content(query: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Prepare multimodal content blocks for Claude
    
    Fetches actual media content (images, PDFs) and formats as base64
    Returns array of content blocks (images + text)
    """
    content_blocks = []
    text_context_parts = []
    
    for i, source in enumerate(sources, 1):
        metadata = source.get('metadata', {})
        filename = metadata.get('fileName', 'Unknown')
        modality = metadata.get('modalityType', 'Unknown')
        source_uri = metadata.get('sourceS3Uri', '')
        
        # For images (including PDF pages), fetch and encode
        if modality == 'IMAGE':
            is_pdf_str = metadata.get('isPdf', 'False')
            is_pdf = str(is_pdf_str).lower() == 'true'
            page_num = metadata.get('processedPage')
            if page_num is not None:
                page_num = int(page_num)
            
            # Fetch image from S3
            image_data = fetch_image_from_s3(source_uri)
            
            if image_data:
                # Base64 encode
                image_b64 = base64.b64encode(image_data).decode('utf-8')
                
                # Determine media type from source URI
                media_type = 'image/png' if source_uri.endswith('.png') else 'image/jpeg'
                
                # Add image block
                content_blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_b64
                    }
                })
                
                # Add text description
                if is_pdf and page_num:
                    text_context_parts.append(f"Image {len(content_blocks)}: Page {page_num} from {filename}")
                else:
                    text_context_parts.append(f"Image {len(content_blocks)}: {filename}")
            else:
                print(f"Warning: Could not fetch image from {source_uri}")
        
        # For text, include actual content
        elif modality == 'TEXT':
            content = get_text_content(source_uri, metadata)
            if content:
                text_context_parts.append(f"Text Source - {filename}:\n{content}")
        
        # For video/audio, include metadata
        elif modality in ['VIDEO', 'AUDIO']:
            segment_idx = int(metadata.get('segmentIndex', 0))
            start_time = float(metadata.get('segmentStartSeconds', 0))
            end_time = float(metadata.get('segmentEndSeconds', 0))
            text_context_parts.append(
                f"{modality} Source - {filename} (segment {segment_idx}: {start_time:.1f}s - {end_time:.1f}s)"
            )
    
    # Build final text prompt
    context_text = "\n\n".join(text_context_parts) if text_context_parts else "No additional context"
    
    prompt_text = f"""You are a helpful assistant answering questions based on a multimodal knowledge base.

The images above show relevant content from the knowledge base. Additional context:
{context_text}

User Question: {query}

Instructions:
- Analyze the images carefully and extract all relevant information
- For PDF pages, read any text visible in the images
- Combine information from all sources to provide a comprehensive answer
- Cite which sources you used (e.g., "According to Page 3 of document.pdf...")
- Be specific and detailed based on what you can see in the images
- If you need more information than what's provided, acknowledge the limitation

Answer:"""
    
    # Add text prompt at the end
    content_blocks.append({
        "type": "text",
        "text": prompt_text
    })
    
    return content_blocks


def fetch_image_from_s3(source_uri: str) -> bytes:
    """
    Fetch image from S3 and return as bytes
    
    Args:
        source_uri: S3 URI (s3://bucket/key)
    
    Returns:
        Image bytes, or None if fetch fails
    """
    if not source_uri or not source_uri.startswith('s3://'):
        return None
    
    try:
        # Parse S3 URI
        parts = source_uri.replace('s3://', '').split('/', 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ''
        
        # Download image
        response = s3_client.get_object(Bucket=bucket, Key=key)
        image_data = response['Body'].read()
        
        # Check size (Claude has 5MB limit per image)
        size_mb = len(image_data) / (1024 * 1024)
        if size_mb > 5:
            print(f"Warning: Image {source_uri} is {size_mb:.2f}MB, exceeds 5MB limit")
            return None
        
        print(f"Fetched image from {source_uri} ({size_mb:.2f}MB)")
        return image_data
        
    except Exception as e:
        print(f"Error fetching image from {source_uri}: {e}")
        return None


def call_claude_multimodal(content_blocks: List[Dict[str, Any]]) -> str:
    """
    Call Claude with multimodal content (images + text)
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
                "content": content_blocks  # Array of image and text blocks
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
    
    Shows original filename and relevant location info (page, timestamp, etc.)
    
    Returns format expected by ChatWindow.tsx:
    [
        {
            "key": "document.pdf",
            "similarity": 0.95,
            "text_preview": "Page 3"
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
        
        # Build location info based on content type
        location_info = []
        
        # For PDFs (processed as images), show page number
        is_pdf_str = metadata.get('isPdf', 'False')
        is_pdf = str(is_pdf_str).lower() == 'true'
        if is_pdf or (modality == 'IMAGE' and 'processedPage' in metadata):
            page = metadata.get('processedPage')
            if page is not None:
                page = int(page)
                location_info.append(f"Page {page}")
        
        # For video/audio, show timestamp
        elif modality in ['VIDEO', 'AUDIO'] and 'segmentStartSeconds' in metadata:
            start = float(metadata['segmentStartSeconds'])
            end = float(metadata.get('segmentEndSeconds', start))
            # Format as MM:SS
            start_min = int(start // 60)
            start_sec = int(start % 60)
            end_min = int(end // 60)
            end_sec = int(end % 60)
            location_info.append(f"{start_min}:{start_sec:02d}-{end_min}:{end_sec:02d}")
        
        # For text files, show character range if available
        elif modality == 'TEXT' and 'segmentStartCharPosition' in metadata:
            start = int(metadata['segmentStartCharPosition'])
            end = int(metadata.get('segmentEndCharPosition', start))
            # Show as approximate line numbers (assuming ~80 chars per line)
            start_line = start // 80 + 1
            end_line = end // 80 + 1
            if start_line == end_line:
                location_info.append(f"~Line {start_line}")
            else:
                location_info.append(f"~Lines {start_line}-{end_line}")
        
        # Build preview text
        if location_info:
            preview = " | ".join(location_info)
        else:
            # Fallback: just show modality type
            preview = modality
        
        formatted.append({
            'key': filename,
            'similarity': similarity,
            'text_preview': preview
        })
    
    return formatted


def create_no_results_response(query: str, total_sources: int) -> str:
    """
    Create a helpful response when no relevant sources are found
    
    Args:
        query: The user's query
        total_sources: Total number of sources found (before filtering)
    
    Returns:
        Helpful message with suggestions
    """
    if total_sources == 0:
        # No sources found at all
        return """I couldn't find any information in the knowledge base to answer that question.

The knowledge base appears to be empty or your query didn't match any indexed content.

Try:
• Checking if files have been uploaded to the S3 bucket
• Waiting a few minutes if files were just uploaded (processing takes 2-5 minutes)
• Verifying the embedder pipeline completed successfully"""
    
    else:
        # Sources found but below similarity threshold
        return f"""I couldn't find relevant information in the knowledge base to answer that question.

I found {total_sources} potential matches, but none were similar enough to your query (below 60% similarity threshold).

Try:
• Using different keywords or phrasing
• Being more specific about what you're looking for
• Asking about content you know exists in the uploaded files
• Checking if the right files have been uploaded"""


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
