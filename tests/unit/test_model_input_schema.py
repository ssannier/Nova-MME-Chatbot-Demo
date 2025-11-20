"""
Schema validation tests for Nova MME async API requests

These tests ensure that the generated model inputs conform exactly
to the Nova MME async API schema requirements.
"""

import pytest
import sys
import os
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


class TestSchemaCompliance:
    """Tests to ensure generated JSON matches Nova MME async schema"""
    
    def test_required_top_level_fields(self):
        """Test that all required top-level fields are present"""
        result = processor.create_model_input('bucket', 'test.jpg', '.jpg')
        
        # Required fields
        assert 'schemaVersion' in result
        assert 'taskType' in result
        assert 'segmentedEmbeddingParams' in result
        
        # Correct values
        assert result['schemaVersion'] == 'nova-multimodal-embed-v1'
        assert result['taskType'] == 'SEGMENTED_EMBEDDING'
    
    def test_segmented_embedding_params_structure(self):
        """Test segmentedEmbeddingParams has required fields"""
        result = processor.create_model_input('bucket', 'test.jpg', '.jpg')
        
        params = result['segmentedEmbeddingParams']
        assert 'embeddingPurpose' in params
        assert 'embeddingDimension' in params
        
        # Valid values
        assert params['embeddingPurpose'] in [
            'GENERIC_INDEX', 'GENERIC_RETRIEVAL', 'TEXT_RETRIEVAL',
            'IMAGE_RETRIEVAL', 'VIDEO_RETRIEVAL', 'DOCUMENT_RETRIEVAL',
            'AUDIO_RETRIEVAL', 'CLASSIFICATION', 'CLUSTERING'
        ]
        assert params['embeddingDimension'] in [256, 384, 1024, 3072]
    
    def test_exactly_one_modality(self):
        """Test that exactly one modality is present"""
        test_cases = [
            ('test.jpg', '.jpg', 'image'),
            ('test.mp4', '.mp4', 'video'),
            ('test.mp3', '.mp3', 'audio'),
            ('test.txt', '.txt', 'text'),
        ]
        
        for filename, ext, expected_modality in test_cases:
            result = processor.create_model_input('bucket', filename, ext)
            params = result['segmentedEmbeddingParams']
            
            # Count modalities present
            modalities = ['text', 'image', 'video', 'audio']
            present = [m for m in modalities if m in params]
            
            assert len(present) == 1, f"Expected exactly 1 modality, found {len(present)}"
            assert present[0] == expected_modality


class TestImageSchema:
    """Test image-specific schema compliance"""
    
    def test_image_required_fields(self):
        """Test image config has all required fields"""
        result = processor.create_model_input('bucket', 'test.png', '.png')
        image = result['segmentedEmbeddingParams']['image']
        
        assert 'format' in image
        assert 'source' in image
        assert 'detailLevel' in image
    
    def test_image_format_values(self):
        """Test image format values are valid"""
        valid_formats = ['png', 'jpeg', 'gif', 'webp']
        
        test_cases = [
            ('.png', 'png'),
            ('.jpg', 'jpeg'),
            ('.jpeg', 'jpeg'),
            ('.gif', 'gif'),
            ('.webp', 'webp'),
        ]
        
        for ext, expected_format in test_cases:
            result = processor.create_model_input('bucket', f'test{ext}', ext)
            image = result['segmentedEmbeddingParams']['image']
            
            assert image['format'] == expected_format
            assert image['format'] in valid_formats
    
    def test_image_source_structure(self):
        """Test image source has correct S3 structure"""
        result = processor.create_model_input('bucket', 'test.png', '.png')
        source = result['segmentedEmbeddingParams']['image']['source']
        
        assert 's3Location' in source
        assert 'uri' in source['s3Location']
        assert source['s3Location']['uri'].startswith('s3://')
    
    def test_image_detail_level(self):
        """Test image detailLevel is valid"""
        result = processor.create_model_input('bucket', 'test.png', '.png')
        detail_level = result['segmentedEmbeddingParams']['image']['detailLevel']
        
        assert detail_level in ['STANDARD_IMAGE', 'DOCUMENT_IMAGE']


