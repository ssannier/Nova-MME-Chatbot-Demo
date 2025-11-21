# Amplify + Next.js Deployment Template (CDK)

This guide shows how to deploy a Next.js app to AWS Amplify using CDK, with full automation and infrastructure-as-code principles.

## Project Structure

```
your-project/
├── frontend/                    # Next.js app (monorepo subdirectory)
│   ├── app/                    # Next.js 13+ app directory
│   ├── components/             # React components
│   ├── package.json            # Dependencies
│   ├── next.config.ts          # Next.js config
│   └── tsconfig.json           # TypeScript config
├── lib/
│   └── your_stack.py           # CDK stack with Amplify
├── scripts/
│   └── store-github-token.bat  # Script to store GitHub token
├── app.py                      # CDK app entry point
└── requirements.txt            # CDK dependencies
```

## Step-by-Step Setup

### 1. Prerequisites

**Frontend Requirements:**
- Next.js app in a subdirectory (e.g., `frontend/`)
- `package.json` with build script: `"build": "next build"`
- Environment variables prefixed with `NEXT_PUBLIC_` for client-side access

**AWS Requirements:**
- AWS CLI configured
- CDK installed: `npm install -g aws-cdk`
- Python CDK dependencies: `pip install aws-cdk-lib constructs`

**GitHub Requirements:**
- Repository pushed to GitHub
- Personal access token with `repo` scope

### 2. Store GitHub Token

Create a script to store your GitHub token in AWS Secrets Manager:

**`scripts/store-github-token.bat` (Windows):**
```batch
@echo off
if "%1"=="" (
    echo Usage: scripts\store-github-token.bat ^<github-token^>
    exit /b 1
)

set GITHUB_TOKEN=%1
set SECRET_NAME=amplify/github-token

aws secretsmanager create-secret ^
    --name "%SECRET_NAME%" ^
    --description "GitHub personal access token for Amplify" ^
    --secret-string "%GITHUB_TOKEN%" ^
    --region us-east-1 2>nul

if %errorlevel% equ 0 (
    echo ✅ Secret created successfully!
) else (
    echo Updating existing secret...
    aws secretsmanager update-secret ^
        --secret-id "%SECRET_NAME%" ^
        --secret-string "%GITHUB_TOKEN%" ^
        --region us-east-1
)
```

**`scripts/store-github-token.sh` (Linux/Mac):**
```bash
#!/bin/bash
if [ -z "$1" ]; then
    echo "Usage: ./scripts/store-github-token.sh <github-token>"
    exit 1
fi

GITHUB_TOKEN=$1
SECRET_NAME="amplify/github-token"

aws secretsmanager create-secret \
    --name "$SECRET_NAME" \
    --description "GitHub personal access token for Amplify" \
    --secret-string "$GITHUB_TOKEN" \
    --region us-east-1 2>/dev/null || \
aws secretsmanager update-secret \
    --secret-id "$SECRET_NAME" \
    --secret-string "$GITHUB_TOKEN" \
    --region us-east-1
```

Run it:
```bash
scripts\store-github-token.bat ghp_your_token_here
```

### 3. CDK Stack Configuration

**`lib/your_stack.py`:**

