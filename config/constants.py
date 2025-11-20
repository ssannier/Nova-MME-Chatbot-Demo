"""
Shared constants for the Nova MME Demo project
"""

# Supported embedding dimensions (Matryoshka)
EMBEDDING_DIMENSIONS = [256, 384, 1024, 3072]

# Nova MME model ID
NOVA_MME_MODEL_ID = "amazon.nova-2-multimodal-embeddings-v1:0"

# Embedding purposes
EMBEDDING_PURPOSE_INDEX = "GENERIC_INDEX"
EMBEDDING_PURPOSE_RETRIEVAL = "GENERIC_RETRIEVAL"
EMBEDDING_PURPOSE_TEXT_RETRIEVAL = "TEXT_RETRIEVAL"
EMBEDDING_PURPOSE_IMAGE_RETRIEVAL = "IMAGE_RETRIEVAL"
EMBEDDING_PURPOSE_VIDEO_RETRIEVAL = "VIDEO_RETRIEVAL"
EMBEDDING_PURPOSE_AUDIO_RETRIEVAL = "AUDIO_RETRIEVAL"
EMBEDDING_PURPOSE_DOCUMENT_RETRIEVAL = "DOCUMENT_RETRIEVAL"

# Supported file types
SUPPORTED_TEXT_EXTENSIONS = ['.txt', '.md', '.json', '.csv']
SUPPORTED_IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.webp']
SUPPORTED_VIDEO_EXTENSIONS = ['.mp4', '.mov', '.mkv', '.webm', '.flv', '.mpeg', '.mpg', '.wmv', '.3gp']
SUPPORTED_AUDIO_EXTENSIONS = ['.mp3', '.wav', '.ogg']

# File format mappings
IMAGE_FORMATS = {
    '.png': 'png',
    '.jpg': 'jpeg',
    '.jpeg': 'jpeg',
    '.gif': 'gif',
    '.webp': 'webp'
}

VIDEO_FORMATS = {
    '.mp4': 'mp4',
    '.mov': 'mov',
    '.mkv': 'mkv',
    '.webm': 'webm',
    '.flv': 'flv',
    '.mpeg': 'mpeg',
    '.mpg': 'mpg',
    '.wmv': 'wmv',
    '.3gp': '3gp'
}

AUDIO_FORMATS = {
    '.mp3': 'mp3',
    '.wav': 'wav',
    '.ogg': 'ogg'
}

# Segmentation defaults
DEFAULT_TEXT_MAX_LENGTH_CHARS = 32000
DEFAULT_AUDIO_DURATION_SECONDS = 5
DEFAULT_VIDEO_DURATION_SECONDS = 5

# S3 Vector index names
INDEX_NAME_TEMPLATE = "embeddings-{dimension}d"
