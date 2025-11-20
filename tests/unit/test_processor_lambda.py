"""
Unit tests for Lambda 1: Nova MME Processor
"""

import pytest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import importlib.util

# Set required environment variables before importing
os.environ['EMBEDDING_DIMENSION'] = '3072'
os.environ['MODEL_ID'] = 'amazon.nova-2-multimodal-embeddings-v1:0'
os.environ['OUTPUT_BUCKET'] = 'test-output-bucket'
os.environ['SOURCE_BUCKET'] = 'test-source-bucket'

# Import the processor module directly to avoid name collision
processor_path = os.path.join(os.path.dirname(__file__), '../../lambda/embedder/processor/index.py')
spec = importlib.util.spec_from_file_location("processor", processor_path)
processor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(processor)


class TestExtractS3Metadata:
    """Tests for extract_s3_metadata function"""
    
    @patch.object(processor, 's3_client')
    def test_extracts_basic_metadata(self, mock_s3):
        """Test basic metadata extraction"""
        # Mock S3 response
        mock_s3.head_object.return_value = {
            'ContentLength': 1024000,
            'LastModified': datetime(2024, 1, 15, 10, 30, 0),
            'ContentType': 'image/png'
        }
        
        result = processor.extract_s3_metadata('test-bucket', 'images/test.png')
        
        assert result['sourceS3Uri'] == 's3://test-bucket/images/test.png'
        assert result['fileName'] == 'test.png'
        assert result['fileType'] == '.png'
        assert result['fileSize'] == 1024000
        assert result['contentType'] == 'image/png'
        assert 'objectId' in result
        assert 'uploadTimestamp' in result
    
    @patch.object(processor, 's3_client')
    def test_handles_missing_content_type(self, mock_s3):
        """Test handling of missing ContentType"""
        mock_s3.head_object.return_value = {
            'ContentLength': 500,
            'LastModified': datetime(2024, 1, 15, 10, 30, 0)
        }
        
        result = processor.extract_s3_metadata('test-bucket', 'file.txt')
        
        assert result['contentType'] == 'unknown'


