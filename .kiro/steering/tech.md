# Technology Stack

## Infrastructure

**IaC Framework**: AWS CDK (Python)
**Cloud Provider**: AWS
**Deployment Region**: us-east-1 (default)

## Backend

**Runtime**: Python 3.11
**Lambda Functions**: 4 functions (processor, check_status, store_embeddings, query_handler)
**Orchestration**: AWS Step Functions
**Storage**: S3 (source files, embeddings, async outputs)
**Vector Search**: S3 Vectors with 4 indexes (256d, 384d, 1024d, 3072d)
**API**: API Gateway REST API with CORS

## AI/ML Services

**Embedding Model**: amazon.nova-2-multimodal-embeddings-v1:0
**LLM**: anthropic.claude-3-5-sonnet-20241022-v2:0 (dev), claude-4-5-sonnet (prod planned)
**Bedrock APIs**: Async invocation for embeddings, synchronous for queries and LLM

## Frontend

**Framework**: Next.js 16.0.2
**Language**: TypeScript 5
**UI**: React 19.2.0, Tailwind CSS 4
**Hosting**: AWS Amplify (auto-deploy from GitHub)

## Key Libraries

**Backend**: boto3 (AWS SDK), numpy (MRL truncation/normalization)
**Frontend**: next, react, react-dom, tailwindcss

## Common Commands

### Testing
```bash
# Run all unit tests
python -m pytest tests/unit/ -v

# Run with coverage
python -m pytest tests/unit/ --cov=lambda --cov-report=term-missing

# Windows batch script
run_tests.bat

# Unix shell script
./run_tests.sh
```

### Deployment
```bash
# Install CDK dependencies
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy embedder stack
cdk deploy NovaMMEEmbedderStack

# Deploy chatbot stack
cdk deploy NovaMMEChatbotStack

# Deploy all stacks
cdk deploy --all

# Destroy stacks
cdk destroy --all
```

### Frontend Development
```bash
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Lint code
npm run lint
```

### Configuration Management
```bash
# Store GitHub token for Amplify
scripts/store-github-token.bat <token>  # Windows
./scripts/store-github-token.sh <token>  # Unix
```

## Environment Variables

### Lambda (Embedder)
- `EMBEDDING_DIMENSION`: Always 3072 (max for MRL)
- `MODEL_ID`: Nova MME model identifier
- `OUTPUT_BUCKET`: S3 bucket for async job outputs
- `SOURCE_BUCKET`: S3 bucket for source files
- `VECTOR_BUCKET`: S3 bucket for embeddings
- `EMBEDDING_DIMENSIONS`: Comma-separated list (256,384,1024,3072)

### Lambda (Chatbot)
- `VECTOR_BUCKET`: S3 bucket for embeddings
- `EMBEDDING_MODEL_ID`: Nova MME model identifier
- `LLM_MODEL_ID`: Claude model identifier
- `LLM_REGION`: Region for LLM inference
- `DEFAULT_DIMENSION`: Default query dimension (1024)
- `DEFAULT_K`: Number of search results (5)
- `HIERARCHICAL_ENABLED`: Enable hierarchical search (true/false)
- `HIERARCHICAL_CONFIG`: JSON config for hierarchical search
- `VECTOR_INDEXES`: JSON mapping of dimensions to index names
- `LLM_MAX_TOKENS`: Max tokens for Claude (2048)
- `LLM_TEMPERATURE`: Temperature for Claude (0.7)

### Frontend
- `NEXT_PUBLIC_QUERY_URL`: API Gateway endpoint URL

## Configuration Files

- `config/dev.json`: Development environment settings
- `config/prod.json`: Production environment settings
- `cdk.json`: CDK app configuration
- `frontend/.env.local`: Frontend environment variables (not committed)
