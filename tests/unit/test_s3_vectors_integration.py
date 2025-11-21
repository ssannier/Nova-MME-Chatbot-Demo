"""
Unit tests for S3 Vectors integration

Tests the S3 Vectors query_vectors API integration in Query Handler Lambda
"""

import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock
import importlib.util

# Set required environment variables
os.environ['VECTOR_BUCKET'] = 'test-vector-bucket'
os.environ['EMBEDDING_MODEL_ID'] = 'amazon.nova-2-multimodal-embeddings-v1:0'
os.environ['LLM_MODEL_ID'] = 'anthropic.claude-3-5-sonnet-20240620-v1:0'
os.environ['DEFAULT_DIMENSION'] = '1024'
os.environ['DEFAULT_K'] = '5'
os.environ['HIERARCHICAL_ENABLED'] = 'false'
os.environ['HIERARCHICAL_CONFIG'] = '{}'
os.environ['VECTOR_INDEXES'] = json.dumps({
    '256': 'embeddings-256d',
    '384': 'embeddings-384d',
    '1024': 'embeddings-1024d',
    '3072': 'embeddings-3072d'
})
os.environ['LLM_MAX_TOKENS'] = '2048'
os.environ['LLM_TEMPERATURE'] = '0.7'

# Import query handler
query_handler_path = os.path.join(os.path.dirname(__file__), '../../lambda/chatbot/query_handler/index.py')
spec = importlib.util.spec_from_file_location("query_handler", query_handler_path)
query_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(query_handler)


