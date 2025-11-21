# Architecture Decisions - Nova MME Demo

This document explains key architectural decisions made for the Nova MME demo project.

---

## Decision 1: S3 Vector vs Bedrock Knowledge Bases

### Context

AWS offers two approaches for vector-based RAG:
1. **Bedrock Knowledge Bases** - Managed RAG service
2. **S3 Vector + Custom Logic** - Direct vector storage and search

### Decision: Use S3 Vector with Custom Logic ✅

### Rationale

#### Why S3 Vector is Better for This Demo:

**1. Explicit MRL Demonstration**
- Our approach shows: **One 3072-dim invocation → Four usable embeddings**
- We explicitly truncate and store all dimension variants
- This demonstrates the MRL efficiency benefit clearly
- Knowledge Bases would hide this process

**2. Multimodal Support**
- We process text, images, video, and audio in a unified semantic space
- Knowledge Bases traditionally focus on text/documents
- Nova MME's multimodal capabilities are a key feature to showcase

**3. Educational Value**
- Shows how embeddings, chunking, and storage work under the hood
- Demonstrates Step Functions orchestration
- Illustrates metadata flow through the pipeline
- Better for understanding the technology

**4. Flexibility**
- Custom hierarchical search (256-dim → 1024-dim)
- Multiple dimension indexes for comparison
- Rich metadata storage and retrieval
- Configurable search strategies

**5. Research/Demo Purpose**
- This is a demonstration project, not production
- Goal is to showcase Nova MME and MRL capabilities
- Transparency is more valuable than convenience

#### When Knowledge Bases Would Be Better:

**For Production Applications:**
- ✅ Text-only RAG (documents, articles, FAQs)
- ✅ Want managed service (less maintenance)
- ✅ Standard document processing is sufficient
- ✅ Don't need to demonstrate MRL explicitly
- ✅ Faster time to market

**Example Use Cases:**
- Customer support chatbot (text documents)
- Internal documentation search
- FAQ systems
- Standard enterprise RAG

### Current Status of Nova MME + Knowledge Bases

**As of project creation (Nov 2024):**
- Nova MME is newly released
- Knowledge Base integration status: **Unknown/Unconfirmed**
- May be in preview or not yet available
- Traditional Knowledge Bases use Titan/Cohere embeddings (text-only)

**Action Item**: Research current integration status before production deployment.

### Trade-offs Summary

| Aspect | S3 Vector (Our Choice) | Knowledge Bases |
|--------|------------------------|-----------------|
| **MRL Demo** | ✅ Explicit, visible | ❌ Hidden/automatic |
| **Multimodal** | ✅ Full support | ❓ Limited/unknown |
| **Control** | ✅ Complete | ❌ Limited |
| **Maintenance** | ❌ More code | ✅ Managed service |
| **Setup Time** | ❌ Longer | ✅ Faster |
| **Customization** | ✅ Unlimited | ❌ Constrained |
| **Demo Value** | ✅ Educational | ❌ Black box |

---

## Decision 2: Automatic Chunking (Nova MME) vs Manual Chunking

### Context

Long content (videos, documents) needs to be split into chunks for embedding.

### Decision: Use Nova MME's Automatic Chunking ✅

### Rationale

**What We Do:**
- Upload full files to S3
- Nova MME async API automatically chunks:
  - **Text**: 32,000 character segments (configurable)
  - **Video**: 5-second segments (configurable)
  - **Audio**: 5-second segments (configurable)
- We receive pre-chunked embeddings in JSONL files

**What We DON'T Do:**
- ❌ No manual pre-processing of files
- ❌ No custom chunking logic
- ❌ No splitting files before upload

**Why This is Better:**

1. **Leverages Nova MME's Intelligence**
   - Model knows optimal chunk boundaries
   - Text chunked at word boundaries (not mid-word)
   - Video/audio chunked at scene/silence boundaries (likely)

2. **Simpler Code**
   - No chunking logic to write or maintain
   - No edge cases to handle (overlapping chunks, etc.)
   - Just process what Nova MME returns

3. **Demonstrates API Capability**
   - Shows that Nova MME async API handles segmentation
   - This is a key feature of the async API

4. **Metadata Preservation**
   - Nova MME provides segment metadata (timestamps, positions)
   - We preserve this in our storage
   - Enables temporal/spatial navigation

**Our "Manual" Work:**
- ✅ Parse the JSONL output files
- ✅ Process each chunk's embedding
- ✅ Store with metadata

This is **handling** the chunks, not **creating** them. Nova MME does the chunking!

### Clarification

