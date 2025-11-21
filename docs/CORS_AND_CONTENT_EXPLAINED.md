# CORS and Content Retrieval Explained

## CORS (Cross-Origin Resource Sharing)

### The Problem

Web browsers enforce the **Same-Origin Policy** for security:

```
┌─────────────────────────────────────────────────────────┐
│  Browser Security: Same-Origin Policy                   │
│                                                          │
│  Origin = Protocol + Domain + Port                      │
│                                                          │
│  ✅ ALLOWED (Same Origin):                              │
│  https://example.com → https://example.com              │
│                                                          │
│  ❌ BLOCKED (Different Origin):                         │
│  http://localhost:3000 → https://api.aws.com            │
│  (different protocol, domain, and port)                 │
└─────────────────────────────────────────────────────────┘
```

### Your Setup

```
┌──────────────────┐         ┌─────────────────────────┐
│   Frontend       │         │   Backend               │
│                  │         │                         │
│  localhost:3000  │ ──X──→  │  abc123.execute-api     │
│  (Next.js)       │         │  .amazonaws.com         │
│                  │         │  (API Gateway + Lambda) │
└──────────────────┘         └─────────────────────────┘
        ↑                              │
        │                              │
        └──────── BLOCKED! ────────────┘
           (Different origins)
```

### The Solution: CORS Headers

Your Lambda returns special headers that tell the browser "it's OK":

```python
'headers': {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
}
```

**What each header does:**

| Header | Value | Meaning |
|--------|-------|---------|
| `Access-Control-Allow-Origin` | `*` | "Accept requests from ANY website" |
| `Access-Control-Allow-Headers` | `Content-Type,Authorization` | "These headers are OK to send" |
| `Access-Control-Allow-Methods` | `GET,POST,OPTIONS` | "These HTTP methods are allowed" |

### How It Works

```
┌──────────────────┐                    ┌─────────────────────────┐
│   Frontend       │                    │   Backend               │
│  localhost:3000  │                    │  API Gateway + Lambda   │
└──────────────────┘                    └─────────────────────────┘
        │                                           │
        │  1. POST /query                          │
        │  ────────────────────────────────────→   │
        │                                           │
        │  2. Response with CORS headers           │
        │  ←────────────────────────────────────   │
        │     Access-Control-Allow-Origin: *       │
        │                                           │
        │  3. Browser checks headers               │
        │     ✅ "Origin allowed!"                 │
        │                                           │
        │  4. Frontend receives data               │
        │  ←────────────────────────────────────   │
        │                                           │
```

### CORS Preflight (OPTIONS Request)

For POST requests, browsers send a "preflight" check first:

```
Step 1: Browser sends OPTIONS request
┌──────────────────┐                    ┌─────────────────────────┐
│   Browser        │  OPTIONS /query    │   API Gateway           │
│                  │  ──────────────→   │                         │
│                  │                    │  "Is POST allowed?"     │
│                  │  ←──────────────   │                         │
│                  │  200 OK            │  CORS headers           │
└──────────────────┘  + CORS headers    └─────────────────────────┘

Step 2: If allowed, browser sends actual POST
┌──────────────────┐                    ┌─────────────────────────┐
│   Browser        │  POST /query       │   Lambda                │
│                  │  ──────────────→   │                         │
│                  │  {query: "..."}    │  Process query          │
│                  │  ←──────────────   │                         │
│                  │  Response          │  + CORS headers         │
└──────────────────┘                    └─────────────────────────┘
```

### Production vs Development

**Development (Demo):**
```python
'Access-Control-Allow-Origin': '*'  # Allow from anywhere
```

**Production (Secure):**
```python
'Access-Control-Allow-Origin': 'https://yourdomain.com'  # Only your domain
```

---

## Content Retrieval for Claude

### The Problem

Originally, Claude only saw metadata:

```
❌ OLD APPROACH:
┌─────────────────────────────────────────────────────────┐
│  Prompt to Claude:                                       │
│                                                          │
│  Source 1: video.mp4 (VIDEO)                            │
│  Source 2: document.txt (TEXT)                          │
│                                                          │
│  Question: What does the document say?                  │
│                                                          │
│  Claude: "I can see there's a document.txt file,        │
│           but I don't have access to its content."      │
└─────────────────────────────────────────────────────────┘
```