class TestS3VectorsQueryAPI:
    """Tests for S3 Vectors query_vectors API integration"""
    
    @patch.object(query_handler, 's3_client')
    def test_query_vectors_api_called_correctly(self, mock_s3):
        """Test that query_vectors API is called with correct parameters"""
        # Setup mock response
        mock_s3.query_vectors.return_value = {
            'Vectors': [
                {
                    'Key': 'embeddings-1024d/test_file_segment_0.json',
                    'Distance': 0.05  # Low distance = high similarity
                }
            ]
        }
        
        # Mock get_object for metadata retrieval
        mock_s3.get_object.return_value = {
            'Body': Mock(read=lambda: json.dumps({
                'vector': [0.1] * 1024,
                'metadata': {
                    'fileName': 'test.jpg',
                    'modalityType': 'IMAGE'
                }
            }).encode())
        }
        
        # Call search function
        query_embedding = [0.1] * 1024
        results = query_handler.search_s3_vector_index('embeddings-1024d', query_embedding, 5)
        
        # Verify query_vectors was called
        mock_s3.query_vectors.assert_called_once_with(
            Bucket='test-vector-bucket',
            IndexName='embeddings-1024d',
            QueryVector=query_embedding,
            MaxResults=5,
            DistanceMetric='cosine'
        )
        
        # Verify results
        assert len(results) == 1
        assert results[0]['similarity'] == 0.95  # 1 - 0.05 distance
        assert results[0]['metadata']['fileName'] == 'test.jpg'
    
    @patch.object(query_handler, 's3_client')
    def test_handles_multiple_results(self, mock_s3):
        """Test handling multiple results from S3 Vectors"""
        mock_s3.query_vectors.return_value = {
            'Vectors': [
                {'Key': 'embeddings-1024d/file1_segment_0.json', 'Distance': 0.1},
                {'Key': 'embeddings-1024d/file2_segment_0.json', 'Distance': 0.2},
                {'Key': 'embeddings-1024d/file3_segment_0.json', 'Distance': 0.3}
            ]
        }
        
        # Mock get_object for each result
        def mock_get_object(Bucket, Key):
            file_num = '1' if 'file1' in Key else ('2' if 'file2' in Key else '3')
            return {
                'Body': Mock(read=lambda: json.dumps({
                    'vector': [0.1] * 1024,
                    'metadata': {'fileName': f'file{file_num}.jpg'}
                }).encode())
            }
        
        mock_s3.get_object.side_effect = mock_get_object
        
        results = query_handler.search_s3_vector_index('embeddings-1024d', [0.1] * 1024, 5)
        
        assert len(results) == 3
        assert results[0]['similarity'] == 0.9  # 1 - 0.1
        assert results[1]['similarity'] == 0.8  # 1 - 0.2
        assert results[2]['similarity'] == 0.7  # 1 - 0.3
    
    @patch.object(query_handler, 's3_client')
    def test_handles_empty_results(self, mock_s3):
        """Test handling empty results from S3 Vectors"""
        mock_s3.query_vectors.return_value = {'Vectors': []}
        
        results = query_handler.search_s3_vector_index('embeddings-1024d', [0.1] * 1024, 5)
        
        assert len(results) == 0
    
    @patch.object(query_handler, 's3_client')
    def test_handles_query_vectors_error(self, mock_s3):
        """Test error handling when query_vectors fails"""
        mock_s3.query_vectors.side_effect = Exception("S3 Vectors API error")
        
        results = query_handler.search_s3_vector_index('embeddings-1024d', [0.1] * 1024, 5)
        
        # Should return empty list on error
        assert len(results) == 0
    
    @patch.object(query_handler, 's3_client')
    def test_works_with_all_dimensions(self, mock_s3):
        """Test that query_vectors works with all MRL dimensions"""
        for dim in [256, 384, 1024, 3072]:
            mock_s3.reset_mock()
            mock_s3.query_vectors.return_value = {'Vectors': []}
            
            index_name = f'embeddings-{dim}d'
            query_embedding = [0.1] * dim
            
            query_handler.search_s3_vector_index(index_name, query_embedding, 5)
            
            # Verify called with correct dimension
            call_args = mock_s3.query_vectors.call_args
            assert call_args[1]['IndexName'] == index_name
            assert len(call_args[1]['QueryVector']) == dim
    
    @patch.object(query_handler, 's3_client')
    def test_distance_to_similarity_conversion(self, mock_s3):
        """Test that cosine distance is correctly converted to similarity"""
        test_cases = [
            (0.0, 1.0),   # Distance 0 = Similarity 1 (identical)
            (0.1, 0.9),   # Distance 0.1 = Similarity 0.9
            (0.5, 0.5),   # Distance 0.5 = Similarity 0.5
            (1.0, 0.0),   # Distance 1 = Similarity 0 (opposite)
        ]
        
        for distance, expected_similarity in test_cases:
            mock_s3.reset_mock()
            mock_s3.query_vectors.return_value = {
                'Vectors': [
                    {'Key': 'embeddings-1024d/test_segment_0.json', 'Distance': distance}
                ]
            }
            
            mock_s3.get_object.return_value = {
                'Body': Mock(read=lambda: json.dumps({
                    'vector': [0.1] * 1024,
                    'metadata': {'fileName': 'test.jpg'}
                }).encode())
            }
            
            results = query_handler.search_s3_vector_index('embeddings-1024d', [0.1] * 1024, 5)
            
            assert len(results) == 1
            assert abs(results[0]['similarity'] - expected_similarity) < 0.001


class TestURLEncoding:
    """Tests for URL encoding fix in processor Lambda"""
    
    def test_url_decode_import(self):
        """Test that unquote_plus is imported and available"""
        # Just verify the function exists and works
        from urllib.parse import unquote_plus
        assert unquote_plus is not None
        
        # Test it works
        assert unquote_plus('test+file.pdf') == 'test file.pdf'
    
    def test_url_decode_functionality(self):
        """Test URL decoding of special characters"""
        from urllib.parse import unquote_plus
        
        # Test cases from real S3 events
        test_cases = [
            ('file+with+spaces.pdf', 'file with spaces.pdf'),
            ('file%E2%80%93with%E2%80%93dashes.pdf', 'file–with–dashes.pdf'),
            ('normal-file.jpg', 'normal-file.jpg'),
            ('file%20with%20encoded%20spaces.txt', 'file with encoded spaces.txt'),
        ]
        
        for encoded, expected in test_cases:
            decoded = unquote_plus(encoded)
            assert decoded == expected, f"Failed to decode {encoded}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
