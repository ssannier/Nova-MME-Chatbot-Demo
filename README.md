# Nova MME Demo with Matryoshka Relational Learning

A production-ready demonstration of Amazon Nova Multimodal Embeddings (MME) showcasing Matryoshka Relational Learning (MRL) capabilities through a unified multimodal semantic search and RAG system.

## Overview

This project demonstrates:
- **Multimodal embeddings**: Text, images, video, audio, PDFs, and Word documents in a unified semantic space
- **Matryoshka Relational Learning (MRL)**: One 3072-dim embedding generates four usable dimensions (256, 384, 1024, 3072)
- **Automatic chunking**: Nova MME async API segments long-form content automatically
- **Hierarchical search**: Fast coarse search (256d) followed by precise refinement (1024d)
- **S3 Vectors integration**: Native vector search with 4 dimensional indexes
- **Multimodal RAG**: Claude analyzes actual images and PDFs, not just text descriptions
- **Document processing**: PDFs converted to images, Word docs text-extracted, all fully searchable

## Supported File Formats

### Fully Supported (Multimodal)
- **Images**: JPG, JPEG, PNG, GIF, WebP
- **PDFs**: Converted to images, full text and layout understanding
- **Word Documents**: .docx (text extraction with table support)
- **Text**: TXT, MD, JSON, CSV

### Supported for Embedding Only
- **Video**: MP4, MOV, MKV, WebM, FLV, MPEG, MPG, WMV, 3GP
- **Audio**: MP3, WAV, OGG

See [MULTIMODAL_CLAUDE_INTEGRATION.md](docs/MULTIMODAL_CLAUDE_INTEGRATION.md) for details on how each format is processed.

## Key Features

### 1. Matryoshka Relational Learning (MRL)
- **One embedding, four dimensions**: 3072 → 256, 384, 1024, 3072
- **Cost efficient**: One Nova MME invocation produces 4 usable embeddings
- **Performance tradeoffs**: Smaller dimensions = faster search, larger = more accurate
- **Hierarchical search**: Fast 256d coarse search → Precise 1024d refinement

### 2. Multimodal Document Processing
- **PDFs**: Converted to high-res images (300 DPI), each page embedded separately
- **Word Documents**: Text extracted with table support
- **Images**: Embedded with DOCUMENT_IMAGE detail level for text/diagram understanding
- **Video/Audio**: Automatic segmentation with timestamps

### 3. True Multimodal RAG
- **Claude sees actual content**: Images passed as base64, not descriptions
- **PDF pages as images**: Claude reads text and understands layout
- **Mixed modality context**: Combines images, text, video transcripts in one prompt
- **High-fidelity retrieval**: Original content preserved and passed to LLM

### 4. Multi-Page PDF Support
- **All pages processed**: Step Functions Map state tracks each page individually
- **Parallel processing**: Up to 10 pages processed concurrently
- **Individual tracking**: See status of each page in AWS Console
- **Fully searchable**: Find content from any page in the PDF

### 5. Production-Ready Infrastructure
- **Fully automated**: CDK deploys entire stack
- **Comprehensive testing**: 110+ tests with 87% coverage
- **Error handling**: Graceful degradation and detailed logging
- **Monitoring**: CloudWatch logs and metrics for all components
- **Security**: IAM roles, Secrets Manager, no hardcoded credentials

## Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    INGESTION PIPELINE                        │
└─────────────────────────────────────────────────────────────┘

User uploads file to S3
         ↓
┌────────────────────────────────────────────────────────────┐
│ Lambda 1: Processor                                         │
│ • Detects file type (image, video, audio, PDF, .docx, text)│
│ • PDFs → Convert to images (PyMuPDF)                       │
│ • .docx → Extract text (python-docx)                       │
│ • Invokes Nova MME async at 3072 dimensions                │
└────────────────────────────────────────────────────────────┘
         ↓
┌────────────────────────────────────────────────────────────┐
│ Step Functions State Machine                                │
│ • Orchestrates async job monitoring                        │
│ • For PDFs: Map state processes all pages in parallel      │
│ • Polls every 30 seconds until complete                    │
└────────────────────────────────────────────────────────────┘
         ↓
┌────────────────────────────────────────────────────────────┐
│ Lambda 2: Check Status                                      │
│ • Polls Bedrock async invocation status                    │
│ • Returns COMPLETED, FAILED, or IN_PROGRESS                │
└────────────────────────────────────────────────────────────┘
         ↓
