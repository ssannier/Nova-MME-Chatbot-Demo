"""
Unit tests for Lambda: Query Handler
"""

import pytest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock
import importlib.util

# Set required environment variables before importing
os.environ['VECTOR_BUCKET'] = 'test-vector-bucket'
os.environ['EMBEDDING_MODEL_ID'] = 'amazon.nova-2-multimodal-embeddings-v1:0'
os.environ['LLM_MODEL_ID'] = 'anthropic.claude-3-5-sonnet-20240620-v1:0'
os.environ['DEFAULT_DIMENSION'] = '1024'
os.environ['DEFAULT_K'] = '5'
os.environ['HIERARCHICAL_ENABLED'] = 'true'
os.environ['HIERARCHICAL_CONFIG'] = json.dumps({
    'first_pass_dimension': 256,
    'first_pass_k': 20,
    'second_pass_dimension': 1024,
    'second_pass_k': 5
})
os.environ['VECTOR_INDEXES'] = json.dumps({
    '256': 'embeddings-256d',
    '384': 'embeddings-384d',
    '1024': 'embeddings-1024d',
    '3072': 'embeddings-3072d'
})
os.environ['LLM_MAX_TOKENS'] = '2048'
os.environ['LLM_TEMPERATURE'] = '0.7'

# Import the query_handler module directly
query_handler_path = os.path.join(os.path.dirname(__file__), '../../lambda/chatbot/query_handler/index.py')
spec = importlib.util.spec_from_file_location("query_handler", query_handler_path)
query_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(query_handler)


class TestEmbedQuery:
    """Tests for embed_query function"""
    
    @patch.object(query_handler, 'bedrock_runtime')
    def test_embeds_query(self, mock_bedrock):
        """Test query embedding"""
        mock_bedrock.invoke_model.return_value = {
            'body': Mock(read=lambda: json.dumps({
                'embeddings': [
                    {
                        'embeddingType': 'TEXT',
                        'embedding': [0.1] * 1024
                    }
                ]
            }).encode())
        }
        
        result = query_handler.embed_query("test query", 1024)
        
        assert len(result) == 1024
        assert all(isinstance(x, float) for x in result)
        
        # Verify correct API call
        mock_bedrock.invoke_model.assert_called_once()
        call_args = mock_bedrock.invoke_model.call_args
        body = json.loads(call_args[1]['body'])
        
        assert body['taskType'] == 'SINGLE_EMBEDDING'
        assert body['singleEmbeddingParams']['embeddingPurpose'] == 'GENERIC_RETRIEVAL'
        assert body['singleEmbeddingParams']['embeddingDimension'] == 1024
        assert body['singleEmbeddingParams']['text']['value'] == 'test query'


class TestCosineSimilarity:
    """Tests for cosine_similarity function"""
    
    def test_identical_vectors(self):
        """Test similarity of identical vectors"""
        vec = [1.0, 2.0, 3.0]
        similarity = query_handler.cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 1e-6
    
    def test_orthogonal_vectors(self):
        """Test similarity of orthogonal vectors"""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = query_handler.cosine_similarity(vec1, vec2)
        assert abs(similarity) < 1e-6
    
    def test_opposite_vectors(self):
        """Test similarity of opposite vectors"""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [-1.0, -2.0, -3.0]
        similarity = query_handler.cosine_similarity(vec1, vec2)
        assert abs(similarity - (-1.0)) < 1e-6
    
    def test_zero_vector(self):
        """Test handling of zero vectors"""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]
        similarity = query_handler.cosine_similarity(vec1, vec2)
        assert similarity == 0.0


