# Testing Guide

This directory contains unit and integration tests for the Nova MME Demo project.

## Setup

1. **Install test dependencies:**
   ```bash
   pip install -r tests/requirements.txt
   ```

2. **Install Lambda dependencies (for imports):**
   ```bash
   pip install -r requirements-lambda.txt
   ```

## Running Tests

### Run all tests:
```bash
pytest tests/ -v
```

### Run specific test file:
```bash
pytest tests/unit/test_embedding_utils.py -v
```

### Run with coverage:
```bash
pytest tests/ --cov=lambda --cov-report=html
```

This generates a coverage report in `htmlcov/index.html`

### Run specific test class or method:
```bash
# Run specific class
pytest tests/unit/test_embedding_utils.py::TestTruncateAndNormalize -v

# Run specific test
pytest tests/unit/test_embedding_utils.py::TestTruncateAndNormalize::test_basic_truncation -v
```

## Test Structure

```
tests/
├── unit/                           # Unit tests for individual components
│   ├── test_embedding_utils.py    # MRL truncation/normalization tests
│   ├── test_processor_lambda.py   # Lambda 1 tests
│   ├── test_check_status_lambda.py # Lambda 2 tests
│   └── test_store_embeddings_lambda.py # Lambda 3 tests (to be added)
├── integration/                    # Integration tests
│   └── test_embedder_workflow.py  # End-to-end workflow tests (to be added)
└── requirements.txt               # Test dependencies
```

## Writing Tests

### Unit Tests
- Test individual functions in isolation
- Use mocks for AWS services (boto3 clients)
- Focus on logic, edge cases, and error handling

### Integration Tests
- Test multiple components working together
- Use moto for mocking AWS infrastructure
- Test realistic workflows

## Test Coverage Goals

- **Embedding utilities**: 100% coverage (pure Python logic)
- **Lambda handlers**: 90%+ coverage (business logic)
- **CDK stacks**: Synthesis tests (infrastructure as code)

## Continuous Integration

Tests should be run:
- Before committing code
- In CI/CD pipeline before deployment
- After any Lambda function changes

## Debugging Tests

Run with verbose output and print statements:
```bash
pytest tests/unit/test_processor_lambda.py -v -s
```

Use pytest debugger on failure:
```bash
pytest tests/ --pdb
```

## Mock Data

Test fixtures and mock data are defined within each test file. For shared fixtures, see `tests/conftest.py` (to be added if needed).
