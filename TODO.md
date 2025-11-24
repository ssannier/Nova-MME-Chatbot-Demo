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

- [x] **Upload test files**
  - Upload sample files (1 of each type: image, video, audio, text)
  - Monitor Step Functions execution in AWS Console
  - Verify embeddings stored in S3 Vector bucket

- [x] **Test end-to-end**
  - [x] Send test query via API Gateway ✅
  - [x] Verify response from chatbot ✅
  - [x] Test simple search (works!) ✅
  - [x] Test hierarchical search
  - [x] Test through frontend UI ✅

### Phase 5: Documentation & Demo Prep
- [x] **Update architecture diagram** (`docs/initial/architecture-diagram.png`)
  - Add Query Handler Lambda
  - Show content retrieval flow (S3 source bucket → Lambda → Claude)
  - Show hierarchical search flow
  - Update to reflect 4 S3 Vector indexes
  - Show metadata flow through Step Functions

- [x] **Update README.md** with:
  - Deployment instructions
  - Testing instructions
  - API usage examples
  - Architecture diagram reference

---

## 🔧 Before Demo/Production

- [ ] **Refactor PDF processing to avoid rate limiting**
  - **Current issue:** Processor Lambda starts async invocations for all PDF pages immediately in a tight loop, causing Bedrock throttling for PDFs with 5+ pages
  - **Quick fix (implemented):** Added 500ms delay between page invocations
  - **Long-term solution:** Move async invocation logic from Processor Lambda to Step Functions
    - Processor Lambda should only convert PDF to images and return page list
    - Step Functions Map state should handle starting async invocations with built-in rate limiting
    - This provides better control, retry logic, and avoids Lambda timeout issues
  - **Alternative:** Batch multiple pages per invocation (Nova MME supports multiple images)
  - See: `lambda/embedder/processor/index.py` lines 161-173

- [ ] **Update to Claude 4.5 Sonnet** in `config/prod.json`
  - Model ID: `anthropic.claude-4-5-sonnet-20250514-v1:0` (verify latest ID in Bedrock console)
  - Just released to Bedrock - should provide better responses
  - Only change prod, keep dev on 3.5 for cost savings

- [x] **Review and adjust config values**
  - Verify bucket names are correct
  - Adjust search parameters if needed
  - Test with different dimension defaults

- [x] **Security review**
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

## 🎨 UX Improvements

### Chatbot Interface Enhancements
- [x] **Add welcome message to chatbot**
  - Display introductory message when chat loads
  - Prompt user to ask about files in the S3 bucket
  - Example: "Hi! I can help you search through files in the [bucket-name] S3 bucket. Ask me about images, videos, documents, or audio files!"
  - Update: `frontend/components/ChatWindow.tsx` to show initial system message

- [x] **Improve "no results" response** ✅
  - [x] Created structured fallback response when no relevant sources found
  - [x] Short and helpful (not apologetic rambling)
  - [x] Two scenarios handled:
    - No sources at all (empty knowledge base)
    - Sources found but below 60% similarity threshold
  - [x] Provides actionable suggestions
  - [x] Updated: `lambda/chatbot/query_handler/index.py`
  - [x] Added tests: 3 new tests, all passing

## 💡 Future Enhancements (Post-Demo)

### Multimodal Content Integration
- [x] **Fetch and pass actual media content to Claude** ✅
  - [x] Implemented `fetch_image_from_s3()` to retrieve images from S3
  - [x] Implemented `prepare_multimodal_content()` to format content blocks
  - [x] Updated `call_claude_multimodal()` to accept image + text blocks
  - [x] Added base64 encoding for images in Claude API
  - [x] Added 5MB size limit check for images
  - [x] Integrated PDF page images for semantic understanding
  - [x] Integrated regular images (JPG, PNG, GIF, WebP) for semantic understanding
  - [x] Added comprehensive test coverage (29 tests passing)
  - [x] Claude can now read actual PDF content and analyze all images
  - [x] All IMAGE modality content (PDFs and regular images) passed to Claude
  - Note: Video/audio still use metadata only (future: extract keyframes/transcripts)

### Document Format Support
- [x] **Add .docx support (text extraction)** ✅
  - [x] Implemented text extraction with python-docx
  - [x] Extracts paragraphs and tables
  - [x] Uploads as text file for Nova MME embedding
  - [x] Added test coverage
  - ⚠️ **Limitation:** Loses formatting and embedded images
  - **Future:** Convert to images using LibreOffice for full visual preservation (see `docs/DOCX_IMPLEMENTATION_PLAN.md`)

- [ ] **Add PowerPoint support** (.ppt, .pptx)
  - Similar approach: LibreOffice → PDF → Images
  - Each slide becomes a separate image
  - Lower priority than Word docs

- [ ] **Add Excel support** (.xls, .xlsx)
  - More complex: tables, formulas, multiple sheets
  - Consider text extraction vs image conversion

## 📊 Current Status

### ✅ Completed
- [x] Project structure setup
- [x] CDK stacks (Embedder & Chatbot)
- [x] Lambda 1: Nova MME Processor (all file types)
- [x] Lambda 2: Check Job Status
- [x] Lambda 3: Store Embeddings (with MRL)
- [x] Lambda 4: Query Handler (with content retrieval)
- [x] Step Functions state machine with Map state for multi-page PDFs
- [x] Multi-page PDF processing (all pages tracked and stored)
- [x] Shared utilities (MRL truncation/normalization)
- [x] Comprehensive test suite (110+ tests, 87% coverage)
- [x] Configuration files (dev/prod)
- [x] Documentation (CDK structure, embedder summary, CORS explained)
- [x] Frontend (Next.js chatbot by frontend dev)
- [x] IAM permissions (source bucket access for Query Handler)
