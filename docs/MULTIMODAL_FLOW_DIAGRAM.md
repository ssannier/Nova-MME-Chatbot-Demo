# Multimodal Content Flow

## Quick Reference: What Gets Passed to Claude?

| Content Type | Passed to Claude | Format | Notes |
|--------------|------------------|--------|-------|
| **Regular Images** (JPG, PNG, GIF, WebP) | ✅ Yes | Base64-encoded image | Claude analyzes visual content |
| **PDF Documents** | ✅ Yes | Base64-encoded page images | Converted to images, Claude reads text |
| **Text Files** (TXT, MD, JSON, CSV) | ✅ Yes | Raw text content | Included in text prompt |
| **Video Files** (MP4, MOV, etc.) | ⏳ Metadata only | Segment timestamps | Future: keyframes/transcripts |
| **Audio Files** (MP3, WAV, OGG) | ⏳ Metadata only | Segment timestamps | Future: transcripts |

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER UPLOADS FILE TO S3                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────────┐
         │   Lambda 1: Processor             │
         │   - Detects file type             │
         │   - PDFs → Convert to images      │
         │   - Images → Use directly         │
         │   - Invokes Nova MME async        │
         └───────────────┬───────────────────┘
                         │
                         ▼
         ┌───────────────────────────────────┐
         │   Nova MME (Bedrock)              │
         │   - Embeds at 3072 dimensions     │
         │   - DOCUMENT_IMAGE detail level   │
         │   - Automatic segmentation        │
         └───────────────┬───────────────────┘
                         │
                         ▼
         ┌───────────────────────────────────┐
         │   Lambda 3: Store Embeddings      │
         │   - MRL truncation (256/384/1024) │
         │   - Store in S3 Vector indexes    │
         │   - Preserve all metadata         │
         └───────────────────────────────────┘
                         │
                         │
         ┌───────────────▼───────────────────┐
         │      USER ASKS QUESTION            │
         └───────────────┬───────────────────┘
                         │
                         ▼
         ┌───────────────────────────────────┐
         │   Lambda 4: Query Handler         │
         │   Step 1: Embed query (Nova MME)  │
         └───────────────┬───────────────────┘
                         │
                         ▼
         ┌───────────────────────────────────┐
         │   Step 2: S3 Vectors Search       │
         │   - Semantic similarity search    │
         │   - Returns top-K matches         │
         │   - Includes metadata             │
         └───────────────┬───────────────────┘
                         │
                         ▼
         ┌───────────────────────────────────┐
         │   Step 3: Content Retrieval       │
         │                                   │
         │   For IMAGE modality:             │
         │   ├─ Fetch image from S3          │
         │   ├─ Base64 encode                │
         │   └─ Add to content blocks        │
         │                                   │
         │   For TEXT modality:              │
         │   ├─ Fetch text from S3           │
         │   └─ Add to text context          │
         │                                   │
         │   For VIDEO/AUDIO modality:       │
         │   └─ Add metadata to text context │
         └───────────────┬───────────────────┘
                         │
                         ▼
         ┌───────────────────────────────────┐
         │   Step 4: Format Multimodal       │
         │   Content Blocks:                 │
         │   [                               │
         │     {type: "image", data: "..."}  │
         │     {type: "image", data: "..."}  │
         │     {type: "text", text: "..."}   │
         │   ]                               │
         └───────────────┬───────────────────┘
                         │
                         ▼
         ┌───────────────────────────────────┐
         │   Step 5: Claude Multimodal API   │
         │   - Analyzes all images           │
         │   - Reads text in images          │
         │   - Combines with text context    │
         │   - Generates comprehensive answer│
         └───────────────┬───────────────────┘
                         │
                         ▼
         ┌───────────────────────────────────┐
         │   Step 6: Return to User          │
         │   - Answer with citations         │
         │   - Source list with similarity   │
         │   - Processing steps (transparent)│
         └───────────────────────────────────┘
```

## Example: User Uploads Architecture Diagram

### Upload Phase

```
1. User uploads "architecture.png" to S3 source bucket
   ↓
2. Lambda 1 detects IMAGE type
   ↓
3. Nova MME embeds with DOCUMENT_IMAGE detail level
   - Understands diagrams, text, relationships
   - Creates 3072-dim embedding
   ↓
4. Lambda 3 truncates to 256/384/1024/3072 dimensions
   ↓
5. Stored in all 4 S3 Vector indexes with metadata:
   {
     fileName: "architecture.png",
     modalityType: "IMAGE",
     sourceS3Uri: "s3://bucket/architecture.png",
     embeddingDimension: 1024
   }
```

### Query Phase

```
1. User asks: "What are the main components in the architecture?"
   ↓
2. Query embedded at 1024 dimensions
   ↓
3. S3 Vectors search finds "architecture.png" (95% similarity)
   ↓
4. Lambda fetches image from s3://bucket/architecture.png
   ↓
