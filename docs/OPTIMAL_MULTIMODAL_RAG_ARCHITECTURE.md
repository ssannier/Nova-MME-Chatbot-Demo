# Optimal Multimodal RAG Architecture with Nova MME

## Design Goals

**Highest fidelity context delivery:**
1. Preserve original content format (images stay images, video stays video)
2. Return exact segments found through semantic search
3. Pass native formats to LLM when possible
4. Minimize information loss in the pipeline

## Optimal Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    INGESTION PIPELINE                            │
└─────────────────────────────────────────────────────────────────┘

Original Content
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ Smart Content Processor                                          │
│                                                                  │
│ For each content type:                                          │
│ • Images → Store original + embed                               │
│ • Video → Extract keyframes + store original + embed segments   │
│ • Audio → Transcribe + store original + embed segments          │
│ • PDFs → Extract images per page + extract text + embed both    │
│ • .docx → Extract images + extract text + embed both            │
│ • Text → Store original + embed                                 │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ Dual Storage Strategy                                            │
│                                                                  │
│ 1. Original Content Store (S3)                                  │
│    • Full fidelity originals                                    │
│    • Extracted components (keyframes, pages, etc.)              │
│    • Fast retrieval by ID                                       │
│                                                                  │
│ 2. Vector Store (OpenSearch Serverless)                         │
│    • Embeddings at multiple dimensions (MRL)                    │
│    • Rich metadata with pointers to originals                   │
│    • Hybrid search (vector + keyword)                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    QUERY PIPELINE                                │
└─────────────────────────────────────────────────────────────────┘

User Query
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ Query Understanding                                              │
│ • Embed query with Nova MME                                     │
│ • Detect modality preference (if any)                           │
│ • Extract keywords for hybrid search                            │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ Hierarchical Semantic Search                                     │
│                                                                  │
│ Stage 1: Fast Coarse Search (256d)                              │
│ • Search across all content types                               │
│ • Top 100 candidates                                            │
│ • ~10ms latency                                                 │
│                                                                  │
│ Stage 2: Precise Refinement (1024d)                             │
│ • Rerank top 100 candidates                                     │
│ • Top 20 results                                                │
│ • ~30ms latency                                                 │
│                                                                  │
│ Stage 3: Diversity & Relevance Filtering                        │
│ • Ensure modality diversity                                     │
│ • Apply similarity threshold (>70%)                             │
│ • Deduplicate similar chunks                                    │
│ • Final top 5-10 results                                        │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ High-Fidelity Content Retrieval                                  │
│                                                                  │
│ For each result, fetch original content:                        │
│                                                                  │
│ • Images → Fetch original image from S3                         │
│ • Video → Fetch keyframe + timestamp range                      │
│ • Audio → Fetch transcript segment + timestamp                  │
│ • PDF → Fetch specific page image                               │
│ • .docx → Fetch extracted page image OR text                    │
│ • Text → Fetch exact character range                            │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ Intelligent Context Assembly                                     │
│                                                                  │
│ Build multimodal prompt for Claude:                             │
│                                                                  │
│ [Image 1: diagram.png]                                          │
│ [Image 2: Page 3 from report.pdf]                               │
│ [Video keyframe: presentation.mp4 at 1:23]                      │
│ [Text: From notes.txt, lines 45-67]                             │
│ [Audio transcript: meeting.mp3, 2:15-2:45]                      │
│                                                                  │
│ User Question: [query]                                          │
│                                                                  │
│ Constraints:                                                     │
│ • Max 5 images (Claude limit: 20, but 5 is optimal)            │
│ • Max 10,000 tokens of text                                     │
│ • Prioritize by relevance score                                 │
└─────────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ Claude Multimodal Generation                                     │
│ • Analyzes all images                                           │
│ • Reads all text                                                │
│ • Synthesizes comprehensive answer                              │
│ • Cites specific sources                                        │
└─────────────────────────────────────────────────────────────────┘
    ↓
