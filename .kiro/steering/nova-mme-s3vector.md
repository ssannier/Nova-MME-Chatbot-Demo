# Nova Multimodal Embeddings & S3 Vector Reference

## Nova Multimodal Embeddings (MME)

### Model Information
**Model ID**: `amazon.nova-2-multimodal-embeddings-v1:0`
**Service**: AWS Bedrock
**Capabilities**: Unified semantic space for text, images, video, audio, and documents

### Key Features

**Matryoshka Relational Learning (MRL)**:
- One embedding at 3072 dimensions contains nested embeddings at 256, 384, and 1024 dimensions
- First N dimensions of a 3072-dim vector = N-dim invocation result (after renormalization)
- Cost efficient: One invocation produces four usable embeddings
- Enables performance tradeoffs: smaller dimensions = faster search, larger = more accurate

**Automatic Chunking**:
- Long videos/audio: Automatically segmented into chunks (configurable, default 5 seconds)
- Long text: Automatically segmented (configurable, default 32,000 characters)
- Each segment gets its own embedding with metadata

### API Types

**Synchronous API** (`invoke_model`):
- For single embeddings without segmentation
- Max 30 seconds for video/audio
- Max 8,192 characters for text inline
- Returns immediately with embedding

**Asynchronous API** (`start_async_invoke`, `get_async_invoke`):
- Required for segmented embeddings (long content)
- Required for video/audio > 30 seconds
- Output written to S3 bucket
- Poll for completion status

### Schema Structures

#### Async Invocation (Segmented Embeddings)

```python
model_input = {
    "schemaVersion": "nova-multimodal-embed-v1",
    "taskType": "SEGMENTED_EMBEDDING",
    "segmentedEmbeddingParams": {
        "embeddingPurpose": "GENERIC_INDEX",  # For indexing
        "embeddingDimension": 3072,  # Always use max for MRL
        
        # Exactly ONE of: text, image, video, audio
        "text": {
            "truncationMode": "END",
            "source": {"s3Location": {"uri": "s3://bucket/file.txt"}},
            "segmentationConfig": {"maxLengthChars": 32000}
        },
        "image": {
            "format": "jpeg",
            "source": {"s3Location": {"uri": "s3://bucket/image.jpg"}},
            "detailLevel": "STANDARD_IMAGE"
        },
        "video": {
            "format": "mp4",
            "source": {"s3Location": {"uri": "s3://bucket/video.mp4"}},
            "embeddingMode": "AUDIO_VIDEO_COMBINED",
            "segmentationConfig": {"durationSeconds": 5}
        },
        "audio": {
            "format": "mp3",
            "source": {"s3Location": {"uri": "s3://bucket/audio.mp3"}},
            "segmentationConfig": {"durationSeconds": 5}
        }
    }
}

response = bedrock_runtime.start_async_invoke(
    modelId="amazon.nova-2-multimodal-embeddings-v1:0",
    modelInput=model_input,
    outputDataConfig={
        "s3OutputDataConfig": {
            "s3Uri": "s3://output-bucket/job-id"
        }
    }
)
# Returns: {"invocationArn": "arn:aws:bedrock:..."}
```

#### Sync Invocation (Single Embedding)

```python
model_input = {
    "schemaVersion": "nova-multimodal-embed-v1",
    "taskType": "SINGLE_EMBEDDING",
    "singleEmbeddingParams": {
        "embeddingPurpose": "GENERIC_RETRIEVAL",  # For querying
        "embeddingDimension": 1024,
        "text": {
            "truncationMode": "END",
            "value": "User query text here"
        }
    }
}

response = bedrock_runtime.invoke_model(
    modelId="amazon.nova-2-multimodal-embeddings-v1:0",
    body=json.dumps(model_input)
)

result = json.loads(response['body'].read())
embedding = result['embeddings'][0]['embedding']
```

### Embedding Purpose Values

**For Indexing** (creating embeddings to store):
- `GENERIC_INDEX` - Use for all modalities when indexing

