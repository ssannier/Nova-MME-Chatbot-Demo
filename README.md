# Nova MME Demo with Matryoshka Relational Learning

A demonstration of Amazon Nova Multimodal Embeddings (MME) showcasing Matryoshka Relational Learning (MRL) capabilities through a unified multimodal semantic search system.

## Overview

This project demonstrates:
- **Multimodal embeddings**: Text, images, video, audio, and documents in a unified semantic space
- **Matryoshka Relational Learning**: One 3072-dim embedding generates four usable dimensions (256, 384, 1024, 3072)
- **Automatic chunking**: Async API segments long-form content automatically
- **Hierarchical search**: Fast coarse search followed by precise refinement
- **S3 Vector integration**: Multiple dimension indexes for performance/accuracy tradeoffs

## Architecture

The project consists of two main components:

### Embedder (Async Pipeline)
1. Files uploaded to S3 trigger processing
2. Lambda invokes Nova MME at 3072 dimensions
3. Step Functions orchestrates job monitoring
4. Embeddings are truncated to 256, 384, 1024, and 3072 dimensions
5. All variants stored in S3 Vector indexes with rich metadata

### Chatbot (Query Interface)
1. User queries through Amplify frontend
2. Query embedded and searched across dimension indexes
3. Optional hierarchical search for efficiency
4. Results passed to Claude for response generation

## Project Structure

See [CDKStructure.md](docs/improved/CDKStructure.md) for detailed project layout.

## Prerequisites

- AWS Account with Bedrock access
- Python 3.11+
- Node.js 18+ (for frontend)
- AWS CDK CLI
- AWS CLI configured

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Bootstrap CDK (first time only):**
   ```bash
   cdk bootstrap
   ```

3. **Deploy infrastructure:**
   ```bash
   cdk deploy --all
   ```

4. **Upload test files:**
   ```bash
   python scripts/upload_test_files.py
   ```

## Configuration

Edit `config/dev.json` or `config/prod.json` to customize:
- Embedding dimensions to use
- Number of search results (k)
- Enable/disable hierarchical search
- S3 bucket names

## Documentation

- [Improved Structure](docs/improved/improvedStructure.md) - Detailed architecture
- [Demo Suggestions](docs/improved/demoSuggestions.md) - MRL demonstration ideas
- [CDK Structure](docs/improved/CDKStructure.md) - Project organization

## License

MIT
