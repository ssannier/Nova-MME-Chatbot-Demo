"""
Lambda 2: Check Job Status

Polls the async invocation status.
- Checks if job is complete, failed, or still in progress
- Returns status to Step Functions for decision making
"""

import json
import os
import boto3
from typing import Dict, Any

# Initialize client
bedrock_runtime = boto3.client('bedrock-runtime')


def handler(event, context):
    """
    Main handler for Check Job Status Lambda
    
    Args:
        event: Contains invocationArn from previous Lambda
        context: Lambda context
    
    Returns:
        Dict with status (COMPLETED, FAILED, or IN_PROGRESS) and event data
    """
    try:
        invocation_arn = event['invocationArn']
        
        print(f"Checking status for: {invocation_arn}")
        
        # Get async invocation status
        response = bedrock_runtime.get_async_invoke(
            invocationArn=invocation_arn
        )
        
        status = response['status']
        print(f"Job status: {status}")
        
        # Map Bedrock status to our workflow status
        if status == 'Completed':
            workflow_status = 'COMPLETED'
        elif status in ['Failed', 'Expired']:
            workflow_status = 'FAILED'
            print(f"Job failed with reason: {response.get('failureMessage', 'Unknown')}")
        else:
            # InProgress, Scheduled, etc.
            workflow_status = 'IN_PROGRESS'
        
        # Return updated event with status
        return {
            **event,  # Pass through all previous data
            'status': workflow_status,
            'bedrockStatus': status,
            'statusDetails': {
                'submitTime': response.get('submitTime', ''),
                'lastModifiedTime': response.get('lastModifiedTime', ''),
                'failureMessage': response.get('failureMessage', '')
            }
        }
        
    except Exception as e:
        print(f"Error checking job status: {str(e)}")
        return {
            **event,
            'status': 'FAILED',
            'error': str(e)
        }
