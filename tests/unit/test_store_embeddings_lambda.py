"""
Unit tests for Lambda 3: Store Embeddings
"""

import pytest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock, call
import numpy as np
import importlib.util

# Set required environment variables before importing
os.environ['VECTOR_BUCKET'] = 'test-vector-bucket'
os.environ['EMBEDDING_DIMENSIONS'] = '256,384,1024,3072'

# Import the store_embeddings module directly to avoid name collision
store_embeddings_path = os.path.join(os.path.dirname(__file__), '../../lambda/embedder/store_embeddings/index.py')
spec = importlib.util.spec_from_file_location("store_embeddings", store_embeddings_path)
store_embeddings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store_embeddings)


class TestParseS3Uri:
    """Tests for parse_s3_uri function"""
    
    def test_basic_uri(self):
        """Test parsing basic S3 URI"""
        bucket, prefix = store_embeddings.parse_s3_uri('s3://my-bucket/my-prefix')
        assert bucket == 'my-bucket'
        assert prefix == 'my-prefix'
    
    def test_nested_prefix(self):
        """Test parsing URI with nested prefix"""
        bucket, prefix = store_embeddings.parse_s3_uri('s3://my-bucket/path/to/files')
        assert bucket == 'my-bucket'
        assert prefix == 'path/to/files'
    
    def test_no_prefix(self):
        """Test parsing URI with no prefix"""
        bucket, prefix = store_embeddings.parse_s3_uri('s3://my-bucket')
        assert bucket == 'my-bucket'
        assert prefix == ''


class TestReadResultFile:
    """Tests for read_result_file function"""
    
    @patch.object(store_embeddings, 's3_client')
    def test_reads_result_file(self, mock_s3):
        """Test reading segmented-embedding-result.json"""
        mock_result = {
            'sourceFileUri': 's3://bucket/file.mp4',
            'embeddingDimension': 3072,
            'embeddingResults': [
                {
                    'embeddingType': 'VIDEO',
                    'status': 'SUCCESS',
                    'outputFileUri': 's3://bucket/output/embedding-video.jsonl'
                }
            ]
        }
        
        mock_s3.get_object.return_value = {
            'Body': Mock(read=lambda: json.dumps(mock_result).encode('utf-8'))
        }
        
        result = store_embeddings.read_result_file('bucket', 'prefix')
        
        assert result == mock_result
        mock_s3.get_object.assert_called_once_with(
            Bucket='bucket',
            Key='prefix/segmented-embedding-result.json'
        )


class TestCreateCombinedMetadata:
    """Tests for create_combined_metadata function"""
    
    def test_combines_all_metadata_sources(self):
        """Test that metadata from all sources is combined"""
        source_metadata = {
            'sourceS3Uri': 's3://bucket/video.mp4',
            'fileName': 'video.mp4',
            'fileType': '.mp4',
            'fileSize': 1024000,
            'uploadTimestamp': '2024-01-15T10:30:00',
            'contentType': 'video/mp4',
            'objectId': 'video_mp4_20240115103000'
        }
        
        segment_metadata = {
            'segmentIndex': 0,
            'segmentStartSeconds': 0.0,
            'segmentEndSeconds': 5.0
        }
        
        result = store_embeddings.create_combined_metadata(
            source_metadata,
            segment_metadata,
            'VIDEO',
            1024
        )
        
        # From source metadata
        assert result['sourceS3Uri'] == 's3://bucket/video.mp4'
        assert result['fileName'] == 'video.mp4'
        assert result['fileType'] == '.mp4'
        assert result['fileSize'] == 1024000
        assert result['objectId'] == 'video_mp4_20240115103000'
        
        # From segment metadata
        assert result['segmentIndex'] == 0
        assert result['segmentStartSeconds'] == 0.0
        assert result['segmentEndSeconds'] == 5.0
        
        # From processing
        assert result['modalityType'] == 'VIDEO'
        assert result['embeddingDimension'] == 1024
        assert 'processingTimestamp' in result
    
    def test_text_segment_metadata(self):
        """Test text-specific segment metadata"""
        segment_metadata = {
            'segmentIndex': 0,
            'segmentStartCharPosition': 0,
            'segmentEndCharPosition': 1000,
            'truncatedCharLength': 950
        }
        
        result = store_embeddings.create_combined_metadata(
            {'objectId': 'test'},
            segment_metadata,
            'TEXT',
            256
        )
        
        assert result['segmentStartCharPosition'] == 0
        assert result['segmentEndCharPosition'] == 1000
        assert result['truncatedCharLength'] == 950
    
    def test_video_segment_metadata(self):
        """Test video-specific segment metadata"""
        segment_metadata = {
            'segmentIndex': 2,
            'segmentStartSeconds': 10.0,
            'segmentEndSeconds': 15.0
        }
        
        result = store_embeddings.create_combined_metadata(
            {'objectId': 'test'},
            segment_metadata,
            'VIDEO',
            384
        )
        
        assert result['segmentStartSeconds'] == 10.0
        assert result['segmentEndSeconds'] == 15.0


