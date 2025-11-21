# TODO List

## 🚧 Remaining Work to Complete Demo

### Phase 1: Query Handler Lambda (Core Chatbot Logic)
- [x] **Create Query Handler Lambda** (`lambda/chatbot/query_handler/index.py`)
  - [x] Implement query embedding using Nova MME synchronous API
  - [x] Implement S3 Vector search (single dimension)
  - [x] Implement hierarchical search (256-dim → 1024-dim refinement)
  - [x] Format prompt with retrieved context
  - [x] Call Claude for response generation
  - [x] Handle errors gracefully
  - [x] Add logging for debugging

- [x] **Create requirements.txt** for Query Handler
  - boto3>=1.28.0
  - (any other dependencies)

### Phase 2: Testing Query Handler
- [x] **Create test file** (`tests/unit/test_query_handler_lambda.py`)
  - [x] Test query embedding (mock Nova MME)
  - [x] Test vector search (mock S3 Vector) - mocked in handler tests
  - [x] Test hierarchical search logic - skipped (complex S3 mocking)
  - [x] Test prompt formatting
  - [x] Test LLM response handling
  - [x] Test error scenarios
  - [x] Achieved 67% function coverage (8/12 functions fully tested)

- [x] **Run all tests** to ensure nothing broke
  - All 107+ tests passing ✅

### Phase 3: Frontend (Optional - Can Test via API Gateway)
- [x] **Decide on frontend approach**
  - ✅ Next.js app built by frontend dev

- [x] **Frontend built:**
  - [x] Create basic chat interface
  - [x] Add dimension selector (for MRL demo)
  - [x] Add comparison mode toggle
  - [x] Display performance metrics
  - [x] Connect to API Gateway endpoint ✅

### Phase 4: Deployment & Testing
- [x] **Install CDK dependencies**
  - `pip install -r requirements.txt` ✅

- [x] **Bootstrap CDK** (already bootstrapped)
  - `cdk bootstrap` ✅

- [x] **Deploy Embedder Stack**
  - `cdk deploy NovaMMEEmbedderStack` ✅
  - Source Bucket: `cic-multimedia-test-dev` ✅
  - Vector Bucket: `nova-mme-demo-embeddings-dev` ✅
  - Lambda functions deployed ✅
  - Step Functions state machine created ✅

- [x] **Deploy Chatbot Stack**
  - `cdk deploy NovaMMEChatbotStack` ✅
  - API Endpoint: `https://976iaxrejk.execute-api.us-east-1.amazonaws.com/prod/` ✅
  - Lambda function deployed ✅
  - Share API URL with frontend dev ⏳

- [ ] **Upload test files**
  - Upload sample files (1 of each type: image, video, audio, text)
  - Monitor Step Functions execution in AWS Console
  - Verify embeddings stored in S3 Vector bucket

- [x] **Test end-to-end**
  - [x] Send test query via API Gateway ✅
  - [x] Verify response from chatbot ✅
  - [x] Test simple search (works!) ✅
  - [ ] Test hierarchical search (throttled - need to test with delay)
  - [x] Test through frontend UI ✅

### Phase 5: Documentation & Demo Prep
- [ ] **Update architecture diagram** (`docs/initial/architecture-diagram.png`)
  - Add Query Handler Lambda
  - Show content retrieval flow (S3 source bucket → Lambda → Claude)
  - Show hierarchical search flow
  - Update to reflect 4 S3 Vector indexes
  - Show metadata flow through Step Functions

- [ ] **Update README.md** with:
  - Deployment instructions
  - Testing instructions
  - API usage examples
  - Architecture diagram reference

- [ ] **Create demo script**
  - Sample queries to showcase
  - MRL comparison examples
  - Performance metrics to highlight

- [ ] **Prepare presentation materials** (if needed)
  - Updated architecture diagram
  - MRL explanation
  - Performance comparisons

---

## 🔧 Before Demo/Production

- [ ] **Update to Claude 4.5 Sonnet** in `config/prod.json`
  - Model ID: `anthropic.claude-4-5-sonnet-20250514-v1:0` (verify latest ID in Bedrock console)
  - Just released to Bedrock - should provide better responses
  - Only change prod, keep dev on 3.5 for cost savings

- [ ] **Review and adjust config values**
  - Verify bucket names are correct
  - Adjust search parameters if needed
  - Test with different dimension defaults

- [ ] **Security review**
  - Ensure no secrets in code
  - Review IAM permissions (principle of least privilege)
  - Add API Gateway authentication if needed

---

## 🔧 Infrastructure as Code Improvements

- [x] **Fully automate Amplify deployment in CDK** ✅
  - [x] Store GitHub token in AWS Secrets Manager ✅
  - [x] Reference token in CDK to auto-connect repository ✅
  - [x] Define all Amplify settings in CDK (no console needed) ✅
  - [x] Created scripts for token management (`scripts/store-github-token.*`) ✅
  - [x] Updated deployment guide with token rotation instructions ✅
  - [x] Eliminates manual console configuration ✅
  - [x] Enables true infrastructure-as-code for entire stack ✅
  - See: `docs/AMPLIFY_SETUP.md` for full documentation

## 💡 Future Enhancements (Post-Demo)

### Research & Exploration
- [ ] **Research Nova MME + Knowledge Bases integration**
  - Check if Nova MME is now supported as an embedding model in Bedrock Knowledge Bases
  - Compare managed Knowledge Base approach vs current S3 Vector approach
  - Document findings for future projects

### Technical Improvements
- [ ] Add retry logic to Step Functions
- [ ] Add CloudWatch alarms for failed embeddings
- [ ] Add cost tracking/monitoring
- [ ] Consider adding DynamoDB for metadata storage
- [ ] Add caching layer for frequent queries
- [ ] Implement query history/analytics
- [ ] Add user authentication
- [ ] Create admin dashboard for monitoring
- [ ] Add support for batch queries
- [ ] Implement feedback mechanism for result quality

---

## 📊 Current Status

### ✅ Completed
- [x] Project structure setup
- [x] CDK stacks (Embedder & Chatbot)
- [x] Lambda 1: Nova MME Processor (all file types)
- [x] Lambda 2: Check Job Status
- [x] Lambda 3: Store Embeddings (with MRL)
- [x] Lambda 4: Query Handler (with content retrieval)
- [x] Step Functions state machine
- [x] Shared utilities (MRL truncation/normalization)
- [x] Comprehensive test suite (107+ tests, 94% coverage)
- [x] Configuration files (dev/prod)
- [x] Documentation (CDK structure, embedder summary, CORS explained)
- [x] Frontend (Next.js chatbot by frontend dev)
- [x] IAM permissions (source bucket access for Query Handler)

### 🚧 Ready for Deployment
- [x] Run all tests ✅
- [ ] Deploy Embedder Stack
- [ ] Deploy Chatbot Stack
- [ ] Configure frontend with API URL
- [ ] Upload test files
- [ ] End-to-end testing

### ⏳ Post-Deployment
- [ ] Demo preparation
- [ ] Update to Claude 4.5 Sonnet
- [ ] Performance tuning
