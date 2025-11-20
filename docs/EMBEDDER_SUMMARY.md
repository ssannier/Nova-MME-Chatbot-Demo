# Embedder Pipeline - Complete Architecture Summary

## Overview

The Embedder is an async processing pipeline that takes uploaded files, generates multimodal embeddings using Nova MME, and stores them in multiple dimensions using Matryoshka Relational Learning (MRL).

## Architecture Flow

```
S3 Upload → Lambda 1 → Step Functions → Lambda 2 (polling) → Lambda 3 → S3 Vector Storage
```

## Components

### 1. S3 Source Bucket (`cic-multimedia-test`)
- Receives uploaded files (images, videos, audio, text)
- Triggers Step Functions workflow via S3 event notification
- Supports all Nova MME file types

### 2. Lambda 1: Nova MME Processor
**File**: `lambda/embedder/processor/index.py`

**Responsibilities**:
- Extracts metadata from uploaded S3 object
- Determines file type and creates appropriate model input JSON
- Always invokes Nova MME at **3072 dimensions** (for MRL)
- Starts async Bedrock invocation
- Returns invocation ARN and metadata to Step Functions

**Metadata Captured**:
- Source S3 URI and filename
- File type, size, content type
- Upload timestamp
- Unique object ID

**Supported File Types**:
- **Images**: PNG, JPG, JPEG, GIF, WebP
- **Videos**: MP4, MOV, MKV, WebM, FLV, MPEG, MPG, WMV, 3GP
- **Audio**: MP3, WAV, OGG
- **Text**: TXT, MD, JSON, CSV

**Tests**: 35 tests covering all file types and schema validation

### 3. Step Functions State Machine
**Orchestration**:
1. Invokes Lambda 1 (Processor)
2. Waits 30 seconds
3. Invokes Lambda 2 (Check Status)
4. If IN_PROGRESS: loop back to wait
5. If COMPLETED: invoke Lambda 3
6. If FAILED: terminate with error

**State Management**:
- Carries metadata from Lambda 1 through entire workflow
- Enables Lambda 3 to combine source metadata with segment metadata
- 2-hour timeout for long processing jobs

### 4. Lambda 2: Check Job Status
**File**: `lambda/embedder/check_status/index.py`

**Responsibilities**:
- Polls Bedrock async invocation status
- Maps Bedrock status to workflow status
- Passes through all event data unchanged
- Provides status details for monitoring

**Status Mapping**:
- `Completed` → `COMPLETED`
- `InProgress`, `Scheduled` → `IN_PROGRESS`
- `Failed`, `Expired` → `FAILED`

**Tests**: 7 tests covering all status scenarios

### 5. Lambda 3: Store Embeddings
**File**: `lambda/embedder/store_embeddings/index.py`

**Responsibilities**:
- Reads `segmented-embedding-result.json` from S3
- Parses `embedding-*.jsonl` files for each modality
- For each 3072-dim embedding:
  - Truncates to 256, 384, 1024 dimensions
  - Renormalizes using L2 norm
  - Stores all 4 variants in S3 Vector indexes
- Combines metadata from all sources

**MRL Implementation**:
```python
# One 3072-dim embedding generates 4 usable embeddings
embeddings = {
    256: truncate_and_normalize(embedding_3072, 256),
    384: truncate_and_normalize(embedding_3072, 384),
    1024: truncate_and_normalize(embedding_3072, 1024),
    3072: embedding_3072  # Keep original
}
```

**Metadata Combination**:
- **From Lambda 1**: Source file info, object ID, upload time
- **From async output**: Segment index, timestamps/positions, modality type
- **From Lambda 3**: Embedding dimension, processing timestamp

**Tests**: 20 tests covering segment processing, metadata combination, storage

### 6. S3 Vector Bucket (`nova-mme-demo-embeddings`)
**Indexes**:
- `embeddings-256d` - Fast, coarse-grained search
- `embeddings-384d` - Balanced performance
- `embeddings-1024d` - High precision
- `embeddings-3072d` - Maximum precision

**Storage Structure** (current implementation):
```
embeddings-{dimension}d/
  {objectId}/
    segment_0.json
    segment_1.json
    ...
```

Each JSON contains:
```json
{
  "embedding": [0.1, 0.2, ...],
  "metadata": {
    "sourceS3Uri": "s3://...",
    "fileName": "video.mp4",
    "segmentIndex": 0,
    "segmentStartSeconds": 0.0,
    "embeddingDimension": 1024,
    ...
  }
}
```

