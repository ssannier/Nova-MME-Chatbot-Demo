Complete asynchronous schema for Nova MME
(from: https://docs.aws.amazon.com/nova/latest/userguide/embeddings-schema.html)

You can generate embeddings asynchronously using the Amazon Bedrock Runtime API functions StartAsyncInvoke, GetAsyncInvoke, and ListAsyncInvokes. The asynchronous API must be used if you want to use Nova Embeddings to segment long content such as long passage of text or video and audio longer than 30 seconds.

When calling StartAsyncInvoke, you must provide modelId, outputDataConfig, and modelInput parameters.



response = bedrock_runtime.start_async_invoke(
    modelId="amazon.nova-2-multimodal-embeddings-v1:0",
    outputDataConfig=Data Config,
    modelInput=Model Input
)
  
outputDataConfig specifies the S3 bucket to which you'd like to save the generated output. It has the following structure:



{
    "s3OutputDataConfig": {
        "s3Uri": "s3://your-s3-bucket"
    }
} 
  
The s3Uri is the S3 URI of the destination bucket. For additional optional parameters, see the StartAsyncInvoke documentation.

The following structure is used for the modelInput parameter.



{
    "schemaVersion": "nova-multimodal-embed-v1",
    "taskType": "SEGMENTED_EMBEDDING",
    "segmentedEmbeddingParams": {
        "embeddingPurpose": "GENERIC_INDEX" | "GENERIC_RETRIEVAL" | "TEXT_RETRIEVAL" | "IMAGE_RETRIEVAL" | "VIDEO_RETRIEVAL" | "DOCUMENT_RETRIEVAL" | "AUDIO_RETRIEVAL" | "CLASSIFICATION" | "CLUSTERING",
        "embeddingDimension": 256 | 384 | 1024 | 3072,
        "text": {
            "truncationMode": "START" | "END" | "NONE",
            "value": string,
            "source": {
                "s3Location": {
                    "uri": "s3://Your S3 Object"
                }
            },
            "segmentationConfig": {
                "maxLengthChars": int
            }
        },
        "image": {
            "format": "png" | "jpeg" | "gif" | "webp",
            "source": SourceObject,
            "detailLevel": "STANDARD_IMAGE" | "DOCUMENT_IMAGE"
        },
        "audio": {
            "format": "mp3" | "wav" | "ogg",
            "source": SourceObject,
            "segmentationConfig": {
                "durationSeconds": int
            }
        },
        "video": {
            "format": "mp4" | "mov" | "mkv" | "webm" | "flv" | "mpeg" | "mpg" | "wmv" | "3gp",
            "source": SourceObject,
            "embeddingMode": "AUDIO_VIDEO_COMBINED" | "AUDIO_VIDEO_SEPARATE",
            "segmentationConfig": {
                "durationSeconds": int
            }
        }
    }
}
  
The following list includes all of the parameters for the request:

schemaVersion (Optional) - The schema version for the multimodal embedding model request

Type: string

Allowed values: "nova-multimodal-embed-v1"

Default: "nova-multimodal-embed-v1"

taskType (Required) - Specifies the type of embedding operation to perform on the input content. single_embedding refers to generating one embedding per model input. segmented_embedding refers to first segmenting the model input per user specification and then generating a single embedding per segment.

Type: string

Allowed values: Must be "SEGMENTED_EMBEDDING" for asynchronous calls.

segmentedEmbeddingParams (Required)

embeddingPurpose (Required) - Nova Multimodal Embeddings enables you to optimize your embeddings depending on the intended application. Examples include MM-RAG, Digital Asset Management for image and video search, similarity comparison for multimodal content, or document classification for Intelligent Document Processing. embeddingPurpose enables you to specify the embedding use-case. Select the correct value depending on the use-case below.

Search and Retrieval: Embedding use cases like RAG and search involve two main steps: first, creating an index by generating embeddings for the content, and second, retrieving the most relevant content from the index during search. Use the following values when working with search and retrieval use-cases:

Indexing:

"GENERIC_INDEX" - Creates embeddings optimized for use as indexes in a vector data store. This value should be used irrespective of the modality you are indexing.

Search/retrieval: Optimize your embeddings depending on the type of content you are retrieving:

"TEXT_RETRIEVAL" - Creates embeddings optimized for searching a repository containing only text embeddings.

"IMAGE_RETRIEVAL" - Creates embeddings optimized for searching a repository containing only image embeddings created with the "STANDARD_IMAGE" detailLevel.

"VIDEO_RETRIEVAL" - Creates embeddings optimized for searching a repository containing only video embeddings or embeddings created with the "AUDIO_VIDEO_COMBINED" embedding mode.

"DOCUMENT_RETRIEVAL" - Creates embeddings optimized for searching a repository containing only document image embeddings created with the "DOCUMENT_IMAGE" detailLevel.

"AUDIO_RETRIEVAL" - Creates embeddings optimized for searching a repository containing only audio embeddings.

"GENERIC_RETRIEVAL" - Creates embeddings optimized for searching a repository containing mixed modality embeddings.

Example: In an image search app where users retrieve images using text queries, use embeddingPurpose = generic_index when creating an embedding index based on the images and use embeddingPurpose = image_retrieval when creating an embedding of the query used to retrieve the images.

"CLASSIFICATION" - Creates embeddings optimized for performing classification.

"CLUSTERING" - Creates embeddings optimized for clustering.

embeddingDimension (Optional) - The size of the vector to generate.

Type: int

Allowed values: 256 | 384 | 1024 | 3072

Default: 3072

text (Optional) - Represents text content. Exactly one of text, image, video, audio must be present.

truncationMode (Required) - Specifies which part of the text will be truncated in cases where the tokenized version of the text exceeds the maximum supported by the model.

Type: string

Allowed values:

"START" - Omit characters from the start of the text when necessary.

"END" - Omit characters from the end of the text when necessary.

"NONE" - Fail if text length exceeds the model's maximum token limit.

value (Optional; Either value or source must be provided) - The text value for which to create the embedding.

Type: string

Max length: 8192 characters

source (Optional; Either value or source must be provided) - Reference to a text file stored in S3. Note that the bytes option of the SourceObject is not applicable for text inputs. To pass text inline as part of the request, use the value parameter instead.

segmentationConfig (Required) - Controls how text content should be segmented into multiple embeddings.

maxLengthChars (Optional) - The maximum length to allow for each segment. The model will attempt to segment only at word boundaries.

Type: int

Valid range: 800-50,000

Default: 32,000

image (Optional) - Represents image content. Exactly one of text, image, video, audio must be present.

format (Required)

Type: string

Allowed values: "png" | "jpeg" | "gif" | "webp"

source (Required) - An image content source.

Type: SourceObject (see "Common Objects" section)

detailLevel (Optional) - Dictates the resolution at which the image will be processed with "STANDARD_IMAGE" using a lower image resolution and "DOCUMENT_IMAGE" using a higher resolution image to better interpret text.

Type: string

Allowed values: "STANDARD_IMAGE" | "DOCUMENT_IMAGE"

Default: "STANDARD_IMAGE"

audio (Optional) - Represents audio content. Exactly one of text, image, video, audio must be present.

format (Required)

Type: string

Allowed values: "mp3" | "wav" | "ogg"

source (Required) - An audio content source.

Type: SourceObject (see "Common Objects" section)

segmentationConfig (Required) - Controls how audio content should be segmented into multiple embeddings.

durationSeconds (Optional) - The maximum duration of audio (in seconds) to use for each segment.

Type: int

Valid range: 1-30

Default: 5

video (Optional) - Represents video content. Exactly one of text, image, video, audio must be present.

format (Required)

Type: string

Allowed values: "mp4" | "mov" | "mkv" | "webm" | "flv" | "mpeg" | "mpg" | "wmv" | "3gp"

source (Required) - A video content source.

Type: SourceObject (see "Common Objects" section)

embeddingMode (Required)

Type: string

Values: "AUDIO_VIDEO_COMBINED" | "AUDIO_VIDEO_SEPARATE"

"AUDIO_VIDEO_COMBINED" - Will produce a single embedding for each segment combining both audible and visual content.

"AUDIO_VIDEO_SEPARATE" - Will produce two embeddings for each segment, one for the audio content and one for the video content.

segmentationConfig (Required) - Controls how video content should be segmented into multiple embeddings.

durationSeconds (Optional) - The maximum duration of video (in seconds) to use for each segment.

Type: int

Valid range: 1-30

Default: 5

StartAsyncInvoke Response
The response from a call to StartAsyncInvoke will have the structure below. The invocationArn can be used to query the status of the asynchronous job using the GetAsyncInvoke function.



{
    "invocationArn": "arn:aws:bedrock:us-east-1:xxxxxxxxxxxx:async-invoke/lvmxrnjf5mo3",
}
  
Asynchronous Output
When asynchronous embeddings generation is complete, output artifacts are written to the S3 bucket you specified as the output destination. The files will have the following structure:



   amzn-s3-demo-bucket/
    job-id/
        segmented-embedding-result.json
        embedding-audio.jsonl
        embedding-image.json
        embedding-text.jsonl
        embedding-video.jsonl
        manifest.json
  
The segmented-embedding-result.json will contain the overall job result and reference to the corresponding jsonl files which contain actual embeddings per modality. Below is a truncated example of a file:



{
    "sourceFileUri": string, 
    "embeddingDimension": 256 | 384 | 1024 | 3072,
    "embeddingResults": [
        {
            "embeddingType": "TEXT" | "IMAGE" | "VIDEO" | "AUDIO" | "AUDIO_VIDEO_COMBINED",
            "status": "SUCCESS" | "FAILURE" | "PARTIAL_SUCCESS",
            "failureReason": string, // Granular error codes
            "message": string, // Human-readbale failure message
            "outputFileUri": string // S3 URI to a "embedding-modality.jsonl" file
        }
        ...
    ]
}
  
The embedding-modality.json will be jsonl files which contain the embedding output for each modality. Each line in the jsonl file will adhere to the following schema:



{
    "embedding": number[], // The generated embedding vector
    "segmentMetadata": {
        "segmentIndex": number,
        "segmentStartCharPosition": number, // Included for text only
        "segmentEndCharPosition": number, // Included for text only
        "truncatedCharLength": number, // Included only when text gets truncated
        "segmentStartSeconds": number, // Included for audio/video only
        "segmentEndSeconds": number // Included for audio/video only
    },
    "status": "SUCCESS" | "FAILURE",
    "failureReason": string, // Granular error codes
    "message": string // Human-readable failure message
}
  
The following list includes all of the parameters for the response. For text characters or audio/video times, all starting and ending times are zero-based. Additionally, all ending text positions or audio/video time values are inclusive.

embedding (Required) — The embedding vector.

Type: number

segmentMetadata — The metadata for the segment.

segmentIndex — The index of the segment within the array provided in the request.

segmentStartCharPosition — For text only. The starting (inclusive) character position of the embedded content within the segment.

segmentEndCharPosition — For text only. The ending character (exclusive) position of the embedded content within the segment.

truncatedCharLength (Optional) — Returned if the tokenized version of the input text exceeded the model’s limitations. The value indicates the character after which the text was truncated before generating the embedding.

Type: integer

segmentStartSeconds — For audio/video only. The starting time position of the embedded content within the segment.

segmentEndSeconds — For audio/video only. The ending time position of the embedded content within the segment.

status — The status for the segment.

failureReason — The detailed reasons on the failure for the segment.

RAI_VIOLATION_INPUT_TEXT_DEFLECTION — Input text violates RAI policy.

RAI_VIOLATION_INPUT_IMAGE_DEFLECTION — input image violates RAI policy.

INVALID_CONTENT — Invalid input.

RATE_LIMIT_EXCEEDED — Embedding request is throttled due to service unavailability.

INTERNAL_SERVER_EXCEPTION — Something went wrong.

message — Related failure message.

File limitations for Nova Embeddings

Synchronous operations can accept both S3 inputs and inline chunks. Asynchronous operations can only accept S3 inputs.

When generating embeddings asynchronously, you'll need to ensure that your file is separated into an appropriate number of segments. For text embeddings you cannot have more than 1900 segments. For audio and video embeddings you cannot have more than 1434 segments.

Synchronous Input size limits
File Type

Size Limit

(Inline) All file types

25 MB

(S3) Text

1 MB; 50,000 characters

(S3) Image

50 MB

(S3) Video

30 seconds; 100 MB

(S3) Audio

30 seconds; 100 MB

Note
The 25 MB inline file restriction is after Base64 embedding. This causes a file size inflation of about 33%

Asynchronous Input size limits
File Type

Size Limit

(S3) Text

634 MB

(S3) Image

50 MB

(S3) Video

2 GB; 2 hours

(S3) Audio

1 GB; 2 hours

Input file types
Modality

File types

Image Formats

PNG, JPEG, WEBP, GIF

Audio Formats

MP3, WAV, OGG

Video Formats

MP4, MOV, MKV, WEBM, FLV, MPEG, MPG, WMV, 3GP

