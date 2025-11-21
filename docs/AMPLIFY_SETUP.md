# Amplify Setup - Fully Automated with CDK

This guide explains how to fully automate Amplify deployment using CDK, eliminating the need for manual console configuration.

## Overview

The CDK stack automatically:
- Creates an Amplify app
- Connects to your GitHub repository
- Configures build settings for Next.js monorepo
- Sets environment variables (API URL)
- Deploys the frontend on every git push

## Prerequisites

1. **GitHub Personal Access Token**
   - Go to: GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Click "Generate new token (classic)"
   - Select scopes: `repo` (full control of private repositories)
   - Copy the token (starts with `ghp_`)

## Setup Steps

### 1. Store GitHub Token in AWS Secrets Manager

**Windows:**
```bash
scripts\store-github-token.bat ghp_your_token_here
```

**Linux/Mac:**
```bash
chmod +x scripts/store-github-token.sh
./scripts/store-github-token.sh ghp_your_token_here
```

This stores your token securely in AWS Secrets Manager at `amplify/github-token`.

### 2. Deploy the CDK Stack

```bash
cdk deploy NovaMMEChatbotStack
```

The CDK will:
- ✅ Load the GitHub token from Secrets Manager
- ✅ Create the Amplify app
- ✅ Connect to your GitHub repository
- ✅ Configure build settings automatically
- ✅ Set environment variables
- ✅ Deploy the main branch

### 3. Verify Deployment

After deployment, you'll see:
```
NovaMMEChatbotStack.AmplifyAppUrl = https://main.d1234abcd.amplifyapp.com
```

Visit this URL to see your deployed frontend!

## How It Works

### CDK Configuration

The `ChatbotStack` in `lib/chatbot_stack.py`:

1. **Loads GitHub token from Secrets Manager:**
   ```python
   secret = secretsmanager.Secret.from_secret_name_v2(
       self, "GitHubToken", "amplify/github-token"
   )
   github_token = secret.secret_value.unsafe_unwrap()
   ```

2. **Creates Amplify app with repository connection:**
   ```python
   app = amplify.CfnApp(
       self, "ChatbotFrontend",
       name="Nova-MME-Chatbot",
       repository="https://github.com/ssannier/Nova-MME-Chatbot-Demo",
       access_token=github_token,
       ...
   )
   ```

3. **Configures monorepo build settings:**
   ```yaml
   applications:
     - appRoot: frontend
       frontend:
         phases:
           preBuild:
             commands: [npm ci]
           build:
             commands: [npm run build]
   ```

4. **Sets environment variables:**
   ```python
   environment_variables=[
       {"name": "AMPLIFY_MONOREPO_APP_ROOT", "value": "frontend"},
       {"name": "NEXT_PUBLIC_QUERY_URL", "value": f"{api.url}query"}
   ]
   ```

5. **Creates main branch for auto-deployment:**
   ```python
   amplify.CfnBranch(
       self, "MainBranch",
       app_id=app.attr_app_id,
       branch_name="main",
       stage="PRODUCTION",
       enable_auto_build=True
   )
   ```

## Benefits of This Approach

✅ **Infrastructure as Code** - Everything defined in CDK, no manual console clicks
✅ **Reproducible** - Can tear down and recreate entire stack with one command
✅ **Version Controlled** - All configuration tracked in git
✅ **Secure** - GitHub token stored in Secrets Manager, not in code
✅ **Automated** - Deploys automatically on git push to main branch

## Troubleshooting

### Token Not Found
If you see "Could not load GitHub token from Secrets Manager":
```bash
# Verify the secret exists
aws secretsmanager describe-secret --secret-id amplify/github-token --region us-east-1

# If not, create it
scripts\store-github-token.bat ghp_your_token_here
```

### Build Failures
Check the Amplify Console:
1. Go to AWS Console → Amplify
2. Click on "Nova-MME-Chatbot"
3. Click on the "main" branch
4. View build logs

Common issues:
- Missing environment variables → Check CDK environment_variables configuration
- Wrong monorepo path → Verify `AMPLIFY_MONOREPO_APP_ROOT=frontend`
- Node version mismatch → Amplify uses Node 20 by default

### Updating the Token
To rotate or update your GitHub token:
```bash
scripts\store-github-token.bat ghp_new_token_here
cdk deploy NovaMMEChatbotStack
```

## Cleanup

To remove the Amplify app:
```bash
cdk destroy NovaMMEChatbotStack
```

To remove the GitHub token:
```bash
aws secretsmanager delete-secret --secret-id amplify/github-token --region us-east-1
```

## Next Steps

- Add custom domain in CDK using `amplify.CfnDomain`
- Add multiple branches (dev, staging) using additional `CfnBranch` constructs
- Add WAF protection using `aws_wafv2` constructs
- Set up CloudWatch alarms for build failures
