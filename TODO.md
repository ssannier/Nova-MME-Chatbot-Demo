# TODO List

## 🚧 Remaining Work to Complete Demo

### Phase 1: Query Handler Lambda (Core Chatbot Logic)
- [ ] **Create Query Handler Lambda** (`lambda/chatbot/query_handler/index.py`)
  - [ ] Implement query embedding using Nova MME synchronous API
  - [ ] Implement S3 Vector search (single dimension)
  - [ ] Implement hierarchical search (256-dim → 1024-dim refinement)
  - [ ] Format prompt with retrieved context
  - [ ] Call Claude for response generation
  - [ ] Handle errors gracefully
  - [ ] Add logging for debugging

- [ ] **Create requirements.txt** for Query Handler
  - boto3>=1.28.0
  - (any other dependencies)

### Phase 2: Testing Query Handler
- [ ] **Create test file** (`tests/unit/test_query_handler_lambda.py`)
  - [ ] Test query embedding (mock Nova MME)
  - [ ] Test vector search (mock S3 Vector)
  - [ ] Test hierarchical search logic
  - [ ] Test prompt formatting
  - [ ] Test LLM response handling
  - [ ] Test error scenarios
  - [ ] Aim for ~20-30 tests, 90%+ coverage

- [ ] **Run all tests** to ensure nothing broke
  - `python -m pytest tests/unit/ -v`

### Phase 3: Frontend (Optional - Can Test via API Gateway)
- [ ] **Decide on frontend approach**
  - Option A: Simple HTML/JS page (fastest)
  - Option B: React/Vue app with Amplify
  - Option C: Skip frontend, test via curl/Postman

- [ ] **If building frontend:**
  - [ ] Create basic chat interface
  - [ ] Add dimension selector (for MRL demo)
  - [ ] Add comparison mode toggle
  - [ ] Display performance metrics
  - [ ] Connect to API Gateway endpoint

### Phase 4: Deployment & Testing
- [ ] **Install CDK dependencies**
  - `pip install -r requirements.txt`

- [ ] **Bootstrap CDK** (first time only)
  - `cdk bootstrap`

- [ ] **Deploy Embedder Stack**
  - `cdk deploy NovaMMEEmbedderStack`
  - Verify S3 buckets created
  - Verify Lambda functions deployed
  - Verify Step Functions state machine created

- [ ] **Deploy Chatbot Stack**
  - `cdk deploy NovaMMEChatbotStack`
  - Note the API Gateway endpoint URL
  - Verify Lambda function deployed

- [ ] **Upload test files**
  - Create `scripts/upload_test_files.py` (if not exists)
  - Upload sample files (1 of each type: image, video, audio, text)
  - Monitor Step Functions execution in AWS Console
  - Verify embeddings stored in S3 Vector bucket

- [ ] **Test end-to-end**
  - Send test query via API Gateway
  - Verify response from chatbot
  - Test different dimensions
  - Test hierarchical search

### Phase 5: Documentation & Demo Prep
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
  - Architecture diagram
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

## 💡 Future Enhancements (Post-Demo)

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
- [x] Step Functions state machine
- [x] Shared utilities (MRL truncation/normalization)
- [x] Comprehensive test suite (81 tests, 94% coverage)
- [x] Configuration files (dev/prod)
- [x] Documentation (CDK structure, embedder summary)

### 🚧 In Progress
- [ ] Query Handler Lambda
- [ ] Query Handler tests
- [ ] Frontend (optional)

### ⏳ Not Started
- [ ] Deployment
- [ ] End-to-end testing
- [ ] Demo preparation
