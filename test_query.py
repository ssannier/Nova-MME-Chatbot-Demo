#!/usr/bin/env python3
"""
Quick test script to query the chatbot API and see detailed errors
"""

import requests
import json
import sys

API_URL = "https://976iaxrejk.execute-api.us-east-1.amazonaws.com/prod/query"

def test_query(query_text, dimension=1024, hierarchical=False):
    """Send a test query to the API"""
    payload = {
        "query": query_text,
        "dimension": dimension,
        "hierarchical": hierarchical
    }
    
    print(f"\n🔍 Testing query: '{query_text}'")
    print(f"   Dimension: {dimension}, Hierarchical: {hierarchical}")
    print(f"   URL: {API_URL}")
    print("-" * 60)
    
    try:
        response = requests.post(API_URL, json=payload, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"\nResponse Body:")
        print(json.dumps(response.json(), indent=2))
        
        return response
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return None
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON response:")
        print(response.text)
        return response

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "What files do you have?"
    
    # Test with hierarchical disabled first (simpler)
    print("\n" + "="*60)
    print("TEST 1: Simple search (hierarchical=False)")
    print("="*60)
    test_query(query, dimension=1024, hierarchical=False)
    
    # Test with hierarchical enabled
    print("\n" + "="*60)
    print("TEST 2: Hierarchical search (hierarchical=True)")
    print("="*60)
    test_query(query, dimension=1024, hierarchical=True)
