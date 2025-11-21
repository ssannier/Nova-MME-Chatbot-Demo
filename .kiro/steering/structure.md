# Project Structure

## Root Directory

```
/
├── app.py                    # CDK app entry point
├── cdk.json                  # CDK configuration
├── requirements.txt          # CDK dependencies
├── requirements-lambda.txt   # Lambda runtime dependencies
├── pytest.ini               # Pytest configuration
├── TODO.md                  # Project task tracking
└── README.md                # Project documentation
```

## Infrastructure (CDK)

```
lib/
├── embedder_stack.py        # Embedder pipeline stack (S3, Lambda, Step Functions)
├── chatbot_stack.py         # Chatbot interface stack (Lambda, API Gateway, Amplify)
└── __init__.py
```

**Stack Dependencies**: ChatbotStack depends on EmbedderStack (references S3 buckets and vector indexes)

## Lambda Functions

```
lambda/
├── embedder/
│   ├── processor/           # Lambda 1: Nova MME async invocation
│   │   ├── index.py
│   │   └── requirements.txt
│   ├── check_status/        # Lambda 2: Poll async job status
│   │   ├── index.py
│   │   └── requirements.txt
│   └── store_embeddings/    # Lambda 3: MRL truncation + S3 Vector storage
│       ├── index.py
│       └── requirements.txt
├── chatbot/
│   └── query_handler/       # Lambda 4: Query embedding + search + LLM
│       ├── index.py
│       └── requirements.txt
└── shared/
    ├── embedding_utils.py   # MRL truncation/normalization utilities
    └── __init__.py
```

**Lambda Packaging**: Each Lambda has its own directory with `index.py` (handler) and `requirements.txt`

**Shared Code**: `lambda/shared/` contains utilities used across multiple Lambdas

## Frontend

```
frontend/
├── app/
│   ├── page.tsx             # Main page component
│   ├── layout.tsx           # Root layout
│   ├── globals.css          # Global styles
│   └── favicon.ico
├── components/
│   ├── ChatWindow.tsx       # Chat interface with message history
│   └── QueryInterface.tsx   # Query input and controls
├── package.json
├── tsconfig.json
├── next.config.ts
├── eslint.config.mjs
├── postcss.config.mjs
└── .env.local               # Environment variables (not committed)
```

**Frontend Deployment**: Hosted on AWS Amplify with auto-deploy from GitHub

## Tests

```
tests/
├── unit/
│   ├── test_processor_lambda.py          # Lambda 1 tests
│   ├── test_check_status_lambda.py       # Lambda 2 tests
│   ├── test_store_embeddings_lambda.py   # Lambda 3 tests
│   ├── test_query_handler_lambda.py      # Lambda 4 tests
│   ├── test_embedding_utils.py           # Shared utilities tests
│   ├── test_model_input_schema.py        # Nova MME schema validation
│   └── __init__.py
├── integration/                           # (Empty - future integration tests)
├── requirements.txt                       # Test dependencies
└── README.md                             # Test documentation
```

**Test Coverage**: 107+ tests with 94% code coverage

**Test Execution**: Use `pytest` or convenience scripts (`run_tests.bat`, `run_tests.sh`)

## Configuration

```
config/
├── constants.py             # Shared constants
├── dev.json                 # Development environment config
└── prod.json                # Production environment config
```

**Config Loading**: CDK stacks load config based on `environment` context parameter (defaults to `dev`)

## Documentation

```
docs/
├── initial/                 # Original project documentation
│   ├── architecture-diagram.png
│   ├── novaMMEAsyncDocs.md
│   ├── novaMMESyncDocs.md
│   └── structure.md
├── improved/                # Updated documentation
│   ├── CDKStructure.md
│   ├── improvedStructure.md
│   ├── demoSuggestions.md
│   ├── chunkTruncationLogic.py
│   ├── lambda1MetadataLogic.py
│   └── lambda3MetadataLogic.py
├── AMPLIFY_SETUP.md         # Amplify deployment guide
├── AMPLIFY_NEXTJS_TEMPLATE.md  # Next.js template reference
├── ARCHITECTURE_DECISIONS.md   # Key architectural decisions
├── CORS_AND_CONTENT_EXPLAINED.md  # CORS and content retrieval
├── DEPLOYMENT_GUIDE.md      # Step-by-step deployment
├── EMBEDDER_SUMMARY.md      # Embedder pipeline documentation
└── PROJECT_STATUS.md        # Current project status
```

## Scripts

```
scripts/
├── store-github-token.bat   # Windows script to store GitHub token
└── store-github-token.sh    # Unix script to store GitHub token
```

## Generated/Build Artifacts

```
cdk.out/                     # CDK synthesized CloudFormation templates
frontend/.next/              # Next.js build output
frontend/node_modules/       # Frontend dependencies
**/__pycache__/              # Python bytecode cache
.pytest_cache/               # Pytest cache
.coverage                    # Coverage report
```

**Git Ignore**: Build artifacts, dependencies, and environment files are excluded from version control

## Key Conventions

**Python Style**: Follow PEP 8, use type hints where helpful

**Lambda Handlers**: Always named `handler(event, context)`

**Error Handling**: Log errors with `print()` (CloudWatch Logs), return structured error responses

**Environment Variables**: Required vars raise errors if missing; optional vars have defaults

**CDK Naming**: Stack names use PascalCase with "Stack" suffix; construct IDs use PascalCase

**Frontend Components**: Use TypeScript, functional components with hooks

**API Responses**: Always include CORS headers, return JSON with consistent structure

**Testing**: Mock AWS services (boto3 clients), test all file types and error paths