Response with Citations
```

## Detailed Component Design

### 1. Smart Content Processor

**Goal:** Extract maximum information while preserving originals

#### For Images (JPG, PNG, GIF, WebP)

```python
def process_image(image_path: str) -> ProcessedContent:
    """
    Process image for optimal retrieval
    """
    # Store original
    original_uri = upload_to_s3(image_path, "originals/images/")
    
    # Embed with Nova MME at max dimension
    embedding = nova_mme_embed(
        image_uri=original_uri,
        dimension=3072,
        detail_level="DOCUMENT_IMAGE"  # Best for diagrams/text
    )
    
    # Optional: Extract text with OCR for hybrid search
    text_content = extract_text_from_image(image_path)  # Textract or Tesseract
    
    return ProcessedContent(
        original_uri=original_uri,
        embedding=embedding,
        modality="IMAGE",
        text_content=text_content,  # For keyword search
        metadata={
            "format": "png",
            "dimensions": "1920x1080",
            "file_size": 245678
        }
    )
```

#### For Videos (MP4, MOV, etc.)

```python
def process_video(video_path: str) -> List[ProcessedContent]:
    """
    Process video with keyframe extraction
    """
    # Store original
    original_uri = upload_to_s3(video_path, "originals/videos/")
    
    # Extract keyframes (1 per 5 seconds)
    keyframes = extract_keyframes(video_path, interval=5)
    
    # Transcribe audio
    transcript = transcribe_audio(video_path)  # AWS Transcribe
    
    segments = []
    for i, keyframe in enumerate(keyframes):
        start_time = i * 5
        end_time = (i + 1) * 5
        
        # Upload keyframe
        keyframe_uri = upload_to_s3(keyframe, f"keyframes/{video_id}/frame_{i}.jpg")
        
        # Embed keyframe + audio segment together
        embedding = nova_mme_embed(
            video_uri=original_uri,
            start_time=start_time,
            end_time=end_time,
            dimension=3072,
            embedding_mode="AUDIO_VIDEO_COMBINED"
        )
        
        # Get transcript segment
        transcript_segment = get_transcript_segment(transcript, start_time, end_time)
        
        segments.append(ProcessedContent(
            original_uri=original_uri,
            keyframe_uri=keyframe_uri,
            embedding=embedding,
            modality="VIDEO",
            text_content=transcript_segment,  # For keyword search
            metadata={
                "segment_index": i,
                "start_time": start_time,
                "end_time": end_time,
                "duration": 5,
                "has_audio": True
            }
        ))
    
    return segments
```

#### For Audio (MP3, WAV, OGG)

```python
def process_audio(audio_path: str) -> List[ProcessedContent]:
    """
    Process audio with transcription
    """
    # Store original
    original_uri = upload_to_s3(audio_path, "originals/audio/")
    
    # Transcribe with timestamps
    transcript = transcribe_audio_with_timestamps(audio_path)  # AWS Transcribe
    
    # Segment by 30-second chunks
    segments = []
    for i, segment in enumerate(chunk_transcript(transcript, duration=30)):
        # Embed audio segment
        embedding = nova_mme_embed(
            audio_uri=original_uri,
            start_time=segment.start_time,
            end_time=segment.end_time,
            dimension=3072
        )
        
        segments.append(ProcessedContent(
            original_uri=original_uri,
            embedding=embedding,
            modality="AUDIO",
            text_content=segment.text,  # Full transcript segment
            metadata={
                "segment_index": i,
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "speaker": segment.speaker,  # If diarization enabled
                "confidence": segment.confidence
            }
        ))
    
    return segments
```

#### For PDFs (Optimal Approach)

```python
def process_pdf(pdf_path: str) -> List[ProcessedContent]:
    """
    Process PDF with dual embedding strategy
    """
    # Store original
    original_uri = upload_to_s3(pdf_path, "originals/pdfs/")
    
    pages = []
    for page_num, page in enumerate(extract_pdf_pages(pdf_path), start=1):
        # Convert page to high-res image
        page_image = render_page_to_image(page, dpi=300)
        page_image_uri = upload_to_s3(page_image, f"pdf-pages/{pdf_id}/page_{page_num}.png")
        
        # Extract text from page
        page_text = extract_text_from_page(page)
        
        # Embed page image (visual understanding)
        image_embedding = nova_mme_embed(
            image_uri=page_image_uri,
            dimension=3072,
            detail_level="DOCUMENT_IMAGE"
        )
        
        # Embed page text (semantic understanding)
        text_embedding = nova_mme_embed(
            text=page_text,
            dimension=3072
        )
        
        # Store BOTH embeddings for hybrid retrieval
        pages.append(ProcessedContent(
            original_uri=original_uri,
            page_image_uri=page_image_uri,
            image_embedding=image_embedding,
            text_embedding=text_embedding,
            modality="PDF",
            text_content=page_text,
            metadata={
                "page_number": page_num,
                "total_pages": len(pdf_pages),
                "has_images": detect_images_in_page(page),
                "has_tables": detect_tables_in_page(page)
            }
        ))
    
    return pages
```

#### For .docx (Optimal Approach)

```python
def process_docx(docx_path: str) -> List[ProcessedContent]:
    """
    Process .docx with image extraction + text
    """
    # Store original
    original_uri = upload_to_s3(docx_path, "originals/docs/")
    
    # Convert to PDF first (preserves layout)
    pdf_path = convert_docx_to_pdf(docx_path)  # LibreOffice
    
    # Then process as PDF (reuse PDF pipeline)
    return process_pdf(pdf_path)
```

### 2. Vector Store Design (OpenSearch Serverless)

**Why OpenSearch over S3 Vectors:**
- Hybrid search (vector + keyword)
- Rich filtering capabilities
- Proven at scale
- Better query performance

**Index Schema:**

```json
{
  "mappings": {
    "properties": {
      "content_id": {"type": "keyword"},
      "modality": {"type": "keyword"},
      "original_uri": {"type": "keyword"},
      "display_uri": {"type": "keyword"},
      
      "embedding_256d": {
        "type": "knn_vector",
        "dimension": 256,
        "method": {
          "name": "hnsw",
          "engine": "faiss"
        }
      },
      "embedding_1024d": {
        "type": "knn_vector",
        "dimension": 1024,
        "method": {
          "name": "hnsw",
          "engine": "faiss"
        }
      },
      "embedding_3072d": {
        "type": "knn_vector",
        "dimension": 3072,
        "method": {
          "name": "hnsw",
          "engine": "faiss"
        }
      },
      
      "text_content": {
        "type": "text",
        "analyzer": "standard"
      },
      
      "metadata": {
        "type": "object",
        "properties": {
          "page_number": {"type": "integer"},
          "start_time": {"type": "float"},
          "end_time": {"type": "float"},
          "file_name": {"type": "keyword"},
          "created_date": {"type": "date"}
        }
      },
      
      "created_at": {"type": "date"},
      "updated_at": {"type": "date"}
    }
  }
}
```

### 3. Hierarchical Search Implementation

```python
def hierarchical_search(query: str, k: int = 5) -> List[SearchResult]:
    """
    Multi-stage search for optimal speed/accuracy
    """
    # Embed query at max dimension
    query_embedding_3072 = nova_mme_embed(query, dimension=3072)
    
    # Stage 1: Fast coarse search (256d)
    query_embedding_256 = truncate_and_normalize(query_embedding_3072, 256)
    
    coarse_results = opensearch.search(
        index="content",
        body={
            "size": 100,
            "query": {
                "knn": {
                    "embedding_256d": {
                        "vector": query_embedding_256,
                        "k": 100
                    }
                }
            }
        }
    )
    
    # Stage 2: Precise refinement (1024d)
    query_embedding_1024 = truncate_and_normalize(query_embedding_3072, 1024)
    
    candidate_ids = [hit["_id"] for hit in coarse_results["hits"]["hits"]]
    
    refined_results = opensearch.search(
        index="content",
        body={
            "size": 20,
            "query": {
                "bool": {
                    "must": [
                        {
                            "knn": {
                                "embedding_1024d": {
                                    "vector": query_embedding_1024,
                                    "k": 20
                                }
                            }
                        },
                        {
                            "ids": {
                                "values": candidate_ids
                            }
                        }
                    ]
                }
            }
        }
    )
    
    # Stage 3: Diversity & filtering
    final_results = apply_diversity_filter(
        refined_results,
        similarity_threshold=0.70,
        max_per_modality=3,
        max_results=k
    )
    
    return final_results
