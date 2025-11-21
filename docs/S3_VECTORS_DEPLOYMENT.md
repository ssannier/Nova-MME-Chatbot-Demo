# S3 Vectors Deployment & Testing Guide

## Pre-Deployment Checklist

- [x] CDK stack updated with S3 Vector bucket (CfnResource)
- [x] 4 vector indexes defined in CDK (256d, 384d, 1024d, 3072d)
- [x] IAM permissions updated for S3 Vectors operations
- [x] Store Embeddings Lambda updated (uses 'vector' field)
- [x] Query Handler Lambda updated (uses query_vectors API)
- [x] URL encoding bug fixed in processor Lambda
- [ ] All changes committed to git

## Deployment Steps

### Step 0: Install S3 Vectors Construct

```bash
# Install the cdk-s3-vectors construct library
pip install cdk-s3-vectors>=0.3.2

# Or install all requirements
pip install -r requirements.txt
```

### Step 1: Commit Changes

```bash
git add .
git commit -m "Implement S3 Vectors for native similarity search

- Create S3 Vector bucket with CfnResource in CDK
- Define 4 vector indexes for MRL dimensions
- Update Store Embeddings to use 'vector' field
- Update Query Handler to use S3 Vectors query_vectors API
- Add S3 Vectors IAM permissions
- Fix URL encoding in processor Lambda"

git push origin embedder-tests
```

### Step 2: Deploy Embedder Stack

```bash
# This will create S3 Vector bucket, indexes, and Lambda functions
cdk deploy NovaMMEEmbedderStack
```

**Expected Output:**
```
✅  NovaMMEEmbedderStack

Resources:
- VectorBucket (S3 Vector bucket via cdk-s3-vectors)
- VectorIndex256d, VectorIndex384d, VectorIndex1024d, VectorIndex3072d
- Updated Lambda functions with S3 Vectors permissions
- Step Functions state machine
```

**Note:** The cdk-s3-vectors construct handles creating the S3 Tables bucket and vector indexes.

### Step 3: Verify S3 Vector Bucket

```bash
# Check bucket exists and is vector type
aws s3api head-bucket --bucket nova-mme-demo-embeddings-dev

# List vector indexes
aws s3api list-vector-indexes --bucket nova-mme-demo-embeddings-dev
```

**Expected Output:**
```json
{
  "VectorIndexes": [
    {"IndexName": "embeddings-256d", "Dimension": 256, "DistanceMetric": "cosine"},
    {"IndexName": "embeddings-384d", "Dimension": 384, "DistanceMetric": "cosine"},
    {"IndexName": "embeddings-1024d", "Dimension": 1024, "DistanceMetric": "cosine"},
    {"IndexName": "embeddings-3072d", "Dimension": 3072, "DistanceMetric": "cosine"}
  ]
}
```

### Step 4: Deploy Chatbot Stack

```bash
# This will update the Query Handler Lambda
cdk deploy NovaMMEChatbotStack
```

## Testing Plan

### Test 1: Upload and Process a File

**Upload a test file:**
```bash
# Use a file with a simple name (no special characters for first test)
aws s3 cp test-image.jpg s3://cic-multimedia-test-dev/
```

**Monitor Step Functions:**
1. Go to AWS Console → Step Functions
2. Find the execution for your file
3. Watch it progress through all steps

**Expected Flow:**
```
ProcessFile → Wait → CheckStatus (loop) → StoreEmbeddings → Success
```

**Verify Embeddings Stored:**
```bash
# Check that embeddings were stored in all 4 indexes
aws s3 ls s3://nova-mme-demo-embeddings-dev/embeddings-256d/
aws s3 ls s3://nova-mme-demo-embeddings-dev/embeddings-384d/
aws s3 ls s3://nova-mme-demo-embeddings-dev/embeddings-1024d/
aws s3 ls s3://nova-mme-demo-embeddings-dev/embeddings-3072d/
```

**Check Embedding Format:**
```bash
# Download and inspect one embedding
aws s3 cp s3://nova-mme-demo-embeddings-dev/embeddings-1024d/test-image_jpg_segment_0.json test.json
cat test.json
```

**Expected Format:**
```json
{
  "vector": [0.1, 0.2, ...],  // 1024 floats
  "metadata": {
    "sourceS3Uri": "s3://cic-multimedia-test-dev/test-image.jpg",
    "fileName": "test-image.jpg",
    "modalityType": "IMAGE",
    ...
  }
}
```

### Test 2: Query with Different Dimensions

**Test 256d (fastest):**
```bash
curl -X POST https://your-api.execute-api.us-east-1.amazonaws.com/prod/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test image", "dimension": 256, "hierarchical": false}'
```

**Test 1024d (recommended):**
```bash
curl -X POST https://your-api.execute-api.us-east-1.amazonaws.com/prod/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test image", "dimension": 1024, "hierarchical": false}'
```

