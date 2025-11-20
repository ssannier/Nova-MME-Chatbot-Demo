"""
Unit tests for embedding utilities (MRL truncation and normalization)
"""

import pytest
import numpy as np
import sys
import os

# Add lambda/shared to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../lambda/shared'))

from embedding_utils import (
    truncate_and_normalize,
    create_multi_dimensional_embeddings,
    validate_mrl_property
)


class TestTruncateAndNormalize:
    """Tests for truncate_and_normalize function"""
    
    def test_basic_truncation(self):
        """Test basic truncation and normalization"""
        # Create a simple 1024-dim embedding
        embedding = list(range(1, 1025))
        
        # Truncate to 256 dimensions
        result = truncate_and_normalize(embedding, 256)
        
        assert len(result) == 256
        assert isinstance(result, list)
        
        # Check that it's normalized (L2 norm should be 1.0)
        norm = np.linalg.norm(result)
        assert abs(norm - 1.0) < 1e-6
    
    def test_all_dimensions(self):
        """Test truncation to all standard dimensions"""
        embedding_3072 = np.random.randn(3072).tolist()
        
        for dim in [256, 384, 1024]:
            result = truncate_and_normalize(embedding_3072, dim)
            assert len(result) == dim
            
            # Verify normalization
            norm = np.linalg.norm(result)
            assert abs(norm - 1.0) < 1e-6
    
    def test_invalid_dimension(self):
        """Test error handling for invalid dimensions"""
        embedding = list(range(100))
        
        with pytest.raises(ValueError, match="less than target dimension"):
            truncate_and_normalize(embedding, 256)
    
    def test_zero_vector(self):
        """Test error handling for zero vector"""
        embedding = [0.0] * 1024
        
        with pytest.raises(ValueError, match="Cannot normalize zero vector"):
            truncate_and_normalize(embedding, 256)
    
    def test_preserves_direction(self):
        """Test that truncation preserves relative direction"""
        # Create embedding with known pattern
        embedding = [1.0] * 256 + [0.0] * 768
        
        result = truncate_and_normalize(embedding, 256)
        
        # All values should be equal (uniform direction)
        assert all(abs(result[0] - val) < 1e-6 for val in result)


class TestCreateMultiDimensionalEmbeddings:
    """Tests for create_multi_dimensional_embeddings function"""
    
    def test_creates_all_dimensions(self):
        """Test that all dimension variants are created"""
        embedding_3072 = np.random.randn(3072).tolist()
        
        result = create_multi_dimensional_embeddings(embedding_3072)
        
        assert len(result) == 4
        assert 256 in result
        assert 384 in result
        assert 1024 in result
        assert 3072 in result
    
    def test_full_dimension_unchanged(self):
        """Test that 3072-dim embedding is kept as-is"""
        embedding_3072 = np.random.randn(3072).tolist()
        
        result = create_multi_dimensional_embeddings(embedding_3072)
        
        # 3072-dim should be identical
        assert result[3072] == embedding_3072
    
    def test_custom_dimensions(self):
        """Test with custom dimension list"""
        embedding_3072 = np.random.randn(3072).tolist()
        
        result = create_multi_dimensional_embeddings(
            embedding_3072,
            dimensions=[256, 1024]
        )
        
        assert len(result) == 2
        assert 256 in result
        assert 1024 in result
    
    def test_all_normalized(self):
        """Test that all truncated embeddings are normalized"""
        embedding_3072 = np.random.randn(3072).tolist()
        
        result = create_multi_dimensional_embeddings(embedding_3072)
        
        for dim in [256, 384, 1024]:
            norm = np.linalg.norm(result[dim])
            assert abs(norm - 1.0) < 1e-6


class TestValidateMRLProperty:
    """Tests for validate_mrl_property function"""
    
    def test_perfect_match(self):
        """Test validation with perfectly matching embeddings"""
        # Create a 3072-dim embedding
        embedding_3072 = np.random.randn(3072)
        embedding_3072 = embedding_3072 / np.linalg.norm(embedding_3072)
        
        # Truncate it ourselves to create "native" embedding
        embedding_256 = embedding_3072[:256]
        embedding_256 = embedding_256 / np.linalg.norm(embedding_256)
        
        result = validate_mrl_property(
            embedding_3072.tolist(),
            embedding_256.tolist(),
            256
        )
        
        assert result is True
    
    def test_close_match(self):
        """Test validation with very similar embeddings"""
        embedding_3072 = np.random.randn(3072)
        embedding_3072 = embedding_3072 / np.linalg.norm(embedding_3072)
        
        # Create slightly different "native" embedding
        embedding_256 = embedding_3072[:256] + np.random.randn(256) * 0.001
        embedding_256 = embedding_256 / np.linalg.norm(embedding_256)
        
        result = validate_mrl_property(
            embedding_3072.tolist(),
            embedding_256.tolist(),
            256,
            tolerance=0.01
        )
        
        assert result is True
    
    def test_no_match(self):
        """Test validation with completely different embeddings"""
        embedding_3072 = np.random.randn(3072).tolist()
        embedding_256 = np.random.randn(256).tolist()
        
        result = validate_mrl_property(
            embedding_3072,
            embedding_256,
            256
        )
        
        assert result is False
    
    def test_custom_tolerance(self):
        """Test validation with custom tolerance"""
        # Create a base embedding
        embedding_3072 = np.random.randn(3072)
        embedding_3072 = embedding_3072 / np.linalg.norm(embedding_3072)
        
        # Create a slightly rotated version by mixing with a small orthogonal component
        # This creates a controlled angular difference
        orthogonal = np.random.randn(256)
        orthogonal = orthogonal - np.dot(orthogonal, embedding_3072[:256]) * embedding_3072[:256]
        orthogonal = orthogonal / np.linalg.norm(orthogonal)
        
        # Mix: 99.5% original + 0.5% orthogonal (creates very small angle)
        embedding_256_close = 0.995 * embedding_3072[:256] + 0.005 * orthogonal
        embedding_256_close = embedding_256_close / np.linalg.norm(embedding_256_close)
        
        # Mix: 90% original + 10% orthogonal (creates larger angle)
        embedding_256_far = 0.90 * embedding_3072[:256] + 0.10 * orthogonal
        embedding_256_far = embedding_256_far / np.linalg.norm(embedding_256_far)
        
        # Close embedding should pass with moderate tolerance
        result_close = validate_mrl_property(
            embedding_3072.tolist(),
            embedding_256_close.tolist(),
            256,
            tolerance=0.01
        )
        assert result_close is True
        
        # Far embedding should fail with strict tolerance but pass with loose
        result_far_strict = validate_mrl_property(
            embedding_3072.tolist(),
            embedding_256_far.tolist(),
            256,
            tolerance=0.01
        )
        assert result_far_strict is False
        
        result_far_loose = validate_mrl_property(
            embedding_3072.tolist(),
            embedding_256_far.tolist(),
            256,
            tolerance=0.1
        )
        assert result_far_loose is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