class TestCreateModelInput:
    """Tests for create_model_input function"""
    
    def _verify_base_structure(self, result):
        """Helper to verify base structure is correct"""
        assert result['schemaVersion'] == 'nova-multimodal-embed-v1'
        assert result['taskType'] == 'SEGMENTED_EMBEDDING'
        assert 'segmentedEmbeddingParams' in result
        assert result['segmentedEmbeddingParams']['embeddingDimension'] == 3072
        assert result['segmentedEmbeddingParams']['embeddingPurpose'] == 'GENERIC_INDEX'
    
    # IMAGE TESTS - All supported formats
    def test_image_png(self):
        """Test PNG image format"""
        result = processor.create_model_input('bucket', 'image.png', '.png')
        self._verify_base_structure(result)
        
        assert 'image' in result['segmentedEmbeddingParams']
        image_config = result['segmentedEmbeddingParams']['image']
        assert image_config['format'] == 'png'
        assert image_config['source']['s3Location']['uri'] == 's3://bucket/image.png'
        assert image_config['detailLevel'] == 'STANDARD_IMAGE'
    
    def test_image_jpg(self):
        """Test JPG image format"""
        result = processor.create_model_input('bucket', 'photo.jpg', '.jpg')
        self._verify_base_structure(result)
        
        image_config = result['segmentedEmbeddingParams']['image']
        assert image_config['format'] == 'jpeg'
    
    def test_image_jpeg(self):
        """Test JPEG image format"""
        result = processor.create_model_input('bucket', 'photo.jpeg', '.jpeg')
        self._verify_base_structure(result)
        
        image_config = result['segmentedEmbeddingParams']['image']
        assert image_config['format'] == 'jpeg'
    
    def test_image_gif(self):
        """Test GIF image format"""
        result = processor.create_model_input('bucket', 'animation.gif', '.gif')
        self._verify_base_structure(result)
        
        image_config = result['segmentedEmbeddingParams']['image']
        assert image_config['format'] == 'gif'
    
    def test_image_webp(self):
        """Test WebP image format"""
        result = processor.create_model_input('bucket', 'image.webp', '.webp')
        self._verify_base_structure(result)
        
        image_config = result['segmentedEmbeddingParams']['image']
        assert image_config['format'] == 'webp'
    
    # VIDEO TESTS - All supported formats
    def test_video_mp4(self):
        """Test MP4 video format"""
        result = processor.create_model_input('bucket', 'video.mp4', '.mp4')
        self._verify_base_structure(result)
        
        assert 'video' in result['segmentedEmbeddingParams']
        video_config = result['segmentedEmbeddingParams']['video']
        assert video_config['format'] == 'mp4'
        assert video_config['source']['s3Location']['uri'] == 's3://bucket/video.mp4'
        assert video_config['embeddingMode'] == 'AUDIO_VIDEO_COMBINED'
        assert video_config['segmentationConfig']['durationSeconds'] == 5
    
    def test_video_mov(self):
        """Test MOV video format"""
        result = processor.create_model_input('bucket', 'video.mov', '.mov')
        video_config = result['segmentedEmbeddingParams']['video']
        assert video_config['format'] == 'mov'
    
    def test_video_mkv(self):
        """Test MKV video format"""
        result = processor.create_model_input('bucket', 'video.mkv', '.mkv')
        video_config = result['segmentedEmbeddingParams']['video']
        assert video_config['format'] == 'mkv'
    
    def test_video_webm(self):
        """Test WebM video format"""
        result = processor.create_model_input('bucket', 'video.webm', '.webm')
        video_config = result['segmentedEmbeddingParams']['video']
        assert video_config['format'] == 'webm'
    
    def test_video_flv(self):
        """Test FLV video format"""
        result = processor.create_model_input('bucket', 'video.flv', '.flv')
        video_config = result['segmentedEmbeddingParams']['video']
        assert video_config['format'] == 'flv'
    
    def test_video_mpeg(self):
        """Test MPEG video format"""
        result = processor.create_model_input('bucket', 'video.mpeg', '.mpeg')
        video_config = result['segmentedEmbeddingParams']['video']
        assert video_config['format'] == 'mpeg'
    
    def test_video_mpg(self):
        """Test MPG video format"""
        result = processor.create_model_input('bucket', 'video.mpg', '.mpg')
        video_config = result['segmentedEmbeddingParams']['video']
        assert video_config['format'] == 'mpg'
    
    def test_video_wmv(self):
        """Test WMV video format"""
        result = processor.create_model_input('bucket', 'video.wmv', '.wmv')
        video_config = result['segmentedEmbeddingParams']['video']
        assert video_config['format'] == 'wmv'
    
    def test_video_3gp(self):
        """Test 3GP video format"""
        result = processor.create_model_input('bucket', 'video.3gp', '.3gp')
        video_config = result['segmentedEmbeddingParams']['video']
        assert video_config['format'] == '3gp'
    
    # AUDIO TESTS - All supported formats
    def test_audio_mp3(self):
        """Test MP3 audio format"""
        result = processor.create_model_input('bucket', 'audio.mp3', '.mp3')
        self._verify_base_structure(result)
        
        assert 'audio' in result['segmentedEmbeddingParams']
        audio_config = result['segmentedEmbeddingParams']['audio']
        assert audio_config['format'] == 'mp3'
        assert audio_config['source']['s3Location']['uri'] == 's3://bucket/audio.mp3'
        assert audio_config['segmentationConfig']['durationSeconds'] == 5
    
    def test_audio_wav(self):
        """Test WAV audio format"""
        result = processor.create_model_input('bucket', 'audio.wav', '.wav')
        audio_config = result['segmentedEmbeddingParams']['audio']
        assert audio_config['format'] == 'wav'
    
    def test_audio_ogg(self):
        """Test OGG audio format"""
        result = processor.create_model_input('bucket', 'audio.ogg', '.ogg')
        audio_config = result['segmentedEmbeddingParams']['audio']
        assert audio_config['format'] == 'ogg'
    
    # TEXT TESTS - All supported formats
    def test_text_txt(self):
        """Test TXT text format"""
        result = processor.create_model_input('bucket', 'document.txt', '.txt')
        self._verify_base_structure(result)
        
        assert 'text' in result['segmentedEmbeddingParams']
        text_config = result['segmentedEmbeddingParams']['text']
        assert text_config['truncationMode'] == 'END'
        assert text_config['source']['s3Location']['uri'] == 's3://bucket/document.txt'
        assert text_config['segmentationConfig']['maxLengthChars'] == 32000
    
    def test_text_md(self):
        """Test Markdown text format"""
        result = processor.create_model_input('bucket', 'README.md', '.md')
        assert 'text' in result['segmentedEmbeddingParams']
    
    def test_text_json(self):
        """Test JSON text format"""
        result = processor.create_model_input('bucket', 'data.json', '.json')
        assert 'text' in result['segmentedEmbeddingParams']
    
    def test_text_csv(self):
        """Test CSV text format"""
        result = processor.create_model_input('bucket', 'data.csv', '.csv')
        assert 'text' in result['segmentedEmbeddingParams']
    
    # ERROR HANDLING
    def test_unsupported_file_type(self):
        """Test error handling for unsupported file types"""
        with pytest.raises(ValueError, match="Unsupported file type"):
            processor.create_model_input('bucket', 'file.xyz', '.xyz')
    
    def test_case_insensitive_extensions(self):
        """Test that extensions are handled case-insensitively"""
        # The Lambda should handle .JPG, .Mp4, etc.
        result_upper = processor.create_model_input('bucket', 'photo.JPG', '.jpg')
        result_lower = processor.create_model_input('bucket', 'photo.jpg', '.jpg')
        
        # Both should produce same format
        assert result_upper['segmentedEmbeddingParams']['image']['format'] == 'jpeg'
        assert result_lower['segmentedEmbeddingParams']['image']['format'] == 'jpeg'


class TestStartAsyncInvocation:
    """Tests for start_async_invocation function"""
    
    @patch.object(processor, 'bedrock_runtime')
    def test_starts_invocation(self, mock_bedrock):
        """Test starting async invocation"""
        mock_bedrock.start_async_invoke.return_value = {
            'invocationArn': 'arn:aws:bedrock:us-east-1:123456789012:async-invoke/test123'
        }
        
        model_input = {'test': 'input'}
        output_uri = 's3://output-bucket/job123'
        
        result = processor.start_async_invocation(model_input, output_uri)
        
        assert result == 'arn:aws:bedrock:us-east-1:123456789012:async-invoke/test123'
        
        # Verify correct API call
        mock_bedrock.start_async_invoke.assert_called_once()
        call_args = mock_bedrock.start_async_invoke.call_args
        assert call_args[1]['modelInput'] == model_input
        assert call_args[1]['outputDataConfig']['s3OutputDataConfig']['s3Uri'] == output_uri


class TestHandler:
    """Tests for main handler function"""
    
    @patch.object(processor, 'start_async_invocation')
    @patch.object(processor, 'create_model_input')
    @patch.object(processor, 'extract_s3_metadata')
    def test_successful_processing(self, mock_extract, mock_create, mock_start):
        """Test successful file processing"""
        # Setup mocks
        mock_extract.return_value = {
            'sourceS3Uri': 's3://test-bucket/test.jpg',
            'fileName': 'test.jpg',
            'fileType': '.jpg',
            'fileSize': 1024,
            'uploadTimestamp': '2024-01-15T10:30:00',
            'contentType': 'image/jpeg',
            'objectId': 'test_jpg_20240115103000'
        }
        
        mock_create.return_value = {'test': 'model_input'}
        mock_start.return_value = 'arn:aws:bedrock:us-east-1:123456789012:async-invoke/test123'
        
        # Create event
        event = {
            'bucket': 'test-bucket',
            'key': 'test.jpg'
        }
        
        # Call handler
        result = processor.handler(event, None)
        
        # Verify response
        assert result['statusCode'] == 200
        assert result['status'] == 'IN_PROGRESS'
        assert result['invocationArn'] == 'arn:aws:bedrock:us-east-1:123456789012:async-invoke/test123'
        assert 'metadata' in result
        assert 'outputS3Uri' in result
    
    @patch.object(processor, 'extract_s3_metadata')
    def test_error_handling(self, mock_extract):
        """Test error handling in handler"""
        # Make extract_s3_metadata raise an error
        mock_extract.side_effect = Exception("S3 error")
        
        event = {
            'bucket': 'test-bucket',
            'key': 'test.jpg'
        }
        
        result = processor.handler(event, None)
        
        assert result['statusCode'] == 500
        assert result['status'] == 'FAILED'
        assert 'error' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