**Test 3072d (highest accuracy):**
```bash
curl -X POST https://your-api.execute-api.us-east-1.amazonaws.com/prod/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test image", "dimension": 3072, "hierarchical": false}'
```

**Expected Response:**
```json
{
  "answer": "Based on the image...",
  "sources": [
    {
      "key": "test-image.jpg",
      "similarity": 0.95,
      "text_preview": "Type: IMAGE | ..."
    }
  ],
  "model": "anthropic.claude-3-5-sonnet-20240620-v1:0",
  "query": "test image",
  "dimension": 1024,
  "resultsFound": 1
}
```

### Test 3: Hierarchical Search

```bash
curl -X POST https://your-api.execute-api.us-east-1.amazonaws.com/prod/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test image", "dimension": 1024, "hierarchical": true}'
```

**Expected Behavior:**
- First pass: Query 256d index (fast, broad recall)
- Second pass: Re-rank with 1024d (precise)
- Should return same results as 1024d but potentially faster

### Test 4: Multiple File Types

Upload one of each type:
```bash
aws s3 cp test-image.jpg s3://cic-multimedia-test-dev/
aws s3 cp test-video.mp4 s3://cic-multimedia-test-dev/
aws s3 cp test-audio.mp3 s3://cic-multimedia-test-dev/
aws s3 cp test-document.txt s3://cic-multimedia-test-dev/
```

Wait for all to process, then query:
```bash
curl -X POST https://your-api.execute-api.us-east-1.amazonaws.com/prod/query \
  -H "Content-Type: application/json" \
  -d '{"query": "show me all content", "dimension": 1024}'
```

**Expected:** Should return results from all modalities

### Test 5: Frontend Integration

1. Open frontend: https://main.d3cfiw370sco4d.amplifyapp.com
2. Enter query: "test image"
3. Verify:
   - Results appear
   - Sources are displayed
   - Similarity scores shown
   - No errors in browser console

## Troubleshooting

### Issue: S3 Vector bucket creation fails

**Error:** `Bucket type 'vector' not supported`

**Solution:** S3 Vectors may not be available in your region or account. Check:
```bash
aws s3api list-bucket-types --region us-east-1
```

### Issue: Vector index creation fails

**Error:** `VectorIndex resource type not found`

**Solution:** CDK may not support S3 Vectors yet. The CfnResource approach should work, but verify CloudFormation supports it:
```bash
aws cloudformation describe-type --type RESOURCE --type-name AWS::S3::VectorIndex
```

### Issue: query_vectors returns empty results

**Check:**
1. Embeddings were actually stored:
   ```bash
   aws s3 ls s3://nova-mme-demo-embeddings-dev/embeddings-1024d/ --recursive
   ```

2. Index exists:
   ```bash
   aws s3api describe-vector-index \
     --bucket nova-mme-demo-embeddings-dev \
     --index-name embeddings-1024d
   ```

3. Check Lambda logs:
   ```bash
   aws logs tail /aws/lambda/NovaMMEChatbotStack-QueryHandlerFunction... --follow
   ```

### Issue: "Distance" field missing in query response

**Cause:** S3 Vectors API might return results in different format

**Solution:** Check actual response structure and adjust code:
```python
# In Query Handler Lambda, add debug logging
print(f"S3 Vectors response: {json.dumps(response)}")
```

### Issue: Embeddings stored but not searchable

**Cause:** Objects might not be in correct path format for index

**Check:** Verify key format matches index name:
```
embeddings-1024d/objectid_segment_0.json  ✅ Correct
embeddings-1024d/objectid/segment_0.json  ❌ Wrong
```

## Performance Benchmarks

After successful deployment, measure performance:

**Query Latency by Dimension:**
```bash
# Run 10 queries for each dimension and measure time
for dim in 256 384 1024 3072; do
  echo "Testing ${dim}d..."
  time curl -X POST https://your-api.com/query \
    -d "{\"query\":\"test\",\"dimension\":${dim}}"
done
```

**Expected Latency:**
- 256d: 50-100ms
- 384d: 75-125ms
- 1024d: 100-200ms
- 3072d: 150-300ms

## Success Criteria

- [x] S3 Vector bucket created
- [ ] All 4 vector indexes created
- [ ] File upload triggers Step Functions
- [ ] Embeddings stored in all 4 indexes
- [ ] Query returns results from S3 Vectors
- [ ] All 4 dimensions work
- [ ] Hierarchical search works
- [ ] Frontend displays results
- [ ] No errors in CloudWatch logs

## Rollback Plan

If S3 Vectors doesn't work:

1. Revert CDK changes:
   ```bash
   git revert HEAD
   cdk deploy NovaMMEEmbedderStack
   cdk deploy NovaMMEChatbotStack
   ```

2. Falls back to manual search implementation

3. No data loss - embeddings stored in same format