```

### 4. High-Fidelity Content Retrieval

```python
def retrieve_content_for_llm(search_results: List[SearchResult]) -> MultimodalContext:
    """
    Fetch original content in highest fidelity
    """
    images = []
    text_segments = []
    video_keyframes = []
    audio_transcripts = []
    
    for result in search_results:
        modality = result.metadata["modality"]
        
        if modality == "IMAGE":
            # Fetch original image
            image_data = s3_client.get_object(
                Bucket=bucket,
                Key=result.original_uri
            )
            images.append({
                "data": image_data,
                "filename": result.metadata["file_name"],
                "similarity": result.score
            })
        
        elif modality == "VIDEO":
            # Fetch keyframe for visual context
            keyframe_data = s3_client.get_object(
                Bucket=bucket,
                Key=result.keyframe_uri
            )
            video_keyframes.append({
                "data": keyframe_data,
                "filename": result.metadata["file_name"],
                "timestamp": f"{result.metadata['start_time']}-{result.metadata['end_time']}",
                "transcript": result.text_content,
                "similarity": result.score
            })
        
        elif modality == "AUDIO":
            # Fetch transcript segment
            audio_transcripts.append({
                "filename": result.metadata["file_name"],
                "timestamp": f"{result.metadata['start_time']}-{result.metadata['end_time']}",
                "transcript": result.text_content,
                "speaker": result.metadata.get("speaker"),
                "similarity": result.score
            })
        
        elif modality == "PDF":
            # Fetch page image (visual) + text (searchable)
            page_image_data = s3_client.get_object(
                Bucket=bucket,
                Key=result.page_image_uri
            )
            images.append({
                "data": page_image_data,
                "filename": f"{result.metadata['file_name']} (Page {result.metadata['page_number']})",
                "text_content": result.text_content,
                "similarity": result.score
            })
        
        elif modality == "TEXT":
            # Fetch exact text segment
            text_segments.append({
                "filename": result.metadata["file_name"],
                "content": result.text_content,
                "similarity": result.score
            })
    
    return MultimodalContext(
        images=images[:5],  # Claude limit
        video_keyframes=video_keyframes[:3],
        audio_transcripts=audio_transcripts[:3],
        text_segments=text_segments[:5]
    )
```

### 5. Intelligent Context Assembly

```python
def assemble_claude_prompt(query: str, context: MultimodalContext) -> List[Dict]:
    """
    Build optimal multimodal prompt for Claude
    """
    content_blocks = []
    context_descriptions = []
    
    # Add images (including PDF pages and video keyframes)
    for i, image in enumerate(context.images, 1):
        content_blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.b64encode(image["data"]).decode()
            }
        })
        context_descriptions.append(
            f"Image {i}: {image['filename']} (relevance: {image['similarity']:.0%})"
        )
    
    # Add video keyframes as images
    for i, keyframe in enumerate(context.video_keyframes, len(context.images) + 1):
        content_blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.b64encode(keyframe["data"]).decode()
            }
        })
        context_descriptions.append(
            f"Image {i}: Video frame from {keyframe['filename']} at {keyframe['timestamp']}"
        )
        context_descriptions.append(
            f"  Transcript: {keyframe['transcript']}"
        )
    
    # Build text context
    text_context_parts = []
    
    # Add text segments
    for segment in context.text_segments:
        text_context_parts.append(
            f"Text from {segment['filename']}:\n{segment['content']}"
        )
    
    # Add audio transcripts
    for transcript in context.audio_transcripts:
        speaker_info = f" ({transcript['speaker']})" if transcript.get('speaker') else ""
        text_context_parts.append(
            f"Audio from {transcript['filename']} at {transcript['timestamp']}{speaker_info}:\n{transcript['transcript']}"
        )
    
    # Combine everything into final prompt
    prompt_text = f"""You are a helpful assistant with access to a multimodal knowledge base.

The images above show relevant visual content. Additional context:

{chr(10).join(context_descriptions)}

Text and audio content:
{chr(10).join(text_context_parts)}

User Question: {query}

Instructions:
- Analyze all images carefully
- Read all text and transcripts
- Synthesize information from all sources
- Cite specific sources in your answer (e.g., "According to Image 2..." or "In the transcript from meeting.mp3...")
- Be specific about what you see in images
- If information is incomplete, acknowledge it

Answer:"""
    
    content_blocks.append({
        "type": "text",
        "text": prompt_text
    })
    
    return content_blocks
