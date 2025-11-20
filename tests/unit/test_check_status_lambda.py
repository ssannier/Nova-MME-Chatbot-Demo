"""
Unit tests for Lambda 2: Check Job Status
"""

import pytest
import sys
import os
from unittest.mock import patch

# Add lambda path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../lambda/embedder/check_status'))

import index as check_status


class TestHandler:
    """Tests for check_status handler function"""
    
    @patch('index.bedrock_runtime')
    def test_completed_status(self, mock_bedrock):
        """Test handling of completed job"""
        mock_bedrock.get_async_invoke.return_value = {
            'status': 'Completed',
            'submitTime': '2024-01-15T10:30:00',
            'lastModifiedTime': '2024-01-15T10:35:00'
        }
        
        event = {
            'invocationArn': 'arn:aws:bedrock:us-east-1:123456789012:async-invoke/test123',
            'metadata': {'test': 'data'},
            'outputS3Uri': 's3://output-bucket/job123'
        }
        
        result = check_status.handler(event, None)
        
        assert result['status'] == 'COMPLETED'
        assert result['bedrockStatus'] == 'Completed'
        assert result['metadata'] == {'test': 'data'}  # Passed through
        assert 'statusDetails' in result
    
    @patch('index.bedrock_runtime')
    def test_in_progress_status(self, mock_bedrock):
        """Test handling of in-progress job"""
        mock_bedrock.get_async_invoke.return_value = {
            'status': 'InProgress',
            'submitTime': '2024-01-15T10:30:00',
            'lastModifiedTime': '2024-01-15T10:32:00'
        }
        
        event = {
            'invocationArn': 'arn:aws:bedrock:us-east-1:123456789012:async-invoke/test123',
            'metadata': {'test': 'data'}
        }
        
        result = check_status.handler(event, None)
        
        assert result['status'] == 'IN_PROGRESS'
        assert result['bedrockStatus'] == 'InProgress'
    
    @patch('index.bedrock_runtime')
    def test_failed_status(self, mock_bedrock):
        """Test handling of failed job"""
        mock_bedrock.get_async_invoke.return_value = {
            'status': 'Failed',
            'submitTime': '2024-01-15T10:30:00',
            'lastModifiedTime': '2024-01-15T10:31:00',
            'failureMessage': 'Invalid input format'
        }
        
        event = {
            'invocationArn': 'arn:aws:bedrock:us-east-1:123456789012:async-invoke/test123'
        }
        
        result = check_status.handler(event, None)
        
        assert result['status'] == 'FAILED'
        assert result['bedrockStatus'] == 'Failed'
        assert result['statusDetails']['failureMessage'] == 'Invalid input format'
    
    @patch('index.bedrock_runtime')
    def test_expired_status(self, mock_bedrock):
        """Test handling of expired job"""
        mock_bedrock.get_async_invoke.return_value = {
            'status': 'Expired',
            'submitTime': '2024-01-15T10:30:00',
            'lastModifiedTime': '2024-01-15T12:30:00'
        }
        
        event = {
            'invocationArn': 'arn:aws:bedrock:us-east-1:123456789012:async-invoke/test123'
        }
        
        result = check_status.handler(event, None)
        
        assert result['status'] == 'FAILED'
        assert result['bedrockStatus'] == 'Expired'
    
    @patch('index.bedrock_runtime')
    def test_error_handling(self, mock_bedrock):
        """Test error handling"""
        mock_bedrock.get_async_invoke.side_effect = Exception("API error")
        
        event = {
            'invocationArn': 'arn:aws:bedrock:us-east-1:123456789012:async-invoke/test123',
            'metadata': {'test': 'data'}
        }
        
        result = check_status.handler(event, None)
        
        assert result['status'] == 'FAILED'
        assert 'error' in result
        assert result['metadata'] == {'test': 'data'}  # Still passed through
    
    @patch('index.bedrock_runtime')
    def test_passes_through_all_data(self, mock_bedrock):
        """Test that all event data is passed through"""
        mock_bedrock.get_async_invoke.return_value = {
            'status': 'Completed',
            'submitTime': '2024-01-15T10:30:00',
            'lastModifiedTime': '2024-01-15T10:35:00'
        }
        
        event = {
            'invocationArn': 'arn:aws:bedrock:us-east-1:123456789012:async-invoke/test123',
            'metadata': {'fileName': 'test.jpg', 'fileSize': 1024},
            'outputS3Uri': 's3://output-bucket/job123',
            'customField': 'customValue'
        }
        
        result = check_status.handler(event, None)
        
        # All original fields should be present
        assert result['invocationArn'] == event['invocationArn']
        assert result['metadata'] == event['metadata']
        assert result['outputS3Uri'] == event['outputS3Uri']
        assert result['customField'] == event['customField']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
