"""
Test script to verify chatbot functionality
Run this after starting the Django server
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_chatbot():
    print("🧪 Testing Construction Cost Chatbot\n")
    print("=" * 60)

    test_queries = [
        "Hello",
        "Help",
        "Which cities are available?",
        "Average cost in Mumbai",
        "What factors affect cost?",
        "Predict cost for 2000 sqft in Mumbai",
        "Residential building statistics"
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Testing query: '{query}'")
        print("-" * 60)

        try:
            response = requests.get(
                f"{BASE_URL}/chatbot/",
                params={"message": query},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Status: Success")
                print(f"📝 Response preview: {data['response'][:150]}...")
            else:
                print(f"❌ Status: Failed (HTTP {response.status_code})")

        except requests.exceptions.ConnectionError:
            print("❌ Error: Cannot connect to server")
            print("💡 Make sure Django server is running: python manage.py runserver")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")

    print("\n" + "=" * 60)
    print("✅ Chatbot testing complete!")
    print("\n📌 To test manually:")
    print(f"   1. Start server: python manage.py runserver")
    print(f"   2. Open browser: {BASE_URL}/chat/")
    print(f"   3. Try the queries above")

if __name__ == "__main__":
    test_chatbot()