class TestFormatPrompt:
    """Tests for format_prompt function"""
    
    @patch.object(query_handler, 'get_text_content')
    def test_formats_prompt_with_sources(self, mock_get_text):
        """Test prompt formatting with sources"""
        mock_get_text.return_value = "This is the text content from the document."
        
        sources = [
            {
                'metadata': {
                    'fileName': 'video.mp4',
                    'modalityType': 'VIDEO',
                    'sourceS3Uri': 's3://bucket/video.mp4',
                    'segmentIndex': 0,
                    'segmentStartSeconds': 0.0,
                    'segmentEndSeconds': 5.0
                },
                'similarity': 0.95
            },
            {
                'metadata': {
                    'fileName': 'document.txt',
                    'modalityType': 'TEXT',
                    'sourceS3Uri': 's3://bucket/document.txt'
                },
                'similarity': 0.87
            }
        ]
        
        prompt = query_handler.format_prompt("What is this about?", sources)
        
        assert "What is this about?" in prompt
        assert "video.mp4" in prompt
        assert "document.txt" in prompt
        assert "VIDEO" in prompt
        assert "TEXT" in prompt
        assert "This is the text content" in prompt
        assert "Answer:" in prompt
    
    def test_formats_prompt_with_no_sources(self):
        """Test prompt formatting with empty sources"""
        prompt = query_handler.format_prompt("test query", [])
        
        assert "test query" in prompt
        assert "Answer:" in prompt


class TestGetTextContent:
    """Tests for get_text_content function"""
    
    @patch.object(query_handler, 's3_client')
    def test_retrieves_full_text(self, mock_s3):
        """Test retrieving full text content"""
        mock_s3.get_object.return_value = {
            'Body': Mock(read=lambda: b"This is the full text content.")
        }
        
        metadata = {}
        content = query_handler.get_text_content('s3://bucket/file.txt', metadata)
        
        assert content == "This is the full text content."
    
    @patch.object(query_handler, 's3_client')
    def test_retrieves_text_segment(self, mock_s3):
        """Test retrieving text segment"""
        full_text = "0123456789" * 100  # 1000 chars
        mock_s3.get_object.return_value = {
            'Body': Mock(read=lambda: full_text.encode())
        }
        
        metadata = {
            'segmentStartCharPosition': 0,
            'segmentEndCharPosition': 100
        }
        content = query_handler.get_text_content('s3://bucket/file.txt', metadata)
        
        assert len(content) == 100
        assert content == full_text[:100]
    
    @patch.object(query_handler, 's3_client')
    def test_truncates_long_text(self, mock_s3):
        """Test truncation of long text"""
        long_text = "x" * 5000
        mock_s3.get_object.return_value = {
            'Body': Mock(read=lambda: long_text.encode())
        }
        
        metadata = {}
        content = query_handler.get_text_content('s3://bucket/file.txt', metadata)
        
        assert len(content) < 5000
        assert "truncated" in content.lower()
    
    def test_handles_invalid_uri(self):
        """Test handling of invalid S3 URI"""
        content = query_handler.get_text_content('invalid-uri', {})
        assert content == ""
    
    @patch.object(query_handler, 's3_client')
    def test_handles_s3_error(self, mock_s3):
        """Test handling of S3 errors"""
        mock_s3.get_object.side_effect = Exception("S3 error")
        
        content = query_handler.get_text_content('s3://bucket/file.txt', {})
        assert content == ""


class TestCallClaudeMultimodal:
    """Tests for call_claude_multimodal function"""
    
    @patch.object(query_handler, 'bedrock_runtime_llm')
    def test_calls_claude_multimodal(self, mock_bedrock_llm):
        """Test Claude multimodal API call"""
        mock_bedrock_llm.invoke_model.return_value = {
            'body': Mock(read=lambda: json.dumps({
                'content': [
                    {
                        'text': 'This is the answer from Claude.'
                    }
                ]
            }).encode())
        }
        
        content_blocks = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": "base64encodeddata"
                }
            },
            {
                "type": "text",
                "text": "test prompt"
            }
        ]
        
        result = query_handler.call_claude_multimodal(content_blocks)
        
        assert result == 'This is the answer from Claude.'
        
        # Verify correct API call
        mock_bedrock_llm.invoke_model.assert_called_once()
        call_args = mock_bedrock_llm.invoke_model.call_args
        body = json.loads(call_args[1]['body'])
        
        assert body['anthropic_version'] == 'bedrock-2023-05-31'
        assert body['max_tokens'] == 2048
        assert body['temperature'] == 0.7
        assert body['messages'][0]['role'] == 'user'
        assert isinstance(body['messages'][0]['content'], list)
        assert len(body['messages'][0]['content']) == 2