```

## Advanced Features

### 1. Hybrid Search (Vector + Keyword)

```python
def hybrid_search(query: str, k: int = 5) -> List[SearchResult]:
    """
    Combine semantic and keyword search
    """
    # Semantic search
    semantic_results = hierarchical_search(query, k=k*2)
    
    # Keyword search
    keyword_results = opensearch.search(
        index="content",
        body={
            "size": k*2,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["text_content^2", "metadata.file_name"],
                    "type": "best_fields"
                }
            }
        }
    )
    
    # Merge and rerank using Reciprocal Rank Fusion
    merged_results = reciprocal_rank_fusion(
        [semantic_results, keyword_results],
        k=k
    )
    
    return merged_results
```

### 2. Temporal Awareness

```python
def temporal_search(query: str, time_range: Optional[DateRange] = None) -> List[SearchResult]:
    """
    Search with temporal filtering
    """
    filters = []
    
    if time_range:
        filters.append({
            "range": {
                "metadata.created_date": {
                    "gte": time_range.start,
                    "lte": time_range.end
                }
            }
        })
    
    # Boost recent content
    return opensearch.search(
        index="content",
        body={
            "query": {
                "function_score": {
                    "query": {
                        "bool": {
                            "must": [knn_query],
                            "filter": filters
                        }
                    },
                    "functions": [
                        {
                            "gauss": {
                                "metadata.created_date": {
                                    "origin": "now",
                                    "scale": "30d",
                                    "decay": 0.5
                                }
                            }
                        }
                    ]
                }
            }
        }
    )
```

### 3. Modality-Specific Routing

```python
def smart_search(query: str, k: int = 5) -> List[SearchResult]:
    """
    Route query to optimal modality based on query type
    """
    # Detect query intent
    query_type = classify_query(query)  # "visual", "audio", "text", "mixed"
    
    if query_type == "visual":
        # Prioritize images and video
        return search_with_modality_boost(
            query,
            modality_weights={"IMAGE": 2.0, "VIDEO": 2.0, "PDF": 1.5}
        )
    
    elif query_type == "audio":
        # Prioritize audio and video
        return search_with_modality_boost(
            query,
            modality_weights={"AUDIO": 2.0, "VIDEO": 1.5}
        )
    
    else:
        # Balanced search across all modalities
        return hierarchical_search(query, k=k)
```

### 4. Caching Layer

```python
class ContentCache:
    """
    Cache frequently accessed content
    """
    def __init__(self):
        self.redis_client = redis.Redis()
        self.ttl = 3600  # 1 hour
    
    def get_content(self, content_id: str) -> Optional[bytes]:
        """Get from cache or S3"""
        # Try cache first
        cached = self.redis_client.get(f"content:{content_id}")
        if cached:
            return cached
        
        # Fetch from S3
        content = s3_client.get_object(Bucket=bucket, Key=content_id)
        
        # Cache for future requests
        self.redis_client.setex(
            f"content:{content_id}",
            self.ttl,
            content
        )
        
        return content
