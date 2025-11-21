# Deployment Guide - Nova MME Demo

## Quick Start

### 1. Run Tests (Verify Everything Works)

```bash
# Run all tests
python -m pytest tests/unit/ -v

# Should see: ~100+ tests passing
```

### 2. Deploy Backend (AWS)

```bash
# Install CDK dependencies
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy Embedder Stack
cdk deploy NovaMMEEmbedderStack

# Deploy Chatbot Stack
cdk deploy NovaMMEChatbotStack
```

**Important**: Note the API Gateway URL from the output:
```
Outputs:
NovaMMEChatbotStack.ApiEndpoint = https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/
```

### 3. Configure Frontend

Create `frontend/.env.local`:
```bash
NEXT_PUBLIC_QUERY_URL=https://YOUR_API_GATEWAY_URL/query
```

Replace `YOUR_API_GATEWAY_URL` with the URL from step 2.

### 4. Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit: `http://localhost:3000`

### 5. Upload Test Files

```bash
# Upload sample files to trigger embeddings
aws s3 cp test-image.jpg s3://cic-multimedia-test/
aws s3 cp test-video.mp4 s3://cic-multimedia-test/
aws s3 cp test-audio.mp3 s3://cic-multimedia-test/
aws s3 cp test-document.txt s3://cic-multimedia-test/
```

Monitor Step Functions execution in AWS Console to see embeddings being generated.

### 6. Test the Chatbot

In the frontend, try queries like:
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

### Frontend can't connect to backend
- Check CORS is enabled in API Gateway (already configured)
- Verify API Gateway URL is correct in `.env.local`
- Check browser console for errors

### No search results
- Verify embeddings were created (check S3 Vector bucket)
- Check Lambda logs in CloudWatch
- Ensure files were uploaded to source bucket

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
