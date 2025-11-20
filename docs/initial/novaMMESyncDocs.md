Complete synchronous schema
(from: https://docs.aws.amazon.com/nova/latest/userguide/embeddings-schema.html)

{
    "schemaVersion": "nova-multimodal-embed-v1",
    "taskType": "SINGLE_EMBEDDING",
    "singleEmbeddingParams": {
        "embeddingPurpose": "GENERIC_INDEX" | "GENERIC_RETRIEVAL" | "TEXT_RETRIEVAL" | "IMAGE_RETRIEVAL" | "VIDEO_RETRIEVAL" | "DOCUMENT_RETRIEVAL" | "AUDIO_RETRIEVAL" | "CLASSIFICATION" | "CLUSTERING",
        "embeddingDimension": 256 | 384 | 1024 | 3072,
        "text": {
            "truncationMode": "START" | "END" | "NONE",
            "value": string,
            "source": SourceObject,
        },
        "image": {
            "detailLevel": "STANDARD_IMAGE" | "DOCUMENT_IMAGE",
            "format": "png" | "jpeg" | "gif" | "webp",
            "source": SourceObject
        },
        "audio": {
            "format": "mp3" | "wav" | "ogg",
            "source": SourceObject
        },
        "video": {
            "format": "mp4" | "mov" | "mkv" | "webm" | "flv" | "mpeg" | "mpg" | "wmv" | "3gp",
            "source": SourceObject,
            "embeddingMode": "AUDIO_VIDEO_COMBINED" | "AUDIO_VIDEO_SEPARATE"
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

Allowed values: Must be "SINGLE_EMBEDDING" for synchronous calls.

singleEmbeddingParams (Required)

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

Type: SourceObject (see "Common Objects" section)

image (Optional) - Represents image content. Exactly one of text, image, video, audio must be present.

detailLevel (Optional) - Dictates the resolution at which the image will be processed with "STANDARD_IMAGE" using a lower image resolution and "DOCUMENT_IMAGE" using a higher resolution image to better interpret text.

Type: string

Allowed values: "STANDARD_IMAGE" | "DOCUMENT_IMAGE"

Default: "STANDARD_IMAGE"

format (Required)

Type: string

Allowed values: "png" | "jpeg" | "gif" | "webp"

source (Required) - An image content source.

Type: SourceObject (see "Common Objects" section)

audio (Optional) - Represents audio content. Exactly one of text, image, video, audio must be present.

format (Required)

Type: string

Allowed values: "mp3" | "wav" | "ogg"

source (Required) - An audio content source.

Type: SourceObject (see "Common Objects" section)

Maximum audio duration: 30 seconds

video (Optional) - Represents video content. Exactly one of text, image, video, audio must be present.

format (Required)

Type: string

Allowed values: "mp4" | "mov" | "mkv" | "webm" | "flv" | "mpeg" | "mpg" | "wmv" | "3gp"

source (Required) - A video content source.

Type: SourceObject (see "Common Objects" section)

Maximum video duration: 30 seconds

embeddingMode (Required)

Type: string

Values: "AUDIO_VIDEO_COMBINED" | "AUDIO_VIDEO_SEPARATE"

"AUDIO_VIDEO_COMBINED" - Will produce a single embedding combining both audible and visual content.

"AUDIO_VIDEO_SEPARATE" - Will produce two embeddings, one for the audible content and one for the visual content.

InvokeModel Response Body
When InvokeModel returns a successful result, the body of the response will have the following structure:



{
   "embeddings": [
      {
          "embeddingType": "TEXT" | "IMAGE" | "VIDEO" | "AUDIO" | "AUDIO_VIDEO_COMBINED",
          "embedding": number[],
          "truncatedCharLength": int // Only included if text input was truncated
      }
    ]                       
}
   
The following list includes all of the parameters for the response:

embeddings (Required) - For most requests, this array will contain a single embedding. For video requests where the "AUDIO_VIDEO_SEPARATE" embeddingMode mode was selected, this array will contain two embeddings - one embedding for the video content and one for the the audio content.

Type: array of embeddings with the following properties

embeddingType (Required) - Reports the type of embedding that was created.

Type: string

Allowed values: "TEXT" | "IMAGE" | "VIDEO" | "AUDIO" | "AUDIO_VIDEO_COMBINED"

embedding (Required) - The embedding vector.

Type: number[]

truncatedCharLength (Optional) - Only applies to text embedding requests. Returned if the tokenized version of the input text exceeded the model's limitations. The value indicates the character after which the text was truncated before generating the embedding.

Type: int