```

## Cost Optimization

### 1. Dimension Selection Strategy

```python
def select_optimal_dimension(query_complexity: str, latency_requirement: str) -> int:
    """
    Choose dimension based on requirements
    """
    if latency_requirement == "realtime" and query_complexity == "simple":
        return 256  # Fast, good enough for simple queries
    
    elif latency_requirement == "realtime":
        return 1024  # Balanced
    
    elif query_complexity == "complex":
        return 3072  # Maximum accuracy
    
    else:
        return 1024  # Default sweet spot
```

### 2. Lazy Loading

```python
def lazy_load_content(search_results: List[SearchResult]) -> Iterator[Content]:
    """
    Load content on-demand as needed
    """
    for result in search_results:
        # Only load if similarity is high enough
        if result.score > 0.75:
            yield load_content(result)
        else:
            # Return metadata only for low-relevance results
            yield result.metadata
```

## Performance Characteristics

### Latency Breakdown (Optimized)

```
Query embedding:           ~200ms
Hierarchical search:       ~40ms (256d + 1024d)
Content retrieval:         ~150ms (parallel, cached)
Claude processing:         ~3000ms
────────────────────────────────
Total:                     ~3.4 seconds
```

### Throughput

- **Concurrent queries:** 100+ QPS (with caching)
- **Index size:** Millions of documents
- **Search latency:** <50ms (vector search only)

## Technology Stack Recommendation

### Core Services

1. **Embedding:** Amazon Bedrock (Nova MME)
2. **Vector Store:** Amazon OpenSearch Serverless
3. **Object Storage:** Amazon S3 (with CloudFront CDN)
4. **LLM:** Amazon Bedrock (Claude 3.5 Sonnet)
5. **Transcription:** Amazon Transcribe
6. **OCR:** Amazon Textract
7. **Caching:** Amazon ElastiCache (Redis)
8. **Orchestration:** AWS Step Functions
9. **Compute:** AWS Lambda (for processing)
10. **API:** Amazon API Gateway

### Why This Stack?

- ✅ Fully managed (minimal ops)
- ✅ Scales automatically
- ✅ Pay-per-use pricing
- ✅ Native AWS integration
- ✅ Enterprise-grade security
- ✅ Global availability

## Summary: Key Principles

### 1. Preserve Originals
**Always store original content** - Never rely solely on extracted/processed versions

### 2. Dual Embedding Strategy
**For documents:** Embed both visual (images) and textual representations

### 3. Hierarchical Search
**Use MRL effectively:** Fast coarse search → Precise refinement

### 4. High-Fidelity Retrieval
**Pass native formats to LLM:** Images as images, not descriptions

### 5. Intelligent Assembly
**Optimize context:** Right mix of modalities, prioritized by relevance

### 6. Hybrid Approach
**Combine semantic + keyword:** Better recall and precision

### 7. Cache Aggressively
**Reduce latency:** Cache embeddings, content, and search results

### 8. Monitor & Optimize
**Track metrics:** Latency, relevance, cost per query

## Comparison: Current Demo vs Optimal

| Aspect | Current Demo | Optimal Production |
|--------|--------------|-------------------|
| **Vector Store** | S3 Vectors | OpenSearch Serverless |
| **PDF Handling** | Images only | Images + Text (dual) |
| **Video** | Metadata only | Keyframes + Transcripts |
| **Audio** | Metadata only | Full transcripts |
| **Search** | Vector only | Hybrid (vector + keyword) |
| **Caching** | None | Redis (multi-layer) |
| **Dimensions** | All 4 stored | Dynamic selection |
| **Cost** | ~$50/month | ~$500-1000/month |
| **Latency** | ~3.5s | ~3.4s (optimized) |
| **Accuracy** | Good | Excellent |

## Conclusion

The optimal architecture balances:
- **Fidelity:** Preserve and pass original content
- **Performance:** Hierarchical search with caching
- **Cost:** Smart dimension selection and lazy loading
- **Scalability:** Fully managed services
- **Flexibility:** Hybrid search and modality routing

**The key insight:** Nova MME's multimodal capabilities are most powerful when you preserve the original modality of content and pass it to Claude in its native format, rather than converting everything to text.