class TestProcessSegment:
    """Tests for process_segment function"""
    
    @patch.object(store_embeddings, 'store_in_vector_index')
    @patch.object(store_embeddings, 'create_multi_dimensional_embeddings')
    def test_processes_single_segment(self, mock_create_embeddings, mock_store):
        """Test processing a single segment"""
        # Create mock 3072-dim embedding
        embedding_3072 = np.random.randn(3072).tolist()
        
        segment_data = {
            'embedding': embedding_3072,
            'segmentMetadata': {
                'segmentIndex': 0,
                'segmentStartSeconds': 0.0,
                'segmentEndSeconds': 5.0
            },
            'status': 'SUCCESS'
        }
        
        source_metadata = {
            'objectId': 'test_video',
            'fileName': 'test.mp4'
        }
        
        # Mock the multi-dimensional embeddings
        mock_create_embeddings.return_value = {
            256: [0.1] * 256,
            384: [0.1] * 384,
            1024: [0.1] * 1024,
            3072: embedding_3072
        }
        
        result = store_embeddings.process_segment(
            segment_data,
            source_metadata,
            'VIDEO'
        )
        
        # Should return 4 (number of dimensions stored)
        assert result == 4
        
        # Should call store_in_vector_index 4 times
        assert mock_store.call_count == 4
    
    @patch.object(store_embeddings, 'store_in_vector_index')
    @patch.object(store_embeddings, 'create_multi_dimensional_embeddings')
    def test_stores_all_dimensions(self, mock_create_embeddings, mock_store):
        """Test that all dimensions are stored"""
        embedding_3072 = np.random.randn(3072).tolist()
        
        mock_create_embeddings.return_value = {
            256: [0.1] * 256,
            384: [0.1] * 384,
            1024: [0.1] * 1024,
            3072: embedding_3072
        }
        
        segment_data = {
            'embedding': embedding_3072,
            'segmentMetadata': {'segmentIndex': 0},
            'status': 'SUCCESS'
        }
        
        store_embeddings.process_segment(
            segment_data,
            {'objectId': 'test'},
            'IMAGE'
        )
        
        # Verify each dimension was stored
        stored_dimensions = [call[0][0] for call in mock_store.call_args_list]
        assert 256 in stored_dimensions
        assert 384 in stored_dimensions
        assert 1024 in stored_dimensions
        assert 3072 in stored_dimensions


class TestStoreInVectorIndex:
    """Tests for store_in_vector_index function"""
    
    @patch.object(store_embeddings, 's3_client')
    def test_stores_embedding(self, mock_s3):
        """Test storing embedding in S3"""
        embedding = [0.1] * 256
        metadata = {
            'objectId': 'test_image_123',
            'segmentIndex': 0,
            'fileName': 'test.jpg'
        }
        
        store_embeddings.store_in_vector_index(256, embedding, metadata)
        
        # Verify S3 put_object was called
        mock_s3.put_object.assert_called_once()
        call_args = mock_s3.put_object.call_args
        
        assert call_args[1]['Bucket'] == store_embeddings.VECTOR_BUCKET
        assert 'embeddings-256d' in call_args[1]['Key']
        assert 'test_image_123' in call_args[1]['Key']
        
        # Verify data structure
        stored_data = json.loads(call_args[1]['Body'])
        assert 'embedding' in stored_data
        assert 'metadata' in stored_data
        assert stored_data['embedding'] == embedding
        assert stored_data['metadata'] == metadata
    
    @patch.object(store_embeddings, 's3_client')
    def test_creates_correct_key_structure(self, mock_s3):
        """Test that S3 key structure is correct"""
        metadata = {
            'objectId': 'video_mp4_20240115',
            'segmentIndex': 3
        }
        
        store_embeddings.store_in_vector_index(1024, [0.1] * 1024, metadata)
        
        key = mock_s3.put_object.call_args[1]['Key']
        
        # Should be: embeddings-1024d/video_mp4_20240115/segment_3.json
        assert key.startswith('embeddings-1024d/')
        assert 'video_mp4_20240115' in key
        assert 'segment_3.json' in key