┌────────────────────────────────────────────────────────────┐
│ Lambda 3: Store Embeddings                                  │
│ • Retrieves 3072-dim embeddings from S3                    │
│ • MRL truncation: 3072 → 256, 384, 1024, 3072             │
│ • Stores in 4 S3 Vector indexes with metadata              │
└────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    QUERY PIPELINE                            │
└─────────────────────────────────────────────────────────────┘

User asks question via frontend
         ↓
┌────────────────────────────────────────────────────────────┐
│ Lambda 4: Query Handler                                     │
│ 1. Embed query with Nova MME                               │
│ 2. Hierarchical search:                                    │
│    • Fast: 256d index (top 100)                           │
│    • Precise: 1024d index (top 5)                         │
│ 3. Fetch original content:                                 │
│    • Images → Base64 encode                               │
│    • PDFs → Fetch page images                             │
│    • Text → Fetch actual content                          │
│ 4. Pass to Claude with multimodal context                  │
│ 5. Return answer with citations                            │
└────────────────────────────────────────────────────────────┘
         ↓
┌────────────────────────────────────────────────────────────┐
│ Frontend (Next.js on Amplify)                               │
│ • Displays answer with source citations                    │
│ • Shows similarity scores and processing steps             │
│ • Allows dimension selection for MRL demo                  │
└────────────────────────────────────────────────────────────┘
```

### Key Components

#### Embedder Stack (Async Pipeline)
1. **S3 Source Bucket** - Upload files here
2. **Lambda 1 (Processor)** - Converts PDFs, extracts .docx text, invokes Nova MME
3. **Lambda 2 (Check Status)** - Polls async job status
4. **Lambda 3 (Store Embeddings)** - MRL truncation and S3 Vectors storage
5. **Step Functions** - Orchestrates the workflow with Map state for multi-page PDFs
6. **S3 Output Bucket** - Temporary storage for Nova MME async results
7. **S3 Vector Bucket** - 4 indexes (256d, 384d, 1024d, 3072d)

#### Chatbot Stack (Query Interface)
1. **Lambda 4 (Query Handler)** - Embeds query, searches, fetches content, calls Claude
2. **API Gateway** - REST API with CORS for frontend
3. **Amplify App** - Hosts Next.js frontend with auto-deploy from GitHub
4. **S3 Source Bucket** - Read access for fetching original content

### Data Flow

#### Ingestion Example: 10-Page PDF

```
1. User uploads report.pdf (10 pages)
2. Processor converts to 10 PNG images
3. Starts 10 Nova MME async jobs (one per page)
4. Step Functions Map state tracks all 10 pages
5. Each page: Wait → Check → Store (in parallel)
6. Store Embeddings creates 40 vectors (10 pages × 4 dimensions)
7. All stored in S3 Vector indexes with metadata
```

#### Query Example: "What's the architecture?"

```
1. User types question in frontend
2. Query Handler embeds at 1024d
3. Hierarchical search:
   • 256d: Fast search → 100 candidates
   • 1024d: Precise search → 5 results
4. Fetches: diagram.png, page 3 of report.pdf
5. Passes images to Claude (base64)
6. Claude analyzes images and generates answer
7. Frontend displays answer with citations
```

## Technology Stack

### AWS Services
- **Amazon Bedrock** - Nova MME (embeddings), Claude 3.5 Sonnet (LLM)
- **AWS Lambda** - 4 functions (Python 3.11)
- **AWS Step Functions** - Workflow orchestration with Map state
- **Amazon S3** - Object storage (source files, embeddings, outputs)
- **S3 Vectors** - Native vector search with 4 dimensional indexes
- **Amazon API Gateway** - REST API for frontend
- **AWS Amplify** - Frontend hosting with auto-deploy

### Libraries & Frameworks
- **Backend:** boto3, PyMuPDF (PDF conversion), python-docx (Word extraction), numpy (MRL)
- **Frontend:** Next.js 16, React 19, TypeScript, Tailwind CSS 4
- **IaC:** AWS CDK (Python)
- **Testing:** pytest (110+ tests, 87% coverage)

## Project Structure

```
/
├── app.py                          # CDK app entry point
├── cdk.json                        # CDK configuration
├── requirements.txt                # CDK dependencies
├── requirements-lambda.txt         # Lambda runtime dependencies
│
├── lib/                            # CDK Infrastructure
│   ├── embedder_stack.py          # Embedder pipeline (S3, Lambda, Step Functions)
│   └── chatbot_stack.py           # Chatbot interface (Lambda, API Gateway, Amplify)
│
├── lambda/                         # Lambda Functions
│   ├── embedder/
│   │   ├── processor/             # Lambda 1: Nova MME invocation
│   │   ├── check_status/          # Lambda 2: Poll async status
│   │   └── store_embeddings/      # Lambda 3: MRL + S3 Vectors storage
│   ├── chatbot/
│   │   └── query_handler/         # Lambda 4: Query + search + Claude
│   └── shared/
│       └── embedding_utils.py     # MRL truncation utilities
│
├── frontend/                       # Next.js Frontend
│   ├── app/                       # Pages and layouts
│   ├── components/                # React components
│   └── package.json
│
├── tests/                          # Test Suite
│   └── unit/                      # 110+ unit tests
│
├── config/                         # Configuration
│   ├── dev.json                   # Development settings
│   └── prod.json                  # Production settings
│
├── docs/                           # Documentation
│   ├── MULTIMODAL_CLAUDE_INTEGRATION.md
│   ├── PDF_MULTIPAGE_FIX.md
│   ├── OPTIMAL_MULTIMODAL_RAG_ARCHITECTURE.md
│   └── ... (more docs)
│
└── scripts/                        # Utility scripts
    └── store-github-token.*       # GitHub token management