class TestVideoSchema:
    """Test video-specific schema compliance"""
    
    def test_video_required_fields(self):
        """Test video config has all required fields"""
        result = processor.create_model_input('bucket', 'test.mp4', '.mp4')
        video = result['segmentedEmbeddingParams']['video']
        
        assert 'format' in video
        assert 'source' in video
        assert 'embeddingMode' in video
        assert 'segmentationConfig' in video
    
    def test_video_format_values(self):
        """Test all video formats are valid"""
        valid_formats = ['mp4', 'mov', 'mkv', 'webm', 'flv', 'mpeg', 'mpg', 'wmv', '3gp']
        
        test_cases = [
            ('.mp4', 'mp4'), ('.mov', 'mov'), ('.mkv', 'mkv'),
            ('.webm', 'webm'), ('.flv', 'flv'), ('.mpeg', 'mpeg'),
            ('.mpg', 'mpg'), ('.wmv', 'wmv'), ('.3gp', '3gp'),
        ]
        
        for ext, expected_format in test_cases:
            result = processor.create_model_input('bucket', f'test{ext}', ext)
            video = result['segmentedEmbeddingParams']['video']
            
            assert video['format'] == expected_format
            assert video['format'] in valid_formats
    
    def test_video_embedding_mode(self):
        """Test video embeddingMode is valid"""
        result = processor.create_model_input('bucket', 'test.mp4', '.mp4')
        mode = result['segmentedEmbeddingParams']['video']['embeddingMode']
        
        assert mode in ['AUDIO_VIDEO_COMBINED', 'AUDIO_VIDEO_SEPARATE']
    
    def test_video_segmentation_config(self):
        """Test video segmentationConfig structure"""
        result = processor.create_model_input('bucket', 'test.mp4', '.mp4')
        seg_config = result['segmentedEmbeddingParams']['video']['segmentationConfig']
        
        assert 'durationSeconds' in seg_config
        assert isinstance(seg_config['durationSeconds'], int)
        assert 1 <= seg_config['durationSeconds'] <= 30


class TestAudioSchema:
    """Test audio-specific schema compliance"""
    
    def test_audio_required_fields(self):
        """Test audio config has all required fields"""
        result = processor.create_model_input('bucket', 'test.mp3', '.mp3')
        audio = result['segmentedEmbeddingParams']['audio']
        
        assert 'format' in audio
        assert 'source' in audio
        assert 'segmentationConfig' in audio
    
    def test_audio_format_values(self):
        """Test all audio formats are valid"""
        valid_formats = ['mp3', 'wav', 'ogg']
        
        test_cases = [
            ('.mp3', 'mp3'),
            ('.wav', 'wav'),
            ('.ogg', 'ogg'),
        ]
        
        for ext, expected_format in test_cases:
            result = processor.create_model_input('bucket', f'test{ext}', ext)
            audio = result['segmentedEmbeddingParams']['audio']
            
            assert audio['format'] == expected_format
            assert audio['format'] in valid_formats
    
    def test_audio_segmentation_config(self):
        """Test audio segmentationConfig structure"""
        result = processor.create_model_input('bucket', 'test.mp3', '.mp3')
        seg_config = result['segmentedEmbeddingParams']['audio']['segmentationConfig']
        
        assert 'durationSeconds' in seg_config
        assert isinstance(seg_config['durationSeconds'], int)
        assert 1 <= seg_config['durationSeconds'] <= 30


class TestTextSchema:
    """Test text-specific schema compliance"""
    
    def test_text_required_fields(self):
        """Test text config has all required fields"""
        result = processor.create_model_input('bucket', 'test.txt', '.txt')
        text = result['segmentedEmbeddingParams']['text']
        
        assert 'truncationMode' in text
        assert 'source' in text
        assert 'segmentationConfig' in text
    
    def test_text_truncation_mode(self):
        """Test text truncationMode is valid"""
        result = processor.create_model_input('bucket', 'test.txt', '.txt')
        mode = result['segmentedEmbeddingParams']['text']['truncationMode']
        
        assert mode in ['START', 'END', 'NONE']
    
    def test_text_segmentation_config(self):
        """Test text segmentationConfig structure"""
        result = processor.create_model_input('bucket', 'test.txt', '.txt')
        seg_config = result['segmentedEmbeddingParams']['text']['segmentationConfig']
        
        assert 'maxLengthChars' in seg_config
        assert isinstance(seg_config['maxLengthChars'], int)
        assert 800 <= seg_config['maxLengthChars'] <= 50000


class TestS3SourceStructure:
    """Test S3 source structure is consistent across all modalities"""
    
    def test_s3_uri_format(self):
        """Test S3 URI format is correct for all modalities"""
        test_cases = [
            ('images/photo.jpg', '.jpg', 'image'),
            ('videos/clip.mp4', '.mp4', 'video'),
            ('audio/song.mp3', '.mp3', 'audio'),
            ('docs/file.txt', '.txt', 'text'),
        ]
        
        for key, ext, modality in test_cases:
            result = processor.create_model_input('test-bucket', key, ext)
            source = result['segmentedEmbeddingParams'][modality]['source']
            
            assert 's3Location' in source
            assert 'uri' in source['s3Location']
            
            uri = source['s3Location']['uri']
            assert uri == f's3://test-bucket/{key}'
            assert uri.startswith('s3://')
            assert '://' in uri
            assert uri.count('://') == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
