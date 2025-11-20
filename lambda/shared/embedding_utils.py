"""
Shared utilities for embedding truncation and normalization (MRL)
"""

import numpy as np
from typing import List


def truncate_and_normalize(embedding: List[float], target_dim: int) -> List[float]:
    """
    Truncate an embedding to target dimension and renormalize using L2 norm.
    
    This implements the Matryoshka Relational Learning property where the first
    N dimensions of a larger embedding contain meaningful semantic information.
    
    Args:
        embedding: Full embedding vector (e.g., 3072 dimensions)
        target_dim: Target dimension to truncate to (e.g., 256, 384, 1024)
    
    Returns:
        Truncated and renormalized embedding vector
    """
    if len(embedding) < target_dim:
        raise ValueError(
            f"Embedding length ({len(embedding)}) is less than target dimension ({target_dim})"
        )
    
    # Truncate to first N dimensions
    truncated = np.array(embedding[:target_dim])
    
    # Renormalize using L2 norm
    norm = np.linalg.norm(truncated)
    if norm == 0:
        raise ValueError("Cannot normalize zero vector")
    
    normalized = truncated / norm
    
    return normalized.tolist()


def create_multi_dimensional_embeddings(
    embedding_3072: List[float],
    dimensions: List[int] = [256, 384, 1024, 3072]
) -> dict:
    """
    Create multiple dimension variants from a single 3072-dim embedding.
    
    This demonstrates the MRL benefit: one model invocation generates
    multiple usable embeddings at different granularities.
    
    Args:
        embedding_3072: Full 3072-dimensional embedding
        dimensions: List of target dimensions to generate
    
    Returns:
        Dictionary mapping dimension -> truncated embedding
    """
    result = {}
    
    for dim in dimensions:
        if dim == 3072:
            # Keep full embedding as-is
            result[dim] = embedding_3072
        else:
            # Truncate and renormalize
            result[dim] = truncate_and_normalize(embedding_3072, dim)
    
    return result


def validate_mrl_property(
    embedding_3072: List[float],
    embedding_native: List[float],
    target_dim: int,
    tolerance: float = 0.01
) -> bool:
    """
    Validate that the MRL nesting property holds.
    
    Checks if the first N dimensions of a 3072-dim embedding (after renormalization)
    match a native N-dim embedding from the model.
    
    Args:
        embedding_3072: Full 3072-dimensional embedding
        embedding_native: Native embedding at target dimension
        target_dim: Dimension to compare
        tolerance: Acceptable difference threshold
    
    Returns:
        True if embeddings match within tolerance
    """
    truncated = truncate_and_normalize(embedding_3072, target_dim)
    
    # Calculate cosine similarity
    truncated_arr = np.array(truncated)
    native_arr = np.array(embedding_native)
    
    cosine_sim = np.dot(truncated_arr, native_arr) / (
        np.linalg.norm(truncated_arr) * np.linalg.norm(native_arr)
    )
    
    # Should be very close to 1.0
    # Convert to Python bool to avoid np.bool_ type issues
    return bool(abs(1.0 - cosine_sim) < tolerance)