```

See [structure.md](.kiro/steering/structure.md) for detailed project layout.

## Prerequisites

### AWS Requirements
- AWS Account with Bedrock access (Nova MME and Claude models enabled)
- AWS CLI configured with appropriate credentials
- Bedrock model access in us-east-1:
  - `amazon.nova-2-multimodal-embeddings-v1:0`
  - `anthropic.claude-3-5-sonnet-20241022-v2:0`

### Development Tools
- Python 3.11+
- Node.js 18+ (for frontend)
- AWS CDK CLI: `npm install -g aws-cdk`
- Git (for Amplify auto-deploy)

### Optional
- GitHub account (for Amplify auto-deploy)
- GitHub personal access token (stored in Secrets Manager)

## Quick Start

### 1. Clone and Install

```bash
# Clone repository
git clone <your-repo-url>
cd Nova-MME-Demo

# Install CDK dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### 2. Configure (Optional)

Edit `config/dev.json` or `config/prod.json` to customize:
- Model IDs
- Embedding dimensions
- Search parameters
- LLM settings

### 3. Bootstrap CDK (First Time Only)

```bash
# Bootstrap CDK in your AWS account
cdk bootstrap
```

### 4. Deploy Embedder Stack

```bash
# Deploy the ingestion pipeline
cdk deploy NovaMMEEmbedderStack

# Note the output:
# - SourceBucketName: Upload files here
# - VectorBucketName: Embeddings stored here
```

### 5. Deploy Chatbot Stack

```bash
# Deploy the query interface
cdk deploy NovaMMEChatbotStack

# Note the output:
# - QueryApiUrl: API Gateway endpoint
# - AmplifyAppUrl: Frontend URL (after build completes)
```

### 6. Configure Frontend

```bash
cd frontend

# Create .env.local with API URL from deployment
echo "NEXT_PUBLIC_QUERY_URL=<QueryApiUrl>" > .env.local

# Test locally (optional)
npm run dev

# Or wait for Amplify auto-deploy
```

### 7. Test the System

```bash
# Upload a test file
aws s3 cp test-document.pdf s3://<SourceBucketName>/

# Monitor Step Functions execution in AWS Console
# Wait for processing to complete (~2-5 minutes)

# Query via frontend or API
curl -X POST <QueryApiUrl> \
  -H "Content-Type: application/json" \
  -d '{"query": "What is this document about?"}'
```

## Detailed Deployment

### Option 1: Deploy Both Stacks

```bash
cdk deploy --all
```

### Option 2: Deploy Individually

```bash
# 1. Deploy embedder first (creates S3 buckets)
cdk deploy NovaMMEEmbedderStack

# 2. Deploy chatbot (references embedder resources)
cdk deploy NovaMMEChatbotStack
```

### Option 3: Deploy with GitHub Auto-Deploy

```bash
# 1. Store GitHub token in Secrets Manager
scripts/store-github-token.bat <your-github-token>

# 2. Deploy (Amplify will auto-connect to GitHub)
cdk deploy NovaMMEChatbotStack

# 3. Amplify automatically builds and deploys frontend
```

## Testing

### Run Unit Tests

