# Product Overview

## Nova MME Demo with Matryoshka Relational Learning

A demonstration of Amazon Nova Multimodal Embeddings (MME) showcasing Matryoshka Relational Learning (MRL) capabilities through a unified multimodal semantic search system.

## Core Features

**Multimodal Embeddings**: Unified semantic space for text, images, video, audio, and documents

**Matryoshka Relational Learning (MRL)**: One 3072-dimension embedding generates four usable dimensions (256, 384, 1024, 3072) through client-side truncation and renormalization

**Automatic Chunking**: Nova MME async API segments long-form content automatically

**Hierarchical Search**: Fast coarse search (256-dim) followed by precise refinement (1024-dim)

**Intelligent Content Retrieval**: Text sources include actual content; media sources include descriptive metadata with S3 URIs

## Architecture Components

### Embedder Pipeline (Async)
S3 upload triggers Lambda processor → Nova MME async invocation at 3072-dim → Step Functions orchestrates job monitoring → Store embeddings Lambda truncates to 256/384/1024/3072 dimensions → All variants stored in S3 Vector indexes with rich metadata

### Chatbot Interface (Query)
User query → Frontend → API Gateway → Query Handler Lambda → Nova MME embeds query → S3 Vector search → S3 source content retrieval → Claude generates response → Frontend displays answer with sources

## Key Value Propositions

- **Cost Efficiency**: One embedding invocation produces four usable dimensions
- **Performance Tradeoffs**: Demonstrate speed vs accuracy with different dimensions
- **Unified Semantic Space**: Search across all modalities with a single query
- **Segment-Aware**: Retrieves specific portions of chunked content