**For Retrieval** (creating query embeddings):
- `GENERIC_RETRIEVAL` - Mixed modality search (recommended for this project)
- `TEXT_RETRIEVAL` - Text-only repositories
- `IMAGE_RETRIEVAL` - Image-only repositories
- `VIDEO_RETRIEVAL` - Video-only repositories
- `AUDIO_RETRIEVAL` - Audio-only repositories
- `DOCUMENT_RETRIEVAL` - Document image repositories

**Other**:
- `CLASSIFICATION` - For classification tasks
- `CLUSTERING` - For clustering tasks

### Supported File Types

**Images**: PNG, JPEG, GIF, WebP
**Videos**: MP4, MOV, MKV, WebM, FLV, MPEG, MPG, WMV, 3GP
**Audio**: MP3, WAV, OGG
**Text**: Any text format (TXT, MD, JSON, CSV, etc.)

### File Size Limits

**Synchronous**:
- Inline (all types): 25 MB (after Base64 encoding)
- S3 Text: 1 MB / 50,000 characters
- S3 Image: 50 MB
- S3 Video: 30 seconds / 100 MB
- S3 Audio: 30 seconds / 100 MB

**Asynchronous**:
- Text: 634 MB
- Image: 50 MB
- Video: 2 GB / 2 hours
- Audio: 1 GB / 2 hours

### Segment Limits

**Asynchronous operations**:
- Text: Max 1,900 segments
- Video/Audio: Max 1,434 segments

### Async Output Structure

```
s3://output-bucket/job-id/
  segmented-embedding-result.json    # Job summary
  embedding-text.jsonl               # Text embeddings
  embedding-image.json               # Image embeddings
  embedding-video.jsonl              # Video embeddings
  embedding-audio.jsonl              # Audio embeddings
  manifest.json                      # Job manifest
```

**segmented-embedding-result.json**:
```json
{
  "sourceFileUri": "s3://bucket/file.mp4",
  "embeddingDimension": 3072,
  "embeddingResults": [
    {
      "embeddingType": "VIDEO",
      "status": "SUCCESS",
      "outputFileUri": "s3://output-bucket/job-id/embedding-video.jsonl"
    }
  ]
}
```

**embedding-*.jsonl** (one line per segment):
```json
{
  "embedding": [0.1, 0.2, ...],
  "segmentMetadata": {
    "segmentIndex": 0,
    "segmentStartSeconds": 0.0,
    "segmentEndSeconds": 5.0
  },
  "status": "SUCCESS"
}
```

### MRL Implementation

**Truncation and Renormalization**:
```python
import numpy as np

def truncate_and_normalize(embedding_3072: List[float], target_dim: int) -> List[float]:
    """
    Truncate 3072-dim embedding to target dimension and renormalize.
    This is the core of Matryoshka Relational Learning.
    """
    # Truncate to first N dimensions
    truncated = np.array(embedding_3072[:target_dim])
    
    # Renormalize using L2 norm
    norm = np.linalg.norm(truncated)
    if norm > 0:
        normalized = truncated / norm
    else:
        normalized = truncated
    
    return normalized.tolist()

# One 3072-dim embedding generates four usable embeddings
embeddings = {
    256: truncate_and_normalize(embedding_3072, 256),
    384: truncate_and_normalize(embedding_3072, 384),
    1024: truncate_and_normalize(embedding_3072, 1024),
    3072: embedding_3072  # Already normalized
}
```

## S3 Vectors

### Overview

**S3 Vectors** is an AWS service that enables semantic search directly on S3 using vector embeddings.

**Status**: Generally Available (GA)
**Service Type**: Specialized S3 bucket type for vector storage and search
**Use Case**: Store and query high-dimensional embeddings with native similarity search

**Official Documentation**:
- Main Guide: https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors.html
- Buckets: https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-buckets.html
- Indexes: https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-indexes.html
- Vectors: https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-vectors.html
- Limitations: https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-limitations.html
- Best Practices: https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-best-practices.html
- CLI: https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-cli.html
- Integration: https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-integration.html

