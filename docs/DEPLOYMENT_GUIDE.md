# Deployment Guide - Nova MME Demo

## Quick Start

### 1. Run Tests (Verify Everything Works)

```bash
# Run all tests
python -m pytest tests/unit/ -v

# Should see: ~100+ tests passing
```

### 2. Store GitHub Token (For Amplify Auto-Deployment)

Store your GitHub personal access token in AWS Secrets Manager:

```bash
# Windows
scripts\store-github-token.bat ghp_your_token_here

# Linux/Mac
./scripts/store-github-token.sh ghp_your_token_here
```

**To create a GitHub token:**
1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scope: ✅ `repo` (full control)
4. Copy the token (starts with `ghp_`)

**If your token expires:**
Simply generate a new token and run the script again:
```bash
scripts\store-github-token.bat ghp_new_token_here
cdk deploy NovaMMEChatbotStack
```

The script will update the existing secret and redeploy Amplify with the new token.

### 3. Create S3 Vector Bucket and Indexes

**IMPORTANT**: This must be done BEFORE deploying the CDK stacks.

S3 Vector buckets cannot be created via CDK, so we create them manually:

```bash
# Windows
scripts\setup-s3-vectors.bat dev

# Linux/Mac
chmod +x scripts/setup-s3-vectors.sh
./scripts/setup-s3-vectors.sh dev
```

This creates:
- S3 Vector bucket: `nova-mme-demo-embeddings-dev`
- 4 vector indexes:
  - `embeddings-256d` (dimension: 256, data-type: float32)
  - `embeddings-384d` (dimension: 384, data-type: float32)
  - `embeddings-1024d` (dimension: 1024, data-type: float32)
  - `embeddings-3072d` (dimension: 3072, data-type: float32)

**Verify it worked:**
```bash
aws s3vectors list-indexes --vector-bucket-name nova-mme-demo-embeddings-dev --region us-east-1
```

You should see all 4 indexes listed with status `ACTIVE`.

### 4. Install Lambda Layer Dependencies

Lambda Layers contain the Python packages needed by the Lambda functions. Install them locally:

```bash
# Windows
scripts\install-lambda-layers.bat

# Linux/Mac
chmod +x scripts/install-lambda-layers.sh
./scripts/install-lambda-layers.sh
```

This installs:
- **PyMuPDF** - For PDF to image conversion
- **python-docx** - For DOCX text extraction
- **NumPy** - For MRL truncation and normalization

### 5. Deploy Backend (AWS)

```bash
# Install CDK dependencies
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy Embedder Stack
cdk deploy NovaMMEEmbedderStack

# Deploy Chatbot Stack (includes Amplify frontend)
cdk deploy NovaMMEChatbotStack
```

**Important**: Note the URLs and App ID from the output:
```
Outputs:
NovaMMEChatbotStack.ApiEndpoint = https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/
NovaMMEChatbotStack.AmplifyAppUrl = https://main.d1234abcd.amplifyapp.com
```

### 5a. Trigger Initial Amplify Build

After first deployment, Amplify needs a manual trigger to start the first build:

```bash
# Get your Amplify App ID from the URL above (e.g., d1234abcd from d1234abcd.amplifyapp.com)
# Or list apps to find it:
aws amplify list-apps --region us-east-1 --query "apps[?name=='Nova-MME-Chatbot'].appId" --output text

# Trigger the first build
aws amplify start-job --app-id YOUR_APP_ID --branch-name main --job-type RELEASE --region us-east-1
```

**After this first build:**
- ✅ Future git pushes to `main` will automatically trigger builds
- ✅ No manual intervention needed
- ✅ No CDK redeployment required for frontend changes

**To update frontend:**
```bash
# Just push to GitHub - Amplify auto-builds!
git add frontend/
git commit -m "Update frontend"
git push origin main

# Watch build progress in Amplify Console or:
aws amplify list-jobs --app-id YOUR_APP_ID --branch-name main --region us-east-1
```

### 6. (Optional) Run Frontend Locally

The frontend is already deployed to Amplify, but if you want to run it locally:

Create `frontend/.env.local`:
```bash
NEXT_PUBLIC_QUERY_URL=https://YOUR_API_GATEWAY_URL/query
```

Run locally:
```bash
cd frontend
npm install
npm run dev
```

Visit: `http://localhost:3000`

### 7. Upload Test Files

```bash
# Upload sample files to trigger embeddings
aws s3 cp test-image.jpg s3://cic-multimedia-test/
aws s3 cp test-video.mp4 s3://cic-multimedia-test/
aws s3 cp test-audio.mp3 s3://cic-multimedia-test/
aws s3 cp test-document.txt s3://cic-multimedia-test/
```

Monitor Step Functions execution in AWS Console to see embeddings being generated.

### 8. Test the Chatbot

Visit your Amplify URL (from step 3 output) and try queries like:
- "What videos do we have?"
- "Tell me about the images"
- "Summarize the documents"

---

## Response Format

The Lambda returns JSON matching the frontend's expected format:

```json
{
  "answer": "Based on the sources, here's what I found...",
  "sources": [
    {
      "key": "video.mp4",
      "similarity": 0.95,
      "text_preview": "Type: VIDEO | Segment: 2 | Time: 10.0s - 15.0s"
    }
  ],
  "model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
  "query": "What videos do we have?",
  "dimension": 1024,
  "resultsFound": 5
}
```

---

## Architecture

```
User Query
    ↓
Frontend (Next.js)
    ↓
API Gateway
    ↓
Query Handler Lambda
    ├─→ Nova MME (embed query)
    ├─→ S3 Vector (search)
    └─→ Claude (generate answer)
    ↓
Response to Frontend
```

---

## Environment Variables

### Backend (Lambda)
Set in `lib/chatbot_stack.py`:
- `VECTOR_BUCKET` - S3 Vector bucket name
- `EMBEDDING_MODEL_ID` - Nova MME model ID
- `LLM_MODEL_ID` - Claude model ID
- `DEFAULT_DIMENSION` - Default embedding dimension (1024)
- `DEFAULT_K` - Number of results to return (5)
- `HIERARCHICAL_ENABLED` - Enable hierarchical search (true)
- `HIERARCHICAL_CONFIG` - Hierarchical search configuration (JSON)

### Frontend
Set in `frontend/.env.local`:
- `NEXT_PUBLIC_QUERY_URL` - API Gateway endpoint URL

---

## Troubleshooting

### GitHub Token Issues

**Token expired:**
```bash
# Generate new token at https://github.com/settings/tokens
# Update the secret
scripts\store-github-token.bat ghp_new_token_here

# Redeploy
cdk deploy NovaMMEChatbotStack
```

**Amplify not connecting to GitHub:**
- Verify token has `repo` scope
- Check token is stored: `aws secretsmanager get-secret-value --secret-id amplify/github-token --region us-east-1`
- Redeploy: `cdk deploy NovaMMEChatbotStack`

**Amplify shows "Update required" after deployment:**
This is normal for first deployment. The app is created but needs an initial build trigger:
```bash
# Get App ID from Amplify Console or:
aws amplify list-apps --region us-east-1 --query "apps[?name=='Nova-MME-Chatbot'].appId" --output text

# Trigger first build
aws amplify start-job --app-id YOUR_APP_ID --branch-name main --job-type RELEASE --region us-east-1
```

After the first build completes, all future pushes to `main` will auto-trigger builds.

### Frontend can't connect to backend
- Check CORS is enabled in API Gateway (already configured)
- Verify API Gateway URL is correct in Amplify environment variables
- Check browser console for errors
- Verify environment variable in Amplify Console: App settings → Environment variables

### S3 Vector Bucket Issues

**Indexes not created:**
```bash
# Verify bucket exists
aws s3vectors describe-vector-bucket --vector-bucket-name nova-mme-demo-embeddings-dev --region us-east-1

# List indexes
aws s3vectors list-indexes --vector-bucket-name nova-mme-demo-embeddings-dev --region us-east-1

# If empty, run setup script again
scripts\setup-s3-vectors.bat dev
```

**Common issues:**
- Distance metric must be lowercase: `cosine` not `COSINE`
- Data type is required: `--data-type float32`
- Bucket must be created with `aws s3vectors create-vector-bucket`, not regular S3

### No search results
- Verify embeddings were created (check S3 Vector bucket)
- Check Lambda logs in CloudWatch
- Ensure files were uploaded to source bucket
- Verify vector indexes exist: `aws s3vectors list-indexes --vector-bucket-name nova-mme-demo-embeddings-dev --region us-east-1`

### Lambda timeout
- Increase timeout in `chatbot_stack.py` (currently 60s)
- Check if Claude is responding slowly

### CORS errors
- Verify `Access-Control-Allow-Origin: *` in Lambda response
- Check API Gateway CORS configuration

---

## Optional: Deploy Frontend to Vercel

```bash
cd frontend
vercel deploy
```

Set environment variable in Vercel dashboard:
- `NEXT_PUBLIC_QUERY_URL` = Your API Gateway URL

---

## Cost Estimates (Approximate)

**Development/Testing:**
- Lambda invocations: ~$0.20/day
- S3 storage: ~$0.50/month
- API Gateway: ~$3.50/million requests
- Bedrock (Nova MME): ~$0.10/1000 embeddings
- Bedrock (Claude): ~$3.00/million tokens

**Total for demo**: ~$5-10/month with light usage

---

## Next Steps

1. ✅ Deploy and test basic functionality
2. Add dimension selector to frontend (optional)
3. Add performance metrics display (optional)
4. Update to Claude 4.5 Sonnet in prod (see TODO.md)
5. Add authentication if needed
6. Monitor costs and usage

---

## Support

- AWS CDK Docs: https://docs.aws.amazon.com/cdk/
- Nova MME Docs: https://docs.aws.amazon.com/nova/
- Next.js Docs: https://nextjs.org/docs