**Automatic Chunking (Nova MME):**
```
Upload: video.mp4 (60 seconds)
         ↓
Nova MME: Automatically chunks into 12 segments (5s each)
         ↓
Output: 12 embeddings in embedding-video.jsonl
         ↓
Lambda 3: Processes each of the 12 embeddings
```

**Manual Chunking (What we DON'T do):**
```
Upload: video.mp4 (60 seconds)
         ↓
Custom Code: Split into 12 segments manually
         ↓
Upload: 12 separate files to S3
         ↓
Nova MME: Process each file separately
```

### Benefits of Nova MME's Chunking

1. **Intelligent Boundaries** - Chunks at natural breakpoints
2. **Consistent Metadata** - Standardized segment information
3. **Optimized for Model** - Chunks sized for optimal embedding quality
4. **Less Code** - We don't implement chunking logic

---

## Decision 3: CDK in Python vs TypeScript

### Decision: Use Python ✅

### Rationale

**Consistency:**
- Lambda functions: Python
- CDK infrastructure: Python
- Tests: Python (pytest)
- One language throughout

**Team Fit:**
- ML/data science focus
- Python is primary language
- Simpler for data teams to understand

**Trade-offs:**
- TypeScript has better IDE support
- TypeScript has more community examples
- But Python is perfectly capable and well-supported

---

## Decision 4: Single Project vs Separate Repositories

### Decision: Single CDK Project with Multiple Stacks ✅

### Rationale

**Structure:**
```
nova-mme-demo/
├── lib/
│   ├── embedder_stack.py
│   └── chatbot_stack.py
└── lambda/
    ├── embedder/
    └── chatbot/
```

**Benefits:**
- ✅ Shared configuration
- ✅ Easy cross-stack references
- ✅ Single deployment command
- ✅ Better for demos (one repo to share)

**Independent Deployment:**
- Can still deploy stacks separately
- `cdk deploy NovaMMEEmbedderStack`
- `cdk deploy NovaMMEChatbotStack`

---

## Decision 5: Step Functions Defined in CDK vs JSON

### Decision: Define in CDK Code ✅

### Rationale

**Modern Approach:**
```python
definition = (
    process_task.next(wait_state)
    .next(check_status_task)
    .next(sfn.Choice(self, "JobComplete?")...)
)
```

**Benefits:**
- ✅ Type-safe
- ✅ Co-located with Lambda definitions
- ✅ No separate JSON file to maintain
- ✅ Direct Lambda references

**Alternative (Not Used):**
- Separate `stepfunctions/workflow.json` file
- More verbose, harder to maintain

---

## Decision 6: Always Invoke at 3072 Dimensions

### Decision: Always Use Maximum Dimension (3072) ✅

### Rationale

**MRL Efficiency:**
- One 3072-dim invocation contains all lower dimensions
- Client-side truncation creates 256, 384, 1024 variants
- **Cost savings**: ~75% vs invoking at each dimension separately

**Demonstration Value:**
- Shows MRL benefit explicitly
- Proves that embeddings are nested
- Highlights cost/performance optimization

**Trade-off:**
- Slightly higher cost per invocation than 256-dim
- But much cheaper than 4 separate invocations
- Storage cost increases (4× embeddings stored)

---

## Summary for Presentation

### Key Points to Highlight:

1. **S3 Vector Choice**: Enables explicit MRL demonstration and multimodal support
2. **Automatic Chunking**: Leverages Nova MME's intelligent segmentation
3. **Python CDK**: Consistency across infrastructure and application code
4. **MRL Implementation**: One invocation → four embeddings (cost efficiency)
5. **Content Retrieval**: Claude gets actual text content for informed answers

### Questions to Anticipate:

**Q: Why not use Knowledge Bases?**
A: We wanted to explicitly demonstrate MRL and support multimodal content. Knowledge Bases may not support Nova MME yet, and would hide the MRL process.

**Q: Why Python instead of TypeScript for CDK?**
A: Consistency with Lambda functions and better fit for ML/data teams.

**Q: How do you handle chunking?**
A: Nova MME's async API automatically chunks content intelligently. We process the resulting chunks, but don't create them manually.

**Q: Why always use 3072 dimensions?**
A: MRL efficiency - one invocation generates all four dimension variants through client-side truncation. This is ~75% cheaper than separate invocations.

---

## Future Considerations

1. **Monitor Nova MME + Knowledge Base integration** - May become available
2. **Evaluate managed vs custom** - For production deployments
3. **Hybrid approach** - Knowledge Bases for text, custom for multimodal
4. **Cost analysis** - Compare approaches at scale

---

**Document Version**: 1.0
**Last Updated**: November 2024
**Status**: Decisions finalized, ready for implementation