```python
from aws_cdk import (
    Stack,
    aws_amplify as amplify,
    aws_secretsmanager as secretsmanager,
    CfnOutput,
)
from constructs import Construct

class YourStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Your other resources (API Gateway, Lambda, etc.)
        # ...
        
        # Create Amplify app
        self.amplify_app = self._create_amplify_app()
        
        # Output the Amplify URL
        CfnOutput(
            self,
            "AmplifyAppUrl",
            value=f"https://main.{self.amplify_app.attr_app_id}.amplifyapp.com",
            description="Amplify frontend URL",
        )
    
    def _create_amplify_app(self) -> amplify.CfnApp:
        """Create Amplify app for Next.js frontend hosting"""
        
        # Load GitHub token from Secrets Manager
        github_token = None
        try:
            secret = secretsmanager.Secret.from_secret_name_v2(
                self,
                "GitHubToken",
                "amplify/github-token"
            )
            github_token = secret.secret_value.unsafe_unwrap()
            print("✅ GitHub token loaded from Secrets Manager")
        except Exception as e:
            print(f"⚠️  Warning: Could not load GitHub token: {e}")
            github_token = None
        
        # Build spec for Next.js in a monorepo subdirectory
        build_spec = """version: 1
applications:
  - appRoot: frontend
    frontend:
      phases:
        preBuild:
          commands:
            - npm ci
        build:
          commands:
            - echo "NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL" > .env.production
            - npm run build
      artifacts:
        baseDirectory: .next
        files:
          - '**/*'
      cache:
        paths:
          - node_modules/**/*
"""
        
        # Create Amplify app
        app = amplify.CfnApp(
            self,
            "FrontendApp",
            name="Your-App-Name",
            repository="https://github.com/your-username/your-repo" if github_token else None,
            access_token=github_token,
            build_spec=build_spec,
            environment_variables=[
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="AMPLIFY_MONOREPO_APP_ROOT",
                    value="frontend"
                ),
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="NEXT_PUBLIC_API_URL",
                    value="https://your-api-url.com"  # Replace with your API URL
                ),
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="_LIVE_UPDATES",
                    value='[{"name":"Next.js version","pkg":"next-version","type":"internal","version":"latest"}]'
                )
            ],
            platform="WEB_COMPUTE"  # Required for Next.js SSR
        )
        
        # Add main branch for auto-deployment
        if github_token:
            branch = amplify.CfnBranch(
                self,
                "MainBranch",
                app_id=app.attr_app_id,
                branch_name="main",
                stage="PRODUCTION",
                enable_auto_build=True
            )
        
        return app
```

### 4. Key Configuration Details

#### Monorepo Settings

If your Next.js app is in a subdirectory (not at repo root):

```python
# In build_spec
applications:
  - appRoot: frontend  # Path to your Next.js app

# In environment_variables
amplify.CfnApp.EnvironmentVariableProperty(
    name="AMPLIFY_MONOREPO_APP_ROOT",
    value="frontend"
)
```

#### Build Spec Breakdown

```yaml
version: 1
applications:
  - appRoot: frontend              # Where your Next.js app lives
    frontend:
      phases:
        preBuild:
          commands:
            - npm ci               # Install dependencies (faster than npm install)
        build:
          commands:
            # Inject environment variables into .env.production
            - echo "NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL" > .env.production
            - npm run build        # Build Next.js app
      artifacts:
        baseDirectory: .next       # Next.js build output directory
        files:
          - '**/*'                 # Include all files
      cache:
        paths:
          - node_modules/**/*      # Cache dependencies for faster builds
```

#### Environment Variables

**For client-side access (browser):**
```python
amplify.CfnApp.EnvironmentVariableProperty(
    name="NEXT_PUBLIC_API_URL",  # Must start with NEXT_PUBLIC_
    value="https://api.example.com"
)
```

**For build-time only:**
```python
amplify.CfnApp.EnvironmentVariableProperty(
    name="BUILD_ENV",
    value="production"
)
```

#### Platform Setting

```python
platform="WEB_COMPUTE"  # Required for Next.js with SSR/ISR
# Use "WEB" for static sites only
```

### 5. Deploy

```bash
# Store GitHub token
scripts\store-github-token.bat ghp_your_token_here

# Deploy CDK stack
cdk deploy YourStack
```

### 6. Verify Deployment

After deployment:
1. Check CDK outputs for Amplify URL
2. Go to AWS Amplify Console
3. Click on your app
4. View the "main" branch build progress
5. Once complete, visit the Amplify URL

## Common Issues & Solutions

### Issue: "Update required" in Amplify Console

**Cause:** GitHub token not loaded properly or expired

**Solution:**
```bash
# Verify token exists
aws secretsmanager get-secret-value --secret-id amplify/github-token --region us-east-1

# Update token
scripts\store-github-token.bat ghp_new_token_here

# Redeploy
cdk deploy YourStack
```

### Issue: Build fails with "Cannot find module 'next'"

**Cause:** Wrong `appRoot` or missing `package.json`

**Solution:**
- Verify `appRoot` matches your Next.js directory
- Ensure `package.json` exists in that directory
- Check `AMPLIFY_MONOREPO_APP_ROOT` environment variable

### Issue: Environment variables not available in browser

**Cause:** Missing `NEXT_PUBLIC_` prefix