class TestFetchImageFromS3:
    """Tests for fetch_image_from_s3 function"""
    
    @patch.object(query_handler, 's3_client')
    def test_fetches_image_successfully(self, mock_s3):
        """Test successful image fetch"""
        image_data = b"fake image data"
        mock_s3.get_object.return_value = {
            'Body': Mock(read=lambda: image_data)
        }
        
        result = query_handler.fetch_image_from_s3('s3://bucket/image.jpg')
        
        assert result == image_data
        mock_s3.get_object.assert_called_once_with(Bucket='bucket', Key='image.jpg')
    
    def test_handles_invalid_uri(self):
        """Test handling of invalid S3 URI"""
        result = query_handler.fetch_image_from_s3('invalid-uri')
        assert result is None
    
    @patch.object(query_handler, 's3_client')
    def test_handles_s3_error(self, mock_s3):
        """Test handling of S3 errors"""
        mock_s3.get_object.side_effect = Exception("S3 error")
        
        result = query_handler.fetch_image_from_s3('s3://bucket/image.jpg')
        assert result is None
    
    @patch.object(query_handler, 's3_client')
    def test_rejects_oversized_image(self, mock_s3):
        """Test rejection of images over 5MB"""
        # Create 6MB of fake data
        large_image = b"x" * (6 * 1024 * 1024)
        mock_s3.get_object.return_value = {
            'Body': Mock(read=lambda: large_image)
        }
        
        result = query_handler.fetch_image_from_s3('s3://bucket/large.jpg')
        assert result is None


class TestPrepareMultimodalContent:
    """Tests for prepare_multimodal_content function"""
    
    @patch.object(query_handler, 'fetch_image_from_s3')
    @patch.object(query_handler, 'get_text_content')
    def test_prepares_mixed_content(self, mock_get_text, mock_fetch_image):
        """Test preparing multimodal content with images and text"""
        mock_fetch_image.return_value = b"fake image data"
        mock_get_text.return_value = "Text content here"
        
        sources = [
            {
                'metadata': {
                    'fileName': 'page1.png',
                    'modalityType': 'IMAGE',
                    'sourceS3Uri': 's3://bucket/page1.png',
                    'isPdf': True,
                    'processedPage': 1
                },
                'similarity': 0.95
            },
            {
                'metadata': {
                    'fileName': 'document.txt',
                    'modalityType': 'TEXT',
                    'sourceS3Uri': 's3://bucket/document.txt'
                },
                'similarity': 0.87
            }
        ]
        
        result = query_handler.prepare_multimodal_content("test query", sources)
        
        # Should have image block + text block
        assert len(result) == 2
        assert result[0]['type'] == 'image'
        assert result[0]['source']['type'] == 'base64'
        assert result[1]['type'] == 'text'
        assert 'test query' in result[1]['text']
        assert 'Page 1' in result[1]['text']
    
    @patch.object(query_handler, 'fetch_image_from_s3')
    def test_handles_regular_images(self, mock_fetch_image):
        """Test handling regular images (not PDF pages)"""
        mock_fetch_image.return_value = b"fake image data"
        
        sources = [
            {
                'metadata': {
                    'fileName': 'diagram.png',
                    'modalityType': 'IMAGE',
                    'sourceS3Uri': 's3://bucket/diagram.png'
                    # Note: No isPdf flag for regular images
                },
                'similarity': 0.92
            },
            {
                'metadata': {
                    'fileName': 'photo.jpg',
                    'modalityType': 'IMAGE',
                    'sourceS3Uri': 's3://bucket/photo.jpg'
                },
                'similarity': 0.88
            }
        ]
        
        result = query_handler.prepare_multimodal_content("test query", sources)
        
        # Should have 2 image blocks + 1 text block
        assert len(result) == 3
        assert result[0]['type'] == 'image'
        assert result[0]['source']['media_type'] == 'image/png'
        assert result[1]['type'] == 'image'
        assert result[1]['source']['media_type'] == 'image/jpeg'
        assert result[2]['type'] == 'text'
        assert 'diagram.png' in result[2]['text']
        assert 'photo.jpg' in result[2]['text']
    
    @patch.object(query_handler, 'fetch_image_from_s3')
    def test_handles_failed_image_fetch(self, mock_fetch_image):
        """Test handling when image fetch fails"""
        mock_fetch_image.return_value = None
        
        sources = [
            {
                'metadata': {
                    'fileName': 'image.jpg',
                    'modalityType': 'IMAGE',
                    'sourceS3Uri': 's3://bucket/image.jpg'
                },
                'similarity': 0.95
            }
        ]
        
        result = query_handler.prepare_multimodal_content("test query", sources)
        
        # Should only have text block (no image)
        assert len(result) == 1
        assert result[0]['type'] == 'text'
    
    @patch.object(query_handler, 'fetch_image_from_s3')
    @patch.object(query_handler, 'get_text_content')
    def test_handles_all_modalities(self, mock_get_text, mock_fetch_image):
        """Test handling all content types together"""
        mock_fetch_image.return_value = b"fake image data"
        mock_get_text.return_value = "Text content"
        
        sources = [
            {
                'metadata': {
                    'fileName': 'diagram.png',
                    'modalityType': 'IMAGE',
                    'sourceS3Uri': 's3://bucket/diagram.png'
                },
                'similarity': 0.95
            },
            {
                'metadata': {
                    'fileName': 'notes.txt',
                    'modalityType': 'TEXT',
                    'sourceS3Uri': 's3://bucket/notes.txt'
                },
                'similarity': 0.90
            },
            {
                'metadata': {
                    'fileName': 'video.mp4',
                    'modalityType': 'VIDEO',
                    'sourceS3Uri': 's3://bucket/video.mp4',
                    'segmentIndex': 0,
                    'segmentStartSeconds': 0.0,
                    'segmentEndSeconds': 5.0
                },
                'similarity': 0.85
            }
        ]
        
        result = query_handler.prepare_multimodal_content("test query", sources)
        
        # Should have 1 image block + 1 text block
        assert len(result) == 2
        assert result[0]['type'] == 'image'
        assert result[1]['type'] == 'text'
        # Text block should mention all sources
        assert 'diagram.png' in result[1]['text']
        assert 'notes.txt' in result[1]['text']
        assert 'Text content' in result[1]['text']
        assert 'video.mp4' in result[1]['text']
        assert '0.0s - 5.0s' in result[1]['text']


