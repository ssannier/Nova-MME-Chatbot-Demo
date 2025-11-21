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
os.environ['LLM_MODEL_ID'] = 'anthropic.claude-3-5-sonnet-20241022-v2:0'
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


class TestCallClaude:
    """Tests for call_claude function"""
    
    @patch.object(query_handler, 'bedrock_runtime')
    def test_calls_claude(self, mock_bedrock):
        """Test Claude API call"""
        mock_bedrock.invoke_model.return_value = {
            'body': Mock(read=lambda: json.dumps({
                'content': [
                    {
                        'text': 'This is the answer from Claude.'
                    }
                ]
            }).encode())
        }
        
        result = query_handler.call_claude("test prompt")
        
        assert result == 'This is the answer from Claude.'
        
        # Verify correct API call
        mock_bedrock.invoke_model.assert_called_once()
        call_args = mock_bedrock.invoke_model.call_args
        body = json.loads(call_args[1]['body'])
        
        assert body['anthropic_version'] == 'bedrock-2023-05-31'
        assert body['max_tokens'] == 2048
        assert body['temperature'] == 0.7
        assert body['messages'][0]['role'] == 'user'
        assert body['messages'][0]['content'] == 'test prompt'


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
        assert 'VIDEO' in result[0]['text_preview']
        assert 'Segment: 2' in result[0]['text_preview']
        assert '10.5s' in result[0]['text_preview']
    
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
        assert 'TEXT' in result[0]['text_preview']
        assert 'Chars: 0-1000' in result[0]['text_preview']
    
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


class TestHandler:
    """Tests for main handler function"""
    
    @patch.object(query_handler, 'call_claude')
    @patch.object(query_handler, 'simple_search')
    @patch.object(query_handler, 'embed_query')
    def test_successful_query(self, mock_embed, mock_search, mock_claude):
        """Test successful query processing"""
        # Setup mocks
        mock_embed.return_value = [0.1] * 1024
        mock_search.return_value = [
            {
                'metadata': {
                    'fileName': 'test.mp4',
                    'modalityType': 'VIDEO'
                },
                'similarity': 0.95,
                'embedding': [0.1] * 1024
            }
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
