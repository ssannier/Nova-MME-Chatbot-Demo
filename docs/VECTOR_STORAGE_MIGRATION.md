# Vector Storage Migration Plan

## Current State

**Implementation**: Custom S3 + Lambda vector search
- Embeddings stored as JSON files in S3
- Lambda reads all files and calculates cosine similarity manually
- Works but not scalable or performant

**Issues**:
- No actual vector indexes
- Linear search through all embeddings (O(n) complexity)
- High latency for large datasets
- No optimized similarity search

## Migration Options

### Option 1: S3 Vectors (Recommended - Preview)

**Pros**:
- ✅ Native S3 integration (no separate database)
- ✅ Built on S3 Tables with Apache Iceberg
- ✅ Native vector similarity search
- ✅ Supports multiple dimensions (4 separate tables)
- ✅ Scalable and cost-effective
- ✅ Metadata stored alongside vectors

**Cons**:
- ⚠️ Currently in preview (not GA yet)
- ⚠️ Limited CDK support (may need CloudFormation)
- ⚠️ Documentation still evolving
- ⚠️ Need to test with Nova MME embeddings

**Architecture**:
```
S3 Upload → Lambda → Nova MME → Lambda → S3 Tables (4 tables for 4 dimensions)
Query → Lambda → Nova MME → Lambda → S3 Vectors Query → Claude → Response
```

**CDK Support**: ⚠️ Limited - May need `CfnResource` for S3 Tables

### Option 2: OpenSearch Serverless with Vector Engine

**Pros**:
- ✅ Purpose-built for vector search
- ✅ Supports multiple dimensions (can create 4 indexes)
- ✅ Fast k-NN search with HNSW algorithm
- ✅ Full control over indexing and search

**Cons**:
- ⚠️ More infrastructure to manage
- ⚠️ Higher cost than S3
- ⚠️ Requires custom integration code

**Architecture**:
```
S3 Upload → Lambda → Nova MME → Lambda → OpenSearch Index
Query → Lambda → Nova MME → Lambda → OpenSearch Search → Claude → Response
```

**CDK Support**: ✅ Yes - `aws_opensearchserverless.CfnCollection`

### Option 3: Keep Custom S3 Implementation (Current)

**Pros**:
- ✅ Already implemented
- ✅ Simple architecture
- ✅ Low cost (just S3 + Lambda)
- ✅ Full control

**Cons**:
- ❌ Not scalable
- ❌ Slow for large datasets
- ❌ Manual vector search implementation
- ❌ Not production-ready

**When to use**: Demos, prototypes, small datasets (<1000 embeddings)

## Recommended Path Forward

### Phase 1: Research & Validation (Current)
1. ✅ Document current implementation
2. ⏳ Research S3 Vectors preview access and API
3. ⏳ Test S3 Tables with vector columns
4. ⏳ Verify compatibility with Nova MME embeddings and MRL

### Phase 2: Proof of Concept
1. Create small test with Bedrock Knowledge Bases
2. Upload sample files and verify chunking behavior
3. Test query performance and accuracy
4. Compare with current implementation

### Phase 3: Migration Decision
**If S3 Vectors is accessible and works with Nova MME**:
- Migrate to S3 Vectors (best fit for architecture)
- Create 4 S3 Tables (one per dimension)
- Update Store Embeddings Lambda to write to S3 Tables
- Update Query Handler Lambda to use S3 Vectors query API

**If S3 Vectors not ready**:
- Migrate to OpenSearch Serverless (proven technology)
- Keep current embedding pipeline
- Replace search logic with OpenSearch queries

### Phase 4: Implementation
1. Update CDK stack with vector store
2. Modify Store Embeddings Lambda to write to vector store
3. Modify Query Handler Lambda to search vector store
4. Test end-to-end
5. Performance tuning

### Phase 5: Cleanup
1. Remove old S3-based search code
2. Update documentation
3. Update architecture diagrams

## Migration Complexity Estimate

**S3 Vectors**: 🟡 Medium (3-5 days)
- Preview service - may have rough edges
- Need to learn S3 Tables + Iceberg format
- Update Lambda code for S3 Tables API
- Create 4 tables for 4 dimensions
- Test and validate performance

**OpenSearch Serverless**: 🟡 Medium (5-7 days)
- Proven technology
- New infrastructure to set up
- Custom indexing and search code
- Performance tuning required

**Keep Current**: 🟢 Low (0 days)
- Already working
- Just fix URL encoding bug
- Good enough for demo

## Immediate Action Items

1. **Fix URL encoding bug** (blocking current demo)
   - Add `unquote_plus` to processor Lambda
   - Deploy and test with PDF

2. **Research Knowledge Bases**
   - Check Nova MME support in AWS docs
   - Test with sample data
   - Document findings

3. **Update TODO.md**
   - Add vector storage migration task
   - Mark as post-demo enhancement

4. **Demo with current implementation**
   - Works for small datasets
   - Demonstrates MRL concept
   - Can migrate later

## Decision Matrix

| Criteria | Current S3 | S3 Vectors | OpenSearch |
|----------|-----------|------------|------------|
| Setup Time | ✅ Done | 🟡 3-5 days | 🔴 5-7 days |
| Cost | ✅ Very Low | ✅ Low | 🔴 High |
| Performance | 🔴 Slow | ✅ Fast | ✅ Very Fast |
| Scalability | 🔴 Poor | ✅ Excellent | ✅ Excellent |
| Control | ✅ Full | ✅ Full | ✅ Full |
| Maintenance | ✅ Low | ✅ Low | 🟡 Medium |
| MRL Support | ✅ Yes | ✅ Yes | ✅ Yes |
| Maturity | ✅ Stable | ⚠️ Preview | ✅ GA |

## Recommendation

**For Demo**: Keep current S3 implementation
- Fix URL encoding bug
- Test with sample files
- Demonstrate MRL concept
- Works for small datasets

**For Production**: Migrate to S3 Vectors (when GA)
- Perfect fit for architecture (already using S3)
- Native vector search capabilities
- Cost-effective and scalable
- Supports MRL with 4 separate tables
- Worth waiting for GA release

**Alternative**: OpenSearch Serverless (if S3 Vectors not ready)
- Proven technology available now
- Excellent performance and scalability
- More complex setup but battle-tested

## Next Steps

1. ✅ Fix URL encoding bug and complete demo
2. ⏳ Request S3 Vectors preview access
3. ⏳ Test S3 Tables with vector columns and Nova MME embeddings
4. ⏳ Evaluate S3 Vectors vs OpenSearch Serverless
5. ⏳ Make migration decision based on findings
6. ⏳ Schedule migration for post-demo