class TestFormatSources:
    """Tests for format_sources function"""
    
    def test_formats_video_source(self):
        """Test formatting video source"""
        sources = [
            {
                'metadata': {
                    'fileName': 'video.mp4',
                    'modalityType': 'VIDEO',
                    'segmentIndex': 2,
                    'segmentStartSeconds': 10.5,
                    'segmentEndSeconds': 15.5
                },
                'similarity': 0.95
            }
        ]
        
        result = query_handler.format_sources(sources)
        
        assert len(result) == 1
        assert result[0]['key'] == 'video.mp4'
        assert result[0]['similarity'] == 0.95
        # Check for timestamp format (MM:SS-MM:SS)
        assert '0:10-0:15' in result[0]['text_preview']
    
    def test_formats_text_source(self):
        """Test formatting text source"""
        sources = [
            {
                'metadata': {
                    'fileName': 'document.txt',
                    'modalityType': 'TEXT',
                    'segmentIndex': 0,
                    'segmentStartCharPosition': 0,
                    'segmentEndCharPosition': 1000
                },
                'similarity': 0.87
            }
        ]
        
        result = query_handler.format_sources(sources)
        
        assert len(result) == 1
        assert result[0]['key'] == 'document.txt'
        # Check for line number format (~Lines X-Y)
        assert '~Lines' in result[0]['text_preview']
    
    def test_formats_multiple_sources(self):
        """Test formatting multiple sources"""
        sources = [
            {
                'metadata': {'fileName': 'file1.jpg', 'modalityType': 'IMAGE'},
                'similarity': 0.95
            },
            {
                'metadata': {'fileName': 'file2.mp3', 'modalityType': 'AUDIO'},
                'similarity': 0.85
            }
        ]
        
        result = query_handler.format_sources(sources)
        
        assert len(result) == 2
        assert result[0]['key'] == 'file1.jpg'
        assert result[1]['key'] == 'file2.mp3'


