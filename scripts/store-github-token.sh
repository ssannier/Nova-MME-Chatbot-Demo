#!/bin/bash
# Script to store GitHub token in AWS Secrets Manager
# Usage: ./scripts/store-github-token.sh <your-github-token>

if [ -z "$1" ]; then
    echo "Usage: ./scripts/store-github-token.sh <github-token>"
    echo "Example: ./scripts/store-github-token.sh ghp_xxxxxxxxxxxx"
    exit 1
fi

GITHUB_TOKEN=$1
SECRET_NAME="amplify/github-token"

echo "Storing GitHub token in AWS Secrets Manager..."

aws secretsmanager create-secret \
    --name "$SECRET_NAME" \
    --description "GitHub personal access token for Amplify deployments" \
    --secret-string "$GITHUB_TOKEN" \
    --region us-east-1 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ Secret created successfully!"
else
    echo "Secret already exists, updating..."
    aws secretsmanager update-secret \
        --secret-id "$SECRET_NAME" \
        --secret-string "$GITHUB_TOKEN" \
        --region us-east-1
    
    if [ $? -eq 0 ]; then
        echo "✅ Secret updated successfully!"
    else
        echo "❌ Failed to update secret"
        exit 1
    fi
fi

echo ""
echo "Secret name: $SECRET_NAME"
echo "You can now deploy the CDK stack with full Amplify automation!"