**Solution:**
- Client-side variables MUST start with `NEXT_PUBLIC_`
- Rebuild after adding environment variables
- Verify in Amplify Console: App settings → Environment variables

### Issue: 404 errors when accessing API

**Cause:** API URL not configured or incorrect

**Solution:**
```python
# In CDK, pass your API Gateway URL
amplify.CfnApp.EnvironmentVariableProperty(
    name="NEXT_PUBLIC_API_URL",
    value=f"{api_gateway.url}endpoint"  # Use actual API URL
)
```

### Issue: Build succeeds but app shows blank page

**Cause:** Wrong `baseDirectory` in artifacts

**Solution:**
```yaml
artifacts:
  baseDirectory: .next  # For Next.js
  # NOT: build, dist, or out (unless using static export)
```

### Issue: "Platform not supported" error

**Cause:** Using `WEB` platform for SSR app

**Solution:**
```python
platform="WEB_COMPUTE"  # For Next.js with SSR/ISR
```

## Advanced Configuration

### Multiple Branches (Dev/Staging/Prod)

```python
# Production branch
prod_branch = amplify.CfnBranch(
    self, "ProdBranch",
    app_id=app.attr_app_id,
    branch_name="main",
    stage="PRODUCTION",
    enable_auto_build=True
)

# Staging branch
staging_branch = amplify.CfnBranch(
    self, "StagingBranch",
    app_id=app.attr_app_id,
    branch_name="staging",
    stage="BETA",
    enable_auto_build=True,
    environment_variables=[
        amplify.CfnBranch.EnvironmentVariableProperty(
            name="NEXT_PUBLIC_API_URL",
            value="https://staging-api.example.com"
        )
    ]
)
```

### Custom Domain

```python
domain = amplify.CfnDomain(
    self, "CustomDomain",
    app_id=app.attr_app_id,
    domain_name="example.com",
    sub_domain_settings=[
        amplify.CfnDomain.SubDomainSettingProperty(
            branch_name="main",
            prefix=""  # Root domain
        ),
        amplify.CfnDomain.SubDomainSettingProperty(
            branch_name="staging",
            prefix="staging"  # staging.example.com
        )
    ]
)
```

### Build Notifications

```python
# Add SNS topic for build notifications
import aws_cdk.aws_sns as sns

build_notifications = sns.Topic(
    self, "BuildNotifications",
    display_name="Amplify Build Notifications"
)

# Subscribe to notifications
build_notifications.add_subscription(
    sns_subscriptions.EmailSubscription("your-email@example.com")
)
```

## Best Practices

✅ **Store secrets in Secrets Manager** - Never hardcode tokens
✅ **Use monorepo structure** - Keep frontend and backend together
✅ **Prefix client variables** - Use `NEXT_PUBLIC_` for browser access
✅ **Cache dependencies** - Speed up builds with `node_modules` caching
✅ **Use WEB_COMPUTE** - Required for Next.js SSR/ISR features
✅ **Auto-deploy on push** - Enable `enable_auto_build=True`
✅ **Version control everything** - All config in CDK, not console
✅ **Test locally first** - Run `npm run build` before deploying

## Template Checklist

Before deploying, verify:

- [ ] Next.js app builds locally: `npm run build`
- [ ] GitHub token stored: `scripts\store-github-token.bat ghp_xxx`
- [ ] Repository URL correct in CDK
- [ ] `appRoot` matches your directory structure
- [ ] Environment variables have `NEXT_PUBLIC_` prefix (if client-side)
- [ ] `platform="WEB_COMPUTE"` for SSR apps
- [ ] Branch name matches your repo (usually "main")
- [ ] CDK dependencies installed: `pip install -r requirements.txt`

## Complete Example

See the Nova MME Demo project for a complete working example:
- CDK Stack: `lib/chatbot_stack.py`
- Token Script: `scripts/store-github-token.bat`
- Documentation: `docs/AMPLIFY_SETUP.md`

## Resources

- [AWS Amplify Hosting Docs](https://docs.aws.amazon.com/amplify/latest/userguide/welcome.html)
- [Next.js Deployment Docs](https://nextjs.org/docs/deployment)
- [CDK Amplify API Reference](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_amplify.html)
- [Next.js Environment Variables](https://nextjs.org/docs/basic-features/environment-variables)
