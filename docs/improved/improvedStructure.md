# Improved Nova MME Demo Structure with Matryoshka Relational Learning

We are making a demo of Amazon's new model Nova Multimodal Embeddings (MME) using Python and Boto3, with a focus on showcasing Matryoshka Relational Learning (MRL) capabilities. Take some time to search for and familiarize yourself with Nova MME and its documentation (refer to novaMMEAsyncDocs.md & novaMMESyncDocs.md). Also take some time to search for and familiarize yourself with S3 Vector, as it is a relatively new AWS service.

(Refer to architecture-diagram.png for overall project structure)

## Embedder Structure

### S3 Bucket ("cic-multimedia-test")
I will upload objects to be processed (at least one of each type supported by Nova MME) in an S3 bucket. Files should be reasonably small to showcase automatic chunking without generating excessive segments (e.g., short videos, moderate-length documents).

### StepFunctions
As Nova MME asynchronous model invocations can take a long time, StepFunctions will be useful to handle the Lambda functions responsible for invoking an async processing job, monitoring the status of this job, and storing the embeddings in our S3 Vector Bucket.

**State management**: Step Functions carries the source file metadata from Lambda 1 through to Lambda 3, ensuring complete metadata is available when storing embeddings.

### Lambda 1 ("Nova MME Processor")
When a file is uploaded into the S3 Bucket, this Lambda will:

1. Extract metadata from the S3 object:
   - Original S3 URI and filename
   - File type/extension
   - File size
   - Upload timestamp
   - Content type
2. Produce the correctly formatted JSON for the file, according to its type, for asynchronous MME model invocation at **3072 dimensions** (maximum)
3. Start the asynchronous model invocation
4. Return the invocation ARN along with the extracted metadata to Step Functions

**Key change**: Always invoke at 3072 dimensions to demonstrate MRL efficiency - one invocation generates all dimension variants.

**Metadata flow**: This Lambda captures source file metadata that will be passed through Step Functions to Lambda 3 for storage alongside the embeddings.

### Lambda 2 ("Check Job Status")
When the first Lambda function has successfully started a job, this Lambda function will periodically check whether the job is finished. When it is finished, it will trigger the next Lambda function.

### Lambda 3 ("Store Embeddings")
This Lambda function will receive the output from the now-finished asynchronous processing job along with the source file metadata from Lambda 1 (passed through Step Functions). It will:

1. Parse the embedding-*.jsonl files from the async job output
2. For each 3072-dimensional embedding vector (each chunk/segment):
   - Truncate to first 256 dimensions and renormalize (L2 norm)
   - Truncate to first 384 dimensions and renormalize
   - Truncate to first 1024 dimensions and renormalize
   - Keep full 3072 dimensions
3. Store all 4 dimension variants in their respective S3 Vector indexes
4. Preserve rich metadata for each embedding by combining data from multiple sources:
   
   **From Lambda 1 (source file metadata):**
   - Original S3 URI and filename
   - File type/extension
   - File size
   - Upload timestamp
   - Content type
   
   **From async job output (segment metadata):**
   - Segment index
   - Segment timestamps (for video/audio) or character positions (for text)
   - Modality type (TEXT, IMAGE, VIDEO, AUDIO, AUDIO_VIDEO_COMBINED)
   
   **From Lambda 3 processing:**
   - Embedding dimension used (256, 384, 1024, or 3072)
   - Processing timestamp

**Key benefit**: ONE model invocation produces FOUR usable embeddings, demonstrating the true power of Matryoshka embeddings.

### S3 Vector Bucket ("nova-mme-demo-embeddings")
This bucket will have **four indexes** at different dimensions:
- `embeddings-256d` - Fast, coarse-grained search
- `embeddings-384d` - Balanced performance
- `embeddings-1024d` - High precision
- `embeddings-3072d` - Maximum precision

All indexes contain embeddings from every object uploaded to our S3 Bucket, creating unified semantic spaces at multiple granularities to be queried by our RAG chatbot.

## Chatbot Structure

### Amplify
A user will be prompted in a chatbot interface to ask about the documents stored in our S3 Bucket. The interface will include:
- Standard chat input for queries
- Dimension selector or comparison mode toggle
- Performance metrics display (latency, results count)
- Optional: Side-by-side comparison view for different dimensions

When they ask a question, it will be passed to our "Query Handler" Lambda function. They will then receive the output from the chatbot based on their query.

### Lambda 1 ("Query Handler")
This function will:

1. Embed the user input using the synchronous Nova MME invoke model API at the selected dimension(s)
2. Query the appropriate S3 Vector index(es) for the most relevant chunks (configurable, default 5)
3. **Optional**: Implement hierarchical search:
   - First pass: Fast search using 256-dim embeddings (broad recall, top 20)
   - Second pass: Refine using 1024-dim embeddings (precision, top 5)
4. **Retrieve actual content** for text sources:
   - For TEXT modality: Download actual file content from source S3 bucket
   - For VIDEO/AUDIO: Include segment timestamps and S3 URI
   - For IMAGE: Include filename and S3 URI
5. Generate a prompt for the multimodal LLM with:
   - Actual text content (for text sources)
   - Descriptive metadata (for media sources)
   - Instructions to answer only from provided information
6. Pass the formatted prompt, including relevant context, to Claude
7. Return the LLM response along with source citations and performance metrics

**IAM Permissions**:
- Read access to S3 Vector bucket (for embeddings)
- Read access to source S3 bucket (for retrieving actual content)
- Bedrock access for Nova MME and Claude

**Configurable parameters**:
- Number of results to retrieve (k)
- Dimension level(s) to query
- Whether to use hierarchical search
- embeddingPurpose optimization (GENERIC_RETRIEVAL, TEXT_RETRIEVAL, etc.)

### LLM (Multimodal Claude Model)
As mentioned above, this LLM will receive the formatted prompt and hand its response back to the "Query Handler" Lambda function.

## MRL Demonstration Features

### Dimension Comparison Mode
Users can toggle a comparison mode that:
- Runs the same query across multiple dimensions simultaneously
- Displays results side-by-side
- Shows latency and performance metrics for each dimension
- Highlights differences in retrieved content

### Validation Component (Optional)
For one sample file, make separate invocations at each dimension (256, 384, 1024, 3072) and demonstrate that the first N dimensions of the 3072-dim vector match the N-dim invocation result (after renormalization). This proves the MRL nesting property explicitly.

## Architecture Notes

The Embedder and Chatbot operate almost entirely independently, only connecting at the S3 Vector Bucket. As long as there is something to search for in the embedding indexes, the Chatbot can function.

The unified semantic space across all modalities (text, image, video, audio, documents) demonstrates Nova MME's multimodal capabilities, while the multi-dimensional indexes showcase Matryoshka Relational Learning's efficiency and flexibility.
