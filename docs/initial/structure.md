We are making a demo of Amazon's new model Nova Multimodal Embeddings (MME) using Python and Boto3. Take some time to search for and familiarize yourself with Nova MME and its documentation (refer to novaMMEAsyncDocs.md & novaMMESyncDocs.md). Also take some time to search for and familiarize yourself with S3 Vector, as it is a relatively new AWS service.

(Refer to architecture-diagram.png for overall project structure)

Embedder Structure:

S3 Bucket ("cic-multimedia-test")
I will upload objects to be processed (at least one of each type supported by Nova MME) in an S3 bucket. 

StepFunctions
As Nova MME aynchronous model invocations can take a long time, StepFunctions will be useful to handle the Lambda functions responsible for invoking an asynch processing job, monitoring the status of this job, and storing the embeddings in our S3 Vector Bucket.

Lambda 1 ("Nova MME Processor")
When a file is uploaded into the S3 Bucket, this Lambda will produce the correctly formatted JSON for the file, according to its type, for asynchronous MME model invocation at 1024 dimensions. (Dimensionality should be easily-changable). It will then start the asynchronous model invocation on this file.

Lambda 2 ("Check Job Status")
When the first Lambda function has successfully started a job, this Lambda function will periodically check whether the job is finished. When it is finished, it will trigger the next Lambda function.

Lambda 3 ("Store Embeddings")
This Lambda function will receive the output from the now-finished asynchronous processing job. If a 1024-dimension index called "embeddings" does not exist in our S3 Vector Bucket, this function will create one. It will then store the resulting embeddings in this index. 

S3 Vector Bucket ("nova-mme-demo-embeddings")
This bucket will have a single index called "embeddings", in which are stored the embeddings of every object uploaded to our S3 Bucket. This will create a unified semantic space to be queried by our RAG chatbot.

Chatbot Structure:

Amplify
A user will be prompted in a simple chatbot interface to ask about the documents stored in our S3 Bucket. When they ask a question, it will be passed to our "Query Handler" Lambda function. They will then receive the output from the chatbot based on their query.

Lambda 1 ("Query Handler")
This function will embed the user input using the synchronous Nova MME invoke model API, and use these embeddings to query for the most relevant chunks in our S3 Vector Bucket. (Maybe the 5 most relevant? Should be easily configurable). It will generate a prompt for the multimodal LLM, instructing it to answer only from the information retreived by the semantic search. If it cannot answer from these documents, it should be instructed to say so to the user. This formatted prompt, including the relevant context, will be given to our LLM, and its response should be presented to the user. Because of the faster speed of synchronous invocation, a single Lambda should be able to handle this whole process, but it may need to be split into multiple.

LLM (Multimodal Claude Model)
As mentioned above, this LLM will receive the formatted prompt and hand its response back to the "Query Handler" Lambda function.

The Embedder and Chatbot should be able to operate almost entirely independently, only connecting at the S3 Vector Bucket. As long as there is something to search for at the "embeddings" index of this Bucket, the Chatbot should be able to function.