class TestProcessModalityEmbeddings:
    """Tests for process_modality_embeddings function"""
    
    @patch.object(store_embeddings, 'process_segment')
    @patch.object(store_embeddings, 's3_client')
    def test_processes_multiple_segments(self, mock_s3, mock_process_segment):
        """Test processing multiple segments from JSONL"""
        # Mock JSONL content with 3 segments
        jsonl_content = '\n'.join([
            json.dumps({
                'embedding': [0.1] * 3072,
                'segmentMetadata': {'segmentIndex': 0},
                'status': 'SUCCESS'
            }),
            json.dumps({
                'embedding': [0.2] * 3072,
                'segmentMetadata': {'segmentIndex': 1},
                'status': 'SUCCESS'
            }),
            json.dumps({
                'embedding': [0.3] * 3072,
                'segmentMetadata': {'segmentIndex': 2},
                'status': 'SUCCESS'
            })
        ])
        
        mock_s3.get_object.return_value = {
            'Body': Mock(read=lambda: jsonl_content.encode('utf-8'))
        }
        
        mock_process_segment.return_value = 4  # 4 dimensions per segment
        
        embedding_result = {
            'outputFileUri': 's3://bucket/output/embedding-video.jsonl',
            'embeddingType': 'VIDEO',
            'status': 'SUCCESS'
        }
        
        count = store_embeddings.process_modality_embeddings(
            embedding_result,
            {'objectId': 'test'},
            'bucket',
            'prefix'
        )
        
        # Should process 3 segments
        assert mock_process_segment.call_count == 3
        # Total count: 3 segments × 4 dimensions = 12
        assert count == 12
    
    @patch.object(store_embeddings, 'process_segment')
    @patch.object(store_embeddings, 's3_client')
    def test_skips_failed_segments(self, mock_s3, mock_process_segment):
        """Test that failed segments are skipped"""
        jsonl_content = '\n'.join([
            json.dumps({
                'embedding': [0.1] * 3072,
                'segmentMetadata': {'segmentIndex': 0},
                'status': 'SUCCESS'
            }),
            json.dumps({
                'segmentMetadata': {'segmentIndex': 1},
                'status': 'FAILURE',
                'failureReason': 'Invalid content'
            }),
            json.dumps({
                'embedding': [0.3] * 3072,
                'segmentMetadata': {'segmentIndex': 2},
                'status': 'SUCCESS'
            })
        ])
        
        mock_s3.get_object.return_value = {
            'Body': Mock(read=lambda: jsonl_content.encode('utf-8'))
        }
        
        mock_process_segment.return_value = 4
        
        embedding_result = {
            'outputFileUri': 's3://bucket/output/embedding-text.jsonl',
            'embeddingType': 'TEXT',
            'status': 'PARTIAL_SUCCESS'
        }
        
        store_embeddings.process_modality_embeddings(
            embedding_result,
            {'objectId': 'test'},
            'bucket',
            'prefix'
        )
        
        # Should only process 2 successful segments
        assert mock_process_segment.call_count == 2


class TestHandler:
    """Tests for main handler function"""
    
    @patch.object(store_embeddings, 'process_modality_embeddings')
    @patch.object(store_embeddings, 'read_result_file')
    def test_successful_processing(self, mock_read_result, mock_process_modality):
        """Test successful end-to-end processing"""
        mock_read_result.return_value = {
            'sourceFileUri': 's3://bucket/video.mp4',
            'embeddingDimension': 3072,
            'embeddingResults': [
                {
                    'embeddingType': 'VIDEO',
                    'status': 'SUCCESS',
                    'outputFileUri': 's3://bucket/output/embedding-video.jsonl'
                }
            ]
        }
        
        mock_process_modality.return_value = 12  # 3 segments × 4 dimensions
        
        event = {
            'outputS3Uri': 's3://output-bucket/job123',
            'metadata': {
                'objectId': 'video_mp4_123',
                'fileName': 'video.mp4'
            }
        }
        
        result = store_embeddings.handler(event, None)
        
        assert result['statusCode'] == 200
        assert result['status'] == 'SUCCESS'
        assert result['embeddingsStored'] == 12
        assert result['dimensions'] == [256, 384, 1024, 3072]
    
    @patch.object(store_embeddings, 'process_modality_embeddings')
    @patch.object(store_embeddings, 'read_result_file')
    def test_processes_multiple_modalities(self, mock_read_result, mock_process_modality):
        """Test processing multiple modalities (e.g., video with separate audio)"""
        mock_read_result.return_value = {
            'embeddingResults': [
                {
                    'embeddingType': 'VIDEO',
                    'status': 'SUCCESS',
                    'outputFileUri': 's3://bucket/embedding-video.jsonl'
                },
                {
                    'embeddingType': 'AUDIO',
                    'status': 'SUCCESS',
                    'outputFileUri': 's3://bucket/embedding-audio.jsonl'
                }
            ]
        }
        
        mock_process_modality.return_value = 8
        
        event = {
            'outputS3Uri': 's3://bucket/output',
            'metadata': {'objectId': 'test'}
        }
        
        result = store_embeddings.handler(event, None)
        
        # Should process both modalities
        assert mock_process_modality.call_count == 2
        assert result['embeddingsStored'] == 16  # 8 per modality
    
    @patch.object(store_embeddings, 'read_result_file')
    def test_error_handling(self, mock_read_result):
        """Test error handling in handler"""
        mock_read_result.side_effect = Exception("S3 read error")
        
        event = {
            'outputS3Uri': 's3://bucket/output',
            'metadata': {'objectId': 'test'}
        }
        
        result = store_embeddings.handler(event, None)
        
        assert result['statusCode'] == 500
        assert result['status'] == 'FAILED'
        assert 'error' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
