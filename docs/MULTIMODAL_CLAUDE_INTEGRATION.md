# Multimodal Claude Integration

## Overview

The Nova MME chatbot now passes actual multimodal content (images, PDF pages) to Claude for analysis, enabling Claude to read and understand visual content directly rather than relying solely on metadata.

## Architecture

### Content Flow

```
User Query
    ↓
Nova MME Embedding (query)
    ↓
S3 Vectors Search (semantic similarity)
    ↓
Content Retrieval:
  - TEXT: Fetch actual text from S3
  - IMAGE/PDF: Fetch image bytes from S3, base64 encode
  - VIDEO/AUDIO: Include metadata (future: keyframes/transcripts)
    ↓
Multimodal Content Blocks:
  [Image Block 1, Image Block 2, ..., Text Block with context]
    ↓
Claude Multimodal API
    ↓
Generated Answer
```

## Implementation Details

### Key Functions

#### `fetch_image_from_s3(source_uri: str) -> bytes`

Retrieves image data from S3 for multimodal processing.

**Features:**
- Parses S3 URI (s3://bucket/key)
- Downloads image bytes
- Validates size (5MB limit per Claude's requirements)
- Returns None on error (graceful degradation)

**Example:**
```python
image_data = fetch_image_from_s3('s3://bucket/pdf-pages/doc_page_1.png')
if image_data:
    image_b64 = base64.b64encode(image_data).decode('utf-8')
```

#### `prepare_multimodal_content(query: str, sources: List[Dict]) -> List[Dict]`

Prepares content blocks for Claude's multimodal API.

**Content Block Types:**

1. **Image Blocks** (for IMAGE modality):
```python
{
    "type": "image",
    "source": {
        "type": "base64",
        "media_type": "image/jpeg",  # or image/png
        "data": "base64encodeddata..."
    }
}
```

2. **Text Block** (always last):
```python
{
    "type": "text",
    "text": "Context + User Question + Instructions"
}
```

**Processing by Modality:**

- **IMAGE (including PDF pages)**: Fetch from S3, base64 encode, add image block
- **TEXT**: Fetch content from S3, include in text context
- **VIDEO/AUDIO**: Include metadata in text context (timestamps, segment info)

#### `call_claude_multimodal(content_blocks: List[Dict]) -> str`

Invokes Claude with multimodal content.

**API Structure:**
```python
{
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 2048,
    "temperature": 0.7,
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "image", "source": {...}},
                {"type": "image", "source": {...}},
                {"type": "text", "text": "..."}
            ]
        }
    ]
}
```

## Image Processing

### Regular Images (JPG, PNG, GIF, WebP)

1. **Embedder Pipeline** (Lambda 1 → 3):
   - Image uploaded to S3 source bucket
   - Nova MME embeds with `DOCUMENT_IMAGE` detail level
   - Metadata includes `modalityType: 'IMAGE'`
   - Stored in S3 Vector indexes at all 4 dimensions

2. **Query Handler** (Lambda 4):
   - Semantic search finds relevant images
   - Fetches image from original S3 location
   - Passes image to Claude for analysis
   - Claude analyzes visual content, reads text in images

### Metadata for Regular Images

```python
{
    'fileName': 'diagram.png',
    'modalityType': 'IMAGE',
    'sourceS3Uri': 's3://bucket/diagram.png',
    'fileType': '.png',
    'fileSize': 245678,
    'contentType': 'image/png'
}
```

## PDF Integration

### PDF Processing Pipeline

1. **Embedder Pipeline** (Lambda 1 → 3):
   - PDF uploaded to S3 source bucket
   - Lambda 1 converts PDF to images (PyMuPDF)
   - Stores images in `pdf-pages/` prefix
   - Nova MME embeds with `DOCUMENT_IMAGE` detail level
   - Metadata includes `isPdf: true` and `processedPage: N`

2. **Query Handler** (Lambda 4):
   - Semantic search finds relevant PDF pages
   - Fetches page images from S3
   - Passes images to Claude for analysis
   - Claude reads text and understands visual content

### Metadata for PDF Pages

```python
{
    'fileName': 'document.pdf',
    'modalityType': 'IMAGE',
    'sourceS3Uri': 's3://bucket/pdf-pages/document_pdf_page_1.png',
    'isPdf': True,
    'processedPage': 1,
    'totalPages': 10,
    'originalPdfUri': 's3://bucket/document.pdf'
}
```

## Claude Prompt Structure

### Multimodal Prompt Template

```
You are a helpful assistant answering questions based on a multimodal knowledge base.

The images above show relevant content from the knowledge base. Additional context:
Image 1: diagram.png
Image 2: Page 1 from document.pdf
Image 3: Page 3 from document.pdf
Text Source - notes.txt:
[actual text content here]
VIDEO Source - presentation.mp4 (segment 0: 0.0s - 5.0s)

User Question: [user's question]

Instructions:
- Analyze the images carefully and extract all relevant information
- For regular images, describe what you see and read any text present
- For PDF pages, read any text visible in the images
- Combine information from all sources to provide a comprehensive answer
- Cite which sources you used (e.g., "According to diagram.png..." or "According to Page 3 of document.pdf...")
- Be specific and detailed based on what you can see in the images
- If you need more information than what's provided, acknowledge the limitation

Answer:
```

## Size Limits and Constraints

### Claude Multimodal Limits

- **Max image size**: 5MB per image
- **Max images per request**: 20 images (Claude 3.5 Sonnet)
- **Supported formats**: JPEG, PNG, GIF, WebP

### Implementation Safeguards

1. **Size validation**: Reject images > 5MB
2. **Error handling**: Graceful degradation if image fetch fails
3. **Fallback**: Continue with text-only context if no images available

## Testing

### Test Coverage

27 tests covering multimodal functionality:

- `TestCallClaudeMultimodal`: Claude API invocation with content blocks
- `TestFetchImageFromS3`: Image retrieval, error handling, size validation
- `TestPrepareMultimodalContent`: Content block preparation, mixed modalities

### Running Tests

```bash
python -m pytest tests/unit/test_query_handler_lambda.py -v
```

All multimodal tests passing ✅

## Performance Considerations

### Latency

- **Image fetch**: ~50-200ms per image from S3
- **Base64 encoding**: ~10-50ms per image
- **Claude processing**: ~2-5 seconds (depends on image count and complexity)

### Optimization Strategies

1. **Parallel fetching**: Fetch multiple images concurrently (future enhancement)
2. **Caching**: Cache frequently accessed images (future enhancement)
3. **Lazy loading**: Only fetch images for top-K results
4. **Compression**: Use JPEG for photos, PNG for documents

## Future Enhancements

### Video/Audio Support

Currently, video and audio sources only include metadata. Future improvements:

1. **Keyframe extraction**: Extract representative frames from video
2. **Thumbnail generation**: Create visual previews
3. **Transcription**: Use AWS Transcribe for audio/video transcripts
4. **Scene detection**: Identify key moments in video content

### Advanced Features

1. **Image preprocessing**: Resize/compress images before sending to Claude
2. **OCR enhancement**: Pre-process low-quality scans
3. **Multi-page PDFs**: Intelligent page selection (most relevant pages only)
4. **Image caching**: CloudFront or Lambda@Edge for frequently accessed images

## Error Handling

### Graceful Degradation

The system handles errors at multiple levels:

1. **Image fetch failure**: Continue with text-only context
2. **Oversized images**: Skip and log warning
3. **Invalid S3 URIs**: Return None, continue processing
4. **Claude API errors**: Return error message to user

### Logging

All errors are logged to CloudWatch:

```python
print(f"Error fetching image from {source_uri}: {e}")
print(f"Warning: Image {source_uri} is {size_mb:.2f}MB, exceeds 5MB limit")
```

## Configuration

### Environment Variables

No additional environment variables needed. Uses existing:

- `LLM_MODEL_ID`: Claude model identifier
- `LLM_MAX_TOKENS`: Max tokens for response (default: 2048)
- `LLM_TEMPERATURE`: Temperature for generation (default: 0.7)

### IAM Permissions

Query Handler Lambda needs S3 read access:

```python
source_bucket.grant_read(query_handler_lambda)
vector_bucket.grant_read(query_handler_lambda)
```

Already configured in `lib/chatbot_stack.py` ✅

## Deployment

No additional deployment steps required. The multimodal functionality is included in the Query Handler Lambda.

To deploy:

```bash
cdk deploy NovaMMEChatbotStack
```

## Monitoring

### CloudWatch Metrics

Monitor these metrics:

- Lambda duration (increased with image processing)
- Lambda memory usage (base64 encoding uses memory)
- S3 GetObject requests (image fetches)
- Claude API latency

### CloudWatch Logs

Search for:

- `"Fetched image from"` - successful image retrieval
- `"Error fetching image"` - image fetch failures
- `"exceeds 5MB limit"` - oversized images

## Supported Content Types

### Fully Multimodal (Passed to Claude)
- ✅ **Regular Images** (JPG, PNG, GIF, WebP) - Claude analyzes visual content
- ✅ **PDF Documents** - Converted to images, Claude reads text and diagrams
- ✅ **Text Files** (TXT, MD, JSON, CSV) - Actual content fetched and included in prompt

### Metadata Only (Future Enhancement)
- ⏳ **Video** (MP4, MOV, MKV, WebM, etc.) - Currently metadata only (timestamps, segments)
- ⏳ **Audio** (MP3, WAV, OGG) - Currently metadata only (timestamps, segments)

### Partially Supported
- ⚠️ **Word Documents** (.docx) - Text extraction only
  - **What works:** Plain text, paragraphs, tables (as text)
  - **What's lost:** Formatting, embedded images, diagrams
  - **Note:** .doc (old format) not supported - convert to .docx first
  - **Alternative:** Convert to PDF for full visual preservation

### Not Currently Supported
- ❌ **Old Word** (.doc) - Legacy format, convert to .docx or PDF
- ❌ **PowerPoint** (.ppt, .pptx) - Not yet implemented
- ❌ **Excel** (.xls, .xlsx) - Not yet implemented
- ❌ **Google Docs** (.gdoc) - Pointer file only, export to .docx first

## Summary

The multimodal Claude integration enables the chatbot to:

✅ Analyze regular images (diagrams, photos, screenshots)
✅ Read actual PDF content (not just metadata)
✅ Extract text from images using Claude's vision capabilities
✅ Combine visual and textual information
✅ Provide more accurate and detailed answers
✅ Handle errors gracefully with fallback to text-only mode

This significantly improves the quality of responses for document-heavy and image-rich knowledge bases.