**Key Features**:
- Native vector similarity search in S3
- Supports cosine similarity distance metric
- Multiple indexes per bucket (one per dimension)
- Scalable storage and query performance
- No separate vector database needed
- Metadata stored alongside vectors

### Core Concepts

**S3 Vector Bucket**:
- Specialized bucket type for vector storage
- Created with `--bucket-type vector` flag
- Supports multiple vector indexes
- Region-specific (e.g., us-east-1)

**Vector Index**:
- Named collection of vectors at specific dimension
- One index per dimension (e.g., `embeddings-256d`, `embeddings-1024d`)
- Configured with dimension size and distance metric
- Supports metadata alongside vectors

**Vector Object**:
- Individual embedding stored in an index
- Includes vector array and optional metadata
- Identified by unique key
- Searchable via similarity queries

### Architecture for MRL

**4 Indexes for 4 Dimensions**:
```
S3 Vector Bucket: nova-mme-demo-embeddings-dev
├── Index: embeddings-256d (dimension: 256)
├── Index: embeddings-384d (dimension: 384)
├── Index: embeddings-1024d (dimension: 1024)
└── Index: embeddings-3072d (dimension: 3072)
```

Each index stores vectors at its specific dimension with metadata

### Key Concepts

**Vector Indexes**: Named collections of embeddings at specific dimensions
- Example: `embeddings-256d`, `embeddings-1024d`
- Each index stores vectors of the same dimension
- Supports metadata storage alongside vectors

**Similarity Search**: Find nearest neighbors using cosine similarity or other metrics

### Current Implementation

**Note**: This project uses a placeholder implementation that stores embeddings as JSON files in S3. When S3 Vector API becomes fully available, replace with actual API calls.

**Placeholder Storage Structure**:
```
s3://vector-bucket/
  embeddings-256d/
    {objectId}/
      segment_0.json
      segment_1.json
  embeddings-384d/
    {objectId}/
      segment_0.json
  embeddings-1024d/
    {objectId}/
      segment_0.json
  embeddings-3072d/
    {objectId}/
      segment_0.json
```

**Embedding JSON Format**:
```json
{
  "embedding": [0.1, 0.2, 0.3, ...],
  "metadata": {
    "sourceS3Uri": "s3://source-bucket/video.mp4",
    "fileName": "video.mp4",
    "fileType": ".mp4",
    "modalityType": "VIDEO",
    "segmentIndex": 0,
    "segmentStartSeconds": 0.0,
    "segmentEndSeconds": 5.0,
    "embeddingDimension": 1024,
    "objectId": "video_mp4_20240115103000",
    "processingTimestamp": "2024-01-15T10:30:00Z"
  }
}
```

### S3 Vectors API

**Create S3 Vector Bucket** (AWS CLI):
```bash
aws s3api create-bucket \
    --bucket nova-mme-demo-embeddings-dev \
    --region us-east-1 \
    --bucket-type vector
```

**Create Vector Index** (AWS CLI):
```bash
aws s3api create-vector-index \
    --bucket nova-mme-demo-embeddings-dev \
    --index-name embeddings-1024d \
    --dimension 1024 \
    --distance-metric cosine
```

**Put Vector** (Boto3):
```python
import boto3
import json

s3_client = boto3.client('s3')

# Store vector with metadata
s3_client.put_object(
    Bucket='nova-mme-demo-embeddings-dev',
    Key=f'embeddings-1024d/{object_id}_segment_{segment_idx}',
    Body=json.dumps({
        'vector': embedding_array,  # List of floats
        'metadata': {
            'sourceS3Uri': 's3://source-bucket/file.mp4',
            'fileName': 'file.mp4',
            'modalityType': 'VIDEO',
            'segmentIndex': 0,
            'segmentStartSeconds': 0.0,
            'segmentEndSeconds': 5.0
        }
    }),
    ContentType='application/json'
)
```

