@echo off
REM Script to store GitHub token in AWS Secrets Manager (Windows)
REM Usage: scripts\store-github-token.bat <your-github-token>

if "%1"=="" (
    echo Usage: scripts\store-github-token.bat ^<github-token^>
    echo Example: scripts\store-github-token.bat ghp_xxxxxxxxxxxx
    exit /b 1
)

set GITHUB_TOKEN=%1
set SECRET_NAME=amplify/github-token

echo Storing GitHub token in AWS Secrets Manager...

aws secretsmanager create-secret --name "%SECRET_NAME%" --description "GitHub personal access token for Amplify deployments" --secret-string "%GITHUB_TOKEN%" --region us-east-1 2>nul

if %errorlevel% equ 0 (
    echo ✅ Secret created successfully!
) else (
    echo Secret already exists, updating...
    aws secretsmanager update-secret --secret-id "%SECRET_NAME%" --secret-string "%GITHUB_TOKEN%" --region us-east-1
    
    if %errorlevel% equ 0 (
        echo ✅ Secret updated successfully!
    ) else (
        echo ❌ Failed to update secret
        exit /b 1
    )
)

echo.
echo Secret name: %SECRET_NAME%
echo You can now deploy the CDK stack with full Amplify automation!
