# S3 Vectors Implementation Plan

## Overview

Migrate from placeholder S3 + manual search to S3 Vectors for native similarity search.

**S3 Vectors Capability**: Supports 1 to 4,096 dimensions - perfect for Nova MME!

**Solution**: Use S3 Vectors for all 4 MRL dimensions
- 256d, 384d, 1024d, 3072d all use native S3 Vectors search
- No manual search fallback needed
- Consistent performance across all dimensions

## Architecture

```
Nova MME (3072-dim) → Store Embeddings Lambda
                      ├→ S3 Vector Index: embeddings-256d
                      ├→ S3 Vector Index: embeddings-384d
                      ├→ S3 Vector Index: embeddings-1024d
                      └→ S3 Vector Index: embeddings-3072d

Query → Query Handler Lambda → S3 Vectors query_vectors API (all dimensions)
```

## Implementation Steps

### Step 1: Create S3 Vector Bucket

```bash
# Create vector bucket
aws s3api create-bucket \
    --bucket nova-mme-demo-embeddings-dev \
    --region us-east-1 \
    --bucket-type vector

# Create 4 vector indexes (all MRL dimensions)
aws s3api create-vector-index \
    --bucket nova-mme-demo-embeddings-dev \
    --index-name embeddings-256d \
    --dimension 256 \
    --distance-metric cosine

aws s3api create-vector-index \
    --bucket nova-mme-demo-embeddings-dev \
    --index-name embeddings-384d \
    --dimension 384 \
    --distance-metric cosine

aws s3api create-vector-index \
    --bucket nova-mme-demo-embeddings-dev \
    --index-name embeddings-1024d \
    --dimension 1024 \
    --distance-metric cosine

aws s3api create-vector-index \
    --bucket nova-mme-demo-embeddings-dev \
    --index-name embeddings-3072d \
    --dimension 3072 \
    --distance-metric cosine
```

### Step 2: Update CDK Stack

**lib/embedder_stack.py**:
```python
# Replace regular S3 bucket with S3 Vector bucket
# Note: CDK may not have L2 constructs yet, use CfnResource

from aws_cdk import aws_s3 as s3, CfnResource

# Create S3 Vector bucket (using CloudFormation)
vector_bucket_cfn = CfnResource(
    self,
    "VectorBucketCfn",
    type="AWS::S3::Bucket",
    properties={
        "BucketName": config["buckets"]["vector_bucket"],
        "BucketType": "vector"
    }
)

# Create vector indexes for all 4 MRL dimensions
for dim in [256, 384, 1024, 3072]:
    CfnResource(
        self,
        f"VectorIndex{dim}d",
        type="AWS::S3::VectorIndex",
        properties={
            "BucketName": config["buckets"]["vector_bucket"],
            "IndexName": f"embeddings-{dim}d",
            "Dimension": dim,
            "DistanceMetric": "cosine"
        }
    )

# Keep reference for other stacks
self.vector_bucket = s3.Bucket.from_bucket_name(
    self,
    "VectorBucket",
    config["buckets"]["vector_bucket"]
)
```

### Step 3: Update Store Embeddings Lambda

**lambda/embedder/store_embeddings/index.py**:

```python
def store_embedding(bucket: str, index_name: str, object_id: str, 
                   segment_idx: int, embedding: List[float], 
                   metadata: Dict[str, Any], dimension: int):
    """
    Store embedding in S3 Vector index
    """
    key = f"{index_name}/{object_id}_segment_{segment_idx}.json"
    
    data = {
        'vector': embedding,
        'metadata': metadata
    }
    
    # All dimensions (256, 384, 1024, 3072) use S3 Vectors
    # S3 Vectors automatically indexes when you put to index path
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(data),
        ContentType='application/json'
    )
    print(f"Stored in S3 Vector index: {index_name} (dimension: {dimension})")
```

### Step 4: Update Query Handler Lambda

**lambda/chatbot/query_handler/index.py**:

```python
def search_s3_vector_index(index_name: str, embedding: List[float], k: int) -> List[Dict[str, Any]]:
    """
    Search S3 Vector index for similar embeddings
    All dimensions (256, 384, 1024, 3072) use S3 Vectors native search
    """
    try:
        response = s3_client.query_vectors(
            Bucket=VECTOR_BUCKET,
            IndexName=index_name,
            QueryVector=embedding,
            MaxResults=k,
            DistanceMetric='cosine'
        )
        
        # Convert S3 Vectors response to our format
        results = []
        for vector in response.get('Vectors', []):
            # Read full object to get metadata
            obj_response = s3_client.get_object(
                Bucket=VECTOR_BUCKET,
                Key=vector['Key']
            )
            data = json.loads(obj_response['Body'].read())
            
            # Convert distance to similarity (cosine distance → similarity)
            # S3 Vectors returns distance (0 = identical), we want similarity (1 = identical)
            similarity = 1 - vector['Distance']
            
            results.append({
                'similarity': similarity,
                'metadata': data['metadata'],
                'embedding': data['vector']
            })
        
        return results
        
    except Exception as e:
        print(f"Error querying S3 Vectors: {e}")
        return []
```

### Step 5: Update IAM Permissions

**lib/chatbot_stack.py**:

```python
# Add S3 Vectors permissions
role.add_to_policy(
    iam.PolicyStatement(
        actions=[
            "s3:QueryVectors",
            "s3:DescribeVectorIndex",
            "s3:ListVectorIndexes"
        ],
        resources=[
            self.vector_bucket.bucket_arn,
            f"{self.vector_bucket.bucket_arn}/*"
        ]
    )
)
```

**lib/embedder_stack.py**:

```python
# Add S3 Vectors permissions for store embeddings
lambda_role.add_to_policy(
    iam.PolicyStatement(
        actions=[
            "s3:CreateVectorIndex",
            "s3:PutObject",
            "s3:DescribeVectorIndex"
        ],
        resources=[
            self.vector_bucket.bucket_arn,
            f"{self.vector_bucket.bucket_arn}/*"
        ]
    )
)
```

## Testing Plan

### Test 1: Create Infrastructure
```bash
cdk deploy NovaMMEEmbedderStack
```

Verify:
- S3 Vector bucket created
- 3 vector indexes created (256d, 384d, 1024d)

### Test 2: Upload and Process File
```bash
aws s3 cp test-video.mp4 s3://cic-multimedia-test-dev/
```

Verify:
- Step Functions completes successfully
- Embeddings stored in all 4 locations
- S3 Vectors indexes contain vectors

### Test 3: Query at Different Dimensions
```bash
# Test 1024d (S3 Vectors)
curl -X POST https://your-api.com/query \
  -d '{"query": "test", "dimension": 1024}'

# Test 3072d (manual search)
curl -X POST https://your-api.com/query \
  -d '{"query": "test", "dimension": 3072}'
```

Verify:
- Both return results
- 1024d is faster (native S3 Vectors)
- 3072d works but slower (manual search)

## Performance Expectations

**S3 Vectors (All Dimensions: 256d, 384d, 1024d, 3072d)**:
- Query latency: 10-100ms (higher dimensions slightly slower)
- Scales to millions of vectors
- Native similarity search
- Consistent performance across all MRL dimensions

## Migration Checklist

- [ ] Create S3 Vector bucket via CLI
- [ ] Create 4 vector indexes (256d, 384d, 1024d, 3072d)
- [ ] Update CDK stack (may need CfnResource)
- [ ] Update Store Embeddings Lambda
- [ ] Update Query Handler Lambda
- [ ] Update IAM permissions
- [ ] Deploy and test
- [ ] Verify S3 Vectors queries work for all dimensions
- [ ] Performance testing across all dimensions

## Rollback Plan

If S3 Vectors doesn't work:
1. Keep regular S3 bucket
2. Revert Lambda code to manual search
3. Works exactly as before

## Future Improvements

- Monitor S3 Vectors performance at scale
- Optimize query patterns for hierarchical search
- Consider caching frequently accessed vectors
- Add monitoring and alerting for query latency

