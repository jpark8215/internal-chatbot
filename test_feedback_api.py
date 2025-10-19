#!/usr/bin/env python3
"""
Test the feedback API endpoint to debug the 422 error.
"""

import requests
import json

def test_feedback_api():
    """Test the feedback API with different limits."""
    base_url = "http://localhost:8000"
    
    test_limits = [10, 25, 50, 75, 100, 150, 200]
    
    print("🔍 Testing feedback API endpoint...")
    print("=" * 50)
    
    for limit in test_limits:
        try:
            url = f"{base_url}/api/feedback/recent?limit={limit}"
            print(f"\nTesting limit={limit}: {url}")
            
            response = requests.get(url)
            print(f"Status: {response.status_code} {response.reason}")
            
            if response.status_code == 200:
                data = response.json()
                feedback_count = len(data.get('feedback', []))
                print(f"✅ Success: Got {feedback_count} feedback entries")
            else:
                print(f"❌ Error: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"Error details: {json.dumps(error_data, indent=2)}")
                except:
                    print(f"Error text: {response.text}")
                    
        except Exception as e:
            print(f"❌ Exception: {e}")
    
    print(f"\n" + "=" * 50)
    print("💡 If you see 422 errors, the application may need to be restarted")
    print("💡 to pick up the API limit changes.")

if __name__ == "__main__":
    test_feedback_api()