## Key Features

### Matryoshka Relational Learning (MRL)
- **One invocation, four embeddings**: Single 3072-dim call generates all variants
- **Nested property**: First N dimensions are meaningful
- **Cost efficient**: Pay for one invocation, get four usable embeddings
- **Performance tradeoff**: Choose dimension based on speed vs accuracy needs

### Automatic Chunking
- Long videos/audio automatically segmented (5-second chunks)
- Long text automatically segmented (32,000 char chunks)
- Each segment gets its own embedding
- Segment metadata preserved for temporal/spatial navigation

### Rich Metadata
Every embedding includes:
- Source file information
- Segment boundaries (time or character positions)
- Modality type
- Processing timestamps
- Dimension used

### Error Handling
- Failed segments are skipped (PARTIAL_SUCCESS)
- Step Functions retries on transient failures
- Comprehensive error logging
- Status tracking throughout pipeline

## Configuration

**Environment Variables**:
- `EMBEDDING_DIMENSION`: Always 3072 (Lambda 1)
- `MODEL_ID`: Nova MME model ID
- `OUTPUT_BUCKET`: Async job output location
- `VECTOR_BUCKET`: S3 Vector storage bucket
- `EMBEDDING_DIMENSIONS`: Comma-separated list (Lambda 3)

**Config Files**:
- `config/dev.json` - Development settings
- `config/prod.json` - Production settings
- `config/constants.py` - Shared constants

## Testing

**Total Tests**: 85 unit tests

**Coverage**:
- Embedding utilities: 18 tests (MRL logic)
- Processor Lambda: 35 tests (all file types)
- Check Status Lambda: 7 tests (all statuses)
- Store Embeddings Lambda: 20 tests (MRL storage)
- Schema validation: 25 tests (API compliance)

**Run Tests**:
```bash
# Install dependencies
pip install -r tests/requirements.txt
pip install -r requirements-lambda.txt

# Run all tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=lambda --cov-report=html
```

## Deployment

**Prerequisites**:
- AWS account with Bedrock access
- CDK CLI installed
- Python 3.11+

**Deploy**:
```bash
# Install dependencies
pip install -r requirements.txt

# Bootstrap CDK (first time)
cdk bootstrap

# Deploy embedder stack
cdk deploy NovaMMEEmbedderStack
```

**Upload Test Files**:
```bash
python scripts/upload_test_files.py
```

## Performance Characteristics

**Processing Time**:
- Small images: ~30 seconds
- Short videos (30s): ~2-5 minutes
- Long videos (2 hours): ~30-60 minutes
- Text documents: ~1-3 minutes

**Storage**:
- 4× embeddings per segment
- Example: 10-segment video = 40 embedding vectors stored
- Dimensions: 256 (1KB), 384 (1.5KB), 1024 (4KB), 3072 (12KB)

**Cost Optimization**:
- Single 3072-dim invocation instead of 4 separate calls
- ~75% cost reduction vs invoking at each dimension
- Storage cost scales with number of segments

## Future Enhancements

1. **S3 Vector API Integration**: Replace placeholder with actual S3 Vector API
2. **Batch Processing**: Process multiple files in parallel
3. **Progress Tracking**: Real-time status updates via EventBridge
4. **Retry Logic**: Automatic retry for failed segments
5. **Metrics**: CloudWatch metrics for processing times and success rates

## Troubleshooting

**Common Issues**:

1. **Job timeout**: Increase Step Functions timeout or reduce file size
2. **Memory errors in Lambda 3**: Increase memory allocation (currently 2048MB)
3. **Unsupported file type**: Check file extension matches supported formats
4. **Missing metadata**: Verify Step Functions passes data correctly

**Logs**:
- Lambda 1: `/aws/lambda/NovaMMEEmbedderStack-ProcessorFunction`
- Lambda 2: `/aws/lambda/NovaMMEEmbedderStack-CheckStatusFunction`
- Lambda 3: `/aws/lambda/NovaMMEEmbedderStack-StoreEmbeddingsFunction`
- Step Functions: Execution history in AWS Console

## References

- [Nova MME Documentation](docs/initial/novaMMEAsyncDocs.md)
- [Improved Structure](docs/improved/improvedStructure.md)
- [CDK Structure](docs/improved/CDKStructure.md)
- [Demo Suggestions](docs/improved/demoSuggestions.md)