class TestCreateResponse:
    """Tests for create_response function"""
    
    def test_creates_success_response(self):
        """Test creating successful response"""
        data = {'answer': 'test answer', 'sources': []}
        
        result = query_handler.create_response(200, data)
        
        assert result['statusCode'] == 200
        assert 'headers' in result
        assert result['headers']['Content-Type'] == 'application/json'
        assert result['headers']['Access-Control-Allow-Origin'] == '*'
        
        body = json.loads(result['body'])
        assert body['answer'] == 'test answer'
    
    def test_creates_error_response(self):
        """Test creating error response"""
        data = {'error': 'Something went wrong'}
        
        result = query_handler.create_response(500, data)
        
        assert result['statusCode'] == 500
        body = json.loads(result['body'])
        assert body['error'] == 'Something went wrong'


class TestCreateNoResultsResponse:
    """Tests for create_no_results_response function"""
    
    def test_no_sources_at_all(self):
        """Test response when no sources found"""
        result = query_handler.create_no_results_response("test query", 0)
        
        assert "couldn't find any information" in result
        assert "knowledge base appears to be empty" in result
        assert "uploaded to the S3 bucket" in result
    
    def test_sources_below_threshold(self):
        """Test response when sources found but below threshold"""
        result = query_handler.create_no_results_response("test query", 5)
        
        assert "couldn't find relevant information" in result
        assert "5 potential matches" in result
        assert "below 60% similarity" in result
        assert "different keywords" in result


class TestHandler:
    """Tests for main handler function"""
    
    @patch.object(query_handler, 'call_claude_multimodal')
    @patch.object(query_handler, 'prepare_multimodal_content')
    @patch.object(query_handler, 'simple_search')
    @patch.object(query_handler, 'embed_query')
    def test_successful_query(self, mock_embed, mock_search, mock_prepare, mock_claude):
        """Test successful query processing"""
        # Setup mocks
        mock_embed.return_value = [0.1] * 1024
        mock_search.return_value = [
            {
                'metadata': {
                    'fileName': 'test.mp4',
                    'modalityType': 'VIDEO',
                    'segmentStartSeconds': 0.0,
                    'segmentEndSeconds': 5.0
                },
                'similarity': 0.95,
                'embedding': [0.1] * 1024
            }
        ]
        mock_prepare.return_value = [
            {"type": "text", "text": "test prompt"}
        ]
        mock_claude.return_value = 'This is the answer.'
        
        # Create event
        event = {
            'body': json.dumps({
                'query': 'What is this video about?',
                'dimension': 1024,
                'hierarchical': False
            })
        }
        
        # Call handler
        result = query_handler.handler(event, None)
        
        # Verify response
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['answer'] == 'This is the answer.'
        assert len(body['sources']) == 1
        assert body['sources'][0]['key'] == 'test.mp4'
        assert body['model'] == os.environ['LLM_MODEL_ID']
        assert body['query'] == 'What is this video about?'
    
    def test_missing_query(self):
        """Test error handling for missing query"""
        event = {
            'body': json.dumps({})
        }
        
        result = query_handler.handler(event, None)
        
        assert result['statusCode'] == 400
        body = json.loads(result['body'])
        assert 'error' in body
    
    @patch.object(query_handler, 'simple_search')
    @patch.object(query_handler, 'embed_query')
    def test_no_results_found(self, mock_embed, mock_search):
        """Test handling when no relevant sources found"""
        mock_embed.return_value = [0.1] * 1024
        
        # Return sources with low similarity (below 60% threshold)
        mock_search.return_value = [
            {
                'metadata': {'fileName': 'test.txt', 'modalityType': 'TEXT'},
                'similarity': 0.45,  # Below 60% threshold
                'embedding': [0.1] * 1024
            }
        ]
        
        event = {
            'body': json.dumps({
                'query': 'something not in the knowledge base',
                'dimension': 1024,
                'hierarchical': False
            })
        }
        
        result = query_handler.handler(event, None)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['resultsFound'] == 0
        assert len(body['sources']) == 0
        assert "couldn't find relevant information" in body['answer']
        assert "1 potential matches" in body['answer']  # 1 source found but filtered out
    
    @patch.object(query_handler, 'embed_query')
    def test_error_handling(self, mock_embed):
        """Test error handling in handler"""
        mock_embed.side_effect = Exception("Embedding failed")
        
        event = {
            'body': json.dumps({
                'query': 'test query'
            })
        }
        
        result = query_handler.handler(event, None)
        
        assert result['statusCode'] == 500
        body = json.loads(result['body'])
        assert 'error' in body


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
