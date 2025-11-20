# Nova MME Demo - CDK Project Structure

## Project Layout

```
nova-mme-demo/
├── README.md
├── cdk.json                          # CDK configuration
├── app.py                            # CDK app entry point
├── requirements.txt                  # Python dependencies for CDK
├── requirements-lambda.txt           # Python dependencies for Lambda functions
│
├── lib/                              # CDK stack definitions
│   ├── __init__.py
│   ├── embedder_stack.py            # Embedder infrastructure stack
│   └── chatbot_stack.py             # Chatbot infrastructure stack
│
├── lambda/                           # Lambda function code
│   ├── shared/                       # Shared utilities across Lambdas
│   │   ├── __init__.py
│   │   ├── bedrock_client.py        # Bedrock API wrapper
│   │   ├── s3_vector_client.py      # S3 Vector API wrapper
│   │   └── embedding_utils.py       # Truncation/normalization functions
│   │
│   ├── embedder/
│   │   ├── processor/               # Lambda 1: Nova MME Processor
│   │   │   ├── index.py
│   │   │   ├── requirements.txt
│   │   │   └── config.py            # Dimension settings, etc.
│   │   │
│   │   ├── check_status/            # Lambda 2: Check Job Status
│   │   │   ├── index.py
│   │   │   └── requirements.txt
│   │   │
│   │   └── store_embeddings/        # Lambda 3: Store Embeddings
│   │       ├── index.py
│   │       ├── requirements.txt
│   │       └── truncation.py        # MRL truncation logic
│   │
│   └── chatbot/
│       └── query_handler/           # Lambda: Query Handler
│           ├── index.py
│           ├── requirements.txt
│           └── search_strategies.py # Hierarchical search logic
│

├── frontend/                         # Amplify frontend
│   ├── package.json
│   ├── public/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── ChatInterface.jsx
│   │   │   ├── DimensionSelector.jsx
│   │   │   ├── ComparisonView.jsx
│   │   │   └── MetricsDisplay.jsx
│   │   └── api/
│   │       └── chatbot.js           # API Gateway client
│   └── amplify/
│       └── backend-config.json
│
├── config/                           # Configuration files
│   ├── dev.json                     # Dev environment config
│   ├── prod.json                    # Prod environment config
│   └── constants.py                 # Shared constants
│
├── tests/                            # Tests
│   ├── unit/
│   │   ├── test_embedder_stack.py
│   │   ├── test_chatbot_stack.py
│   │   └── test_lambda_functions.py
│   └── integration/
│       ├── test_embedder_workflow.py
│       └── test_end_to_end.py
│
├── scripts/                          # Utility scripts
│   ├── upload_test_files.py         # Upload sample files to S3
│   ├── validate_mrl.py              # Validate MRL nesting property
│   └── cleanup.py                   # Clean up resources
│
└── docs/                             # Documentation
    ├── architecture-diagram.png
    ├── improvedStructure.md
    ├── demoSuggestions.md
    └── deployment.md
```

## Key Files Explained

### Root Level

**app.py** - CDK application entry point
- Instantiates both stacks
- Passes shared resources between stacks
- Sets environment and account configuration

**cdk.json** - CDK toolkit configuration
- Defines app command
- Feature flags
- Context values

**requirements.txt** - CDK dependencies
```
aws-cdk-lib>=2.100.0
constructs>=10.0.0
```

**requirements-lambda.txt** - Lambda runtime dependencies
```
boto3>=1.28.0
numpy>=1.24.0
```

### lib/ - CDK Stacks

**embedder_stack.py** - Defines:
- S3 bucket for input files (cic-multimedia-test)
- S3 Vector bucket with 4 indexes (256d, 384d, 1024d, 3072d)
- Three Lambda functions (processor, check_status, store_embeddings)
- Step Functions state machine (defined in CDK code, not separate JSON)
- S3 event trigger for processor Lambda
- IAM roles and permissions (Bedrock, S3, S3 Vector)

**Note**: The Step Functions state machine is defined directly in CDK code using the `_create_state_machine()` method. This is cleaner than maintaining a separate JSON file and allows for type-safe Lambda references.

**chatbot_stack.py** - Defines:
- Query handler Lambda
- API Gateway REST API
- Amplify app hosting
- IAM roles for Bedrock and S3 Vector access
- Takes S3 Vector bucket as input from embedder stack

### lambda/ - Function Code

**shared/** - Common utilities:
- Bedrock client wrapper for consistent API calls
- S3 Vector client for index operations
- Embedding truncation and normalization functions
- Shared across all Lambda functions

**embedder/** - Three Lambda functions:
- Each has its own `index.py` (handler)
- Separate `requirements.txt` for function-specific dependencies
- Configuration files for easy parameter changes

**chatbot/** - Query handler:
- Single Lambda handling the full query pipeline
- Modular search strategies (simple, hierarchical, comparison)

### frontend/ - Amplify App

Standard React/Vue/Angular structure:
- Chat interface component
- Dimension selector for MRL demonstration
- Side-by-side comparison view
- Performance metrics display
- API Gateway integration

### config/

**Environment-specific configurations:**
- Dimension settings (which dimensions to use)
- Number of results (k value)
- S3 bucket names
- Region settings
- Feature flags (enable/disable hierarchical search, comparison mode)

### tests/

**unit/** - Test individual components:
- Stack synthesis tests
- Lambda function logic tests
- Utility function tests

**integration/** - Test workflows:
- End-to-end embedder workflow
- Query handler with mock data
- Cross-stack integration

### scripts/

**Utility scripts for demo:**
- Upload sample files (one of each type)
- Validate MRL property (compare truncated vs native embeddings)
- Cleanup resources after demo

## Deployment Flow

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Bootstrap CDK (first time only):**
   ```bash
   cdk bootstrap
   ```

3. **Deploy embedder stack:**
   ```bash
   cdk deploy NovaMMEEmbedderStack
   ```

4. **Deploy chatbot stack:**
   ```bash
   cdk deploy NovaMMEChatbotStack
   ```

5. **Or deploy both:**
   ```bash
   cdk deploy --all
   ```

6. **Upload test files:**
   ```bash
   python scripts/upload_test_files.py
   ```

## Configuration Management

**Environment variables in Lambda functions:**
- `EMBEDDING_DIMENSIONS`: "256,384,1024,3072"
- `VECTOR_BUCKET_NAME`: S3 Vector bucket name
- `SOURCE_BUCKET_NAME`: Input files bucket
- `MAX_RESULTS`: Default k value for queries
- `ENABLE_HIERARCHICAL_SEARCH`: "true"/"false"

**Passed via CDK stack:**
```python
processor_lambda = aws_lambda.Function(
    self, "ProcessorFunction",
    environment={
        "EMBEDDING_DIMENSIONS": "256,384,1024,3072",
        "VECTOR_BUCKET_NAME": vector_bucket.bucket_name,
    }
)
```

## Benefits of This Structure

1. **Clear separation**: Embedder and chatbot are logically separated but share resources
2. **Reusable code**: Shared utilities reduce duplication
3. **Easy configuration**: Environment-specific configs without code changes
4. **Testable**: Unit and integration tests for all components
5. **Scalable**: Easy to add new Lambda functions or modify existing ones
6. **Demo-ready**: Scripts for quick setup and validation
7. **Maintainable**: Clear organization makes it easy to find and modify code

## Next Steps

1. Initialize CDK project: `cdk init app --language python`
2. Create the directory structure
3. Implement embedder stack first (can test independently)
4. Implement chatbot stack (depends on embedder)
5. Build frontend last (depends on API Gateway from chatbot stack)
