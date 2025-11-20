#!/bin/bash
# Test runner script for Nova MME Demo

echo "Running Nova MME Demo Tests..."
echo "================================"

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "pytest not found. Installing test dependencies..."
    pip install -r tests/requirements.txt
fi

# Run tests with coverage
echo ""
echo "Running unit tests..."
pytest tests/unit/ -v --cov=lambda/shared --cov=lambda/embedder --cov-report=term-missing

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "✓ All tests passed!"
    exit 0
else
    echo ""
    echo "✗ Some tests failed"
    exit 1
fi