```bash
# Run all tests
python -m pytest tests/unit/ -v

# Run with coverage
python -m pytest tests/unit/ --cov=lambda --cov-report=term-missing

# Run specific test file
python -m pytest tests/unit/test_query_handler_lambda.py -v

# Windows convenience script
run_tests.bat
```

### Test Coverage
- **110+ tests** across all Lambda functions
- **87% code coverage**
- Tests for all file types, error handling, and edge cases

## Monitoring

### CloudWatch Logs

Each Lambda function logs to CloudWatch:
- `/aws/lambda/NovaMMEEmbedder-Processor`
- `/aws/lambda/NovaMMEEmbedder-CheckStatus`
- `/aws/lambda/NovaMMEEmbedder-StoreEmbeddings`
- `/aws/lambda/NovaMMEChatbot-QueryHandler`

### Step Functions

Monitor executions in AWS Console:
1. Go to Step Functions
2. Select `EmbedderStateMachine`
3. View execution history
4. For PDFs: Expand Map state to see all pages

### Metrics to Watch

- **Lambda duration**: Should be <30s for most operations
- **Step Functions execution time**: 2-5 minutes for typical files
- **API Gateway latency**: 3-5 seconds for queries
- **Error rates**: Should be near 0%

## Cost Estimate

### Development/Demo Usage
- **Bedrock (Nova MME)**: ~$0.01 per file
- **Bedrock (Claude)**: ~$0.01 per query
- **Lambda**: ~$0.001 per execution
- **S3**: ~$0.023 per GB/month
- **S3 Vectors**: ~$0.30 per million vectors/month
- **Step Functions**: ~$0.025 per 1000 state transitions
- **API Gateway**: ~$3.50 per million requests
- **Amplify**: ~$0.01 per build minute + $0.15 per GB served

**Estimated monthly cost for demo:** $50-100

### Production Usage (1000 files, 10000 queries/month)
- **Bedrock**: ~$100
- **Lambda**: ~$10
- **S3 + S3 Vectors**: ~$50
- **Other services**: ~$20

**Estimated monthly cost:** $180-250

## Troubleshooting

### Common Issues

**1. Bedrock Model Access**
```
Error: Could not access model
Solution: Request model access in Bedrock console
```

**2. Step Functions Timeout**
```
Error: Execution timed out
Solution: Increase timeout in lib/embedder_stack.py
```

**3. S3 Vectors Not Found**
```
Error: Index not found
Solution: Ensure embedder stack deployed successfully
```

**4. Frontend Can't Connect**
```
Error: Network error
Solution: Check NEXT_PUBLIC_QUERY_URL in .env.local
```

### Debug Mode

Enable verbose logging:
```python
# In Lambda functions
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Documentation

### Architecture & Design
- [OPTIMAL_MULTIMODAL_RAG_ARCHITECTURE.md](docs/OPTIMAL_MULTIMODAL_RAG_ARCHITECTURE.md) - Production architecture guide
- [MULTIMODAL_CLAUDE_INTEGRATION.md](docs/MULTIMODAL_CLAUDE_INTEGRATION.md) - How multimodal content is passed to Claude
- [PDF_MULTIPAGE_FIX.md](docs/PDF_MULTIPAGE_FIX.md) - Multi-page PDF processing implementation

### Implementation Details
- [DOCX_TEXT_EXTRACTION.md](docs/DOCX_TEXT_EXTRACTION.md) - Word document processing
- [S3_VECTORS_IMPLEMENTATION.md](docs/S3_VECTORS_IMPLEMENTATION.md) - S3 Vectors integration
- [VECTOR_STORAGE_ALTERNATIVES.md](docs/VECTOR_STORAGE_ALTERNATIVES.md) - Comparison of vector storage options

### Operations
- [DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) - Detailed deployment instructions
- [SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md) - Security review and recommendations

## Contributing

### Code Style
- Python: PEP 8
- TypeScript: ESLint configuration
- Use type hints where helpful

### Testing
- Add tests for new features
- Maintain >85% coverage
- Run tests before committing

### Documentation
- Update README for major changes
- Add inline comments for complex logic
- Create docs for new features

## License

[Your License Here]

## Acknowledgments

- Amazon Bedrock team for Nova MME and Claude models
- AWS CDK team for infrastructure-as-code framework
- Community contributors to python-docx, PyMuPDF, and other libraries

## Support

For issues or questions:
1. Check [Troubleshooting](#troubleshooting) section
2. Review [Documentation](#documentation)
3. Open an issue on GitHub
4. Contact: [Your Contact Info]
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