5. Image base64-encoded and passed to Claude:
   [
     {
       type: "image",
       source: {
         type: "base64",
         media_type: "image/png",
         data: "iVBORw0KGgoAAAANS..."
       }
     },
     {
       type: "text",
       text: "Image 1: architecture.png\n\nUser Question: What are..."
     }
   ]
   ↓
6. Claude analyzes the diagram and responds:
   "Based on the architecture diagram, the main components are:
    1. Frontend (Next.js)
    2. API Gateway
    3. Lambda Functions (4 total)
    4. S3 Buckets (source, vector, output)
    5. Bedrock (Nova MME, Claude)
    ..."
```

## Example: User Uploads PDF Document

### Upload Phase

```
1. User uploads "manual.pdf" (10 pages) to S3 source bucket
   ↓
2. Lambda 1 detects PDF type
   ↓
3. PyMuPDF converts to 10 PNG images
   - Stored in pdf-pages/ prefix
   - manual_pdf_page_1.png
   - manual_pdf_page_2.png
   - ...
   ↓
4. Nova MME embeds each page with DOCUMENT_IMAGE detail level
   - Each page gets its own embedding
   - Understands text, tables, diagrams
   ↓
5. Lambda 3 stores all pages in S3 Vector indexes with metadata:
   {
     fileName: "manual.pdf",
     modalityType: "IMAGE",
     sourceS3Uri: "s3://bucket/pdf-pages/manual_pdf_page_3.png",
     isPdf: true,
     processedPage: 3,
     totalPages: 10
   }
```

### Query Phase

```
1. User asks: "How do I configure the database connection?"
   ↓
2. Query embedded at 1024 dimensions
   ↓
3. S3 Vectors search finds:
   - Page 3 of manual.pdf (92% similarity)
   - Page 7 of manual.pdf (88% similarity)
   ↓
4. Lambda fetches both page images from S3
   ↓
5. Both images passed to Claude:
   [
     {type: "image", data: "...page 3..."},
     {type: "image", data: "...page 7..."},
     {type: "text", text: "Image 1: Page 3 from manual.pdf\n
                           Image 2: Page 7 from manual.pdf\n
                           User Question: How do I..."}
   ]
   ↓
6. Claude reads text from both pages and responds:
   "According to Page 3 of manual.pdf, to configure the database:
    1. Open config/database.json
    2. Set the connection string...
    
    Page 7 provides additional details about connection pooling..."
```

## Key Differences: Regular Images vs PDF Pages

| Aspect | Regular Images | PDF Pages |
|--------|---------------|-----------|
| **Storage** | Original location | `pdf-pages/` prefix |
| **Metadata** | `modalityType: 'IMAGE'` | `modalityType: 'IMAGE'` + `isPdf: true` |
| **Processing** | Direct embedding | Convert to images first |
| **Page Info** | N/A | `processedPage`, `totalPages` |
| **Claude Handling** | Analyze visual content | Read text + analyze layout |

## Performance Characteristics

### Latency Breakdown (per query)

```
Query Embedding:           ~200ms
S3 Vectors Search:         ~50ms
Image Fetch (per image):   ~100ms
Base64 Encoding:           ~20ms
Claude Processing:         ~3000ms (with 2 images)
────────────────────────────────────
Total (2 images):          ~3470ms
```

### Optimization Tips

1. **Limit images**: Top 3-5 most relevant images
2. **Compress images**: Use JPEG for photos, PNG for diagrams
3. **Parallel fetching**: Fetch multiple images concurrently (future)
4. **Caching**: Cache frequently accessed images (future)

## Error Handling

### Graceful Degradation

```
Image fetch fails
    ↓
Log warning
    ↓
Continue with other sources
    ↓
If no images available:
    ↓
Fall back to text-only mode
    ↓
Claude still generates answer
```

### Size Validation

```
Image > 5MB
    ↓
Log warning
    ↓
Skip image
    ↓
Continue with other sources
```

## Testing

Run multimodal tests:

```bash
# Test all multimodal functionality
python -m pytest tests/unit/test_query_handler_lambda.py::TestPrepareMultimodalContent -v

# Test image fetching
python -m pytest tests/unit/test_query_handler_lambda.py::TestFetchImageFromS3 -v

# Test Claude multimodal API
python -m pytest tests/unit/test_query_handler_lambda.py::TestCallClaudeMultimodal -v
```

All 29 tests passing ✅

## Summary

The multimodal flow enables:

✅ **Regular images** → Fetched from S3 → Base64 encoded → Passed to Claude
✅ **PDF documents** → Converted to images → Stored in pdf-pages/ → Passed to Claude
✅ **Text files** → Fetched from S3 → Included in text prompt
⏳ **Video/Audio** → Metadata only (future: keyframes/transcripts)

Claude receives actual visual content and can read text, analyze diagrams, and understand document structure.