### The Solution

Now Claude gets actual content for text files:

```
✅ NEW APPROACH:
┌─────────────────────────────────────────────────────────┐
│  Prompt to Claude:                                       │
│                                                          │
│  Source 1 - video.mp4 (VIDEO)                           │
│  [Video segment 0: 0.0s - 5.0s]                         │
│  Location: s3://bucket/video.mp4                        │
│                                                          │
│  Source 2 - document.txt (TEXT)                         │
│  Content:                                               │
│  This document explains the Nova MME architecture...    │
│  [actual text content here]                             │
│                                                          │
│  Question: What does the document say?                  │
│                                                          │
│  Claude: "According to document.txt, the Nova MME       │
│           architecture consists of..."                  │
└─────────────────────────────────────────────────────────┘
```

### How It Works

```
┌─────────────────────────────────────────────────────────┐
│  Query Handler Lambda                                    │
│                                                          │
│  1. Search S3 Vector → Get matching embeddings          │
│     ↓                                                    │
│  2. For each result:                                    │
│     ├─ TEXT: Download actual content from S3           │
│     ├─ VIDEO: Include segment info + S3 URI            │
│     ├─ AUDIO: Include segment info + S3 URI            │
│     └─ IMAGE: Include filename + S3 URI                │
│     ↓                                                    │
│  3. Build prompt with all context                       │
│     ↓                                                    │
│  4. Send to Claude                                      │
│     ↓                                                    │
│  5. Return Claude's answer                              │
└─────────────────────────────────────────────────────────┘
```

### Content Retrieval Logic

```python
def get_text_content(source_uri, metadata):
    """
    For TEXT sources:
    1. Parse S3 URI (s3://bucket/key)
    2. Download file from S3
    3. If segment info exists, extract that portion
    4. Truncate if > 2000 chars (to fit in prompt)
    5. Return actual text content
    """
```

**Example:**

```
Document: 10,000 characters total
Segment: Characters 1000-3000 (from metadata)

Retrieved content: Characters 1000-3000
Sent to Claude: Actual text from that segment
```

### What Claude Sees by Modality

**TEXT:**
```
Source 1 - report.txt (TEXT)
Content:
The quarterly results show a 15% increase in revenue...
[actual text content]
```

**VIDEO:**
```
Source 2 - presentation.mp4 (VIDEO)
[Video segment 3: 15.0s - 20.0s]
Location: s3://bucket/presentation.mp4
```

**AUDIO:**
```
Source 3 - podcast.mp3 (AUDIO)
[Audio segment 5: 25.0s - 30.0s]
Location: s3://bucket/podcast.mp3
```

**IMAGE:**
```
Source 4 - diagram.png (IMAGE)
[Image file: diagram.png]
Location: s3://bucket/diagram.png
```

### Benefits

1. **Text Sources**: Claude can actually read and analyze the content
2. **Media Sources**: Claude knows what type of media and where to reference it
3. **Segments**: For chunked content, Claude gets the specific relevant portion
4. **Citations**: Claude can cite specific sources in its answer

### Limitations

- **Text only**: We can only retrieve actual content for text files
- **Media files**: Videos, images, audio are referenced but not processed
  - Future: Could use multimodal Claude to analyze images/videos
- **Size limits**: Text truncated to 2000 chars per source to fit in prompt
  - Prevents exceeding Claude's context window

### Future Enhancements

1. **Multimodal Claude**: Pass images directly to Claude for analysis
2. **Video transcripts**: Extract and include video transcripts
3. **Audio transcripts**: Use speech-to-text for audio content
4. **Caching**: Cache frequently accessed content

---

## Summary

### CORS
- **What**: Browser security mechanism
- **Why**: Prevents malicious websites from stealing data
- **How**: Special headers tell browser "this is allowed"
- **Where**: Set in Lambda response headers

### Content Retrieval
- **What**: Fetching actual file content for Claude
- **Why**: So Claude can answer based on real data, not just filenames
- **How**: Download from S3 using URI from metadata
- **Where**: `get_text_content()` function in Query Handler

Both are essential for the chatbot to work properly!