**Query Vectors** (Boto3):
```python
# Search for similar vectors
response = s3_client.query_vectors(
    Bucket='nova-mme-demo-embeddings-dev',
    IndexName='embeddings-1024d',
    QueryVector=query_embedding,  # List of floats
    MaxResults=5,
    DistanceMetric='cosine'
)

# Returns:
# {
#   'Vectors': [
#     {
#       'Key': 'embeddings-1024d/file_segment_0',
#       'Distance': 0.05,  # Lower is more similar for cosine
#       'Metadata': {...}
#     }
#   ]
# }
```

### IAM Permissions

**For S3 Vectors**:
```python
{
    "Effect": "Allow",
    "Action": [
        "s3:CreateBucket",
        "s3:CreateVectorIndex",
        "s3:PutObject",
        "s3:GetObject",
        "s3:QueryVectors",
        "s3:DescribeVectorIndex",
        "s3:ListVectorIndexes"
    ],
    "Resource": [
        "arn:aws:s3:::nova-mme-demo-embeddings-dev",
        "arn:aws:s3:::nova-mme-demo-embeddings-dev/*"
    ]
}
```

### Key Limitations

**Vector Dimensions**:
- Minimum: 1 dimension
- Maximum: 4,096 dimensions
- ✅ Nova MME 3072-dim is fully supported!
- All 4 MRL dimensions (256, 384, 1024, 3072) can use S3 Vectors

**Index Limits**:
- Maximum indexes per bucket: 100
- Maximum vectors per index: No hard limit (scales with S3)

**Query Limits**:
- MaxResults: Up to 1000 vectors per query
- Distance metric: Currently only cosine similarity supported

**Performance**:
- Query latency: Typically 10-100ms depending on index size
- Throughput: Scales with S3 request rates

## Project-Specific Patterns

### Embedder Pipeline
1. Always invoke Nova MME at **3072 dimensions** for MRL
2. Use `GENERIC_INDEX` for embedding purpose
3. Use async API with `SEGMENTED_EMBEDDING` task type
4. Store all four dimension variants (256, 384, 1024, 3072) in S3 Vector indexes

### Query Handler
1. Use sync API with `SINGLE_EMBEDDING` task type
2. Use `GENERIC_RETRIEVAL` for embedding purpose
3. Query at user-selected dimension (default 1024)
4. Optional: Hierarchical search (256-dim → 1024-dim refinement)

### Metadata Preservation
Always combine metadata from three sources:
1. **Source file** (Lambda 1): S3 URI, filename, file type, size, upload time
2. **Segment info** (async output): Segment index, timestamps/positions, modality
3. **Processing** (Lambda 3): Embedding dimension, processing time

### Error Handling
- Check `status` field in async output (SUCCESS, FAILURE, PARTIAL_SUCCESS)
- Handle missing segments gracefully
- Log detailed error messages for debugging
- Return structured error responses to frontend

## Common Pitfalls

1. **Forgetting to renormalize after truncation**: MRL requires L2 normalization
2. **Wrong embedding purpose**: Use INDEX for storing, RETRIEVAL for querying
3. **Dimension mismatch**: Query dimension must match index dimension
4. **Missing metadata**: Preserve all metadata through the pipeline
5. **Async timeout**: Long videos can take 30+ minutes to process
6. **Segment limits**: Text > 1,900 segments or video > 1,434 segments will fail

## Performance Characteristics

**Embedding Generation**:
- Small image: ~5-10 seconds
- 30-second video: ~2-5 minutes
- 2-hour video: ~30-60 minutes
- 10KB text: ~30-60 seconds

**Search Performance** (estimated):
- 256-dim: Fastest, ~10ms per query
- 384-dim: Fast, ~15ms per query
- 1024-dim: Moderate, ~30ms per query
- 3072-dim: Slowest, ~50ms per query

**Accuracy vs Speed Tradeoff**:
- Lower dimensions: Faster but less precise
- Higher dimensions: Slower but more accurate
- Sweet spot: 1024-dim for most use cases
