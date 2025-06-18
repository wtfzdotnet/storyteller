"""
Demo script showcasing the Epic Management API functionality.

This script demonstrates all the API endpoints with real examples.
"""

import json

import requests


def demo_epic_api(base_url="http://localhost:8000"):
    """Demonstrate the Epic API functionality."""

    print("🚀 Epic Management API Demo")
    print("=" * 50)

    # 1. Health Check
    print("\n1. Health Check")
    print("-" * 20)
    try:
        response = requests.get(f"{base_url}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    # 2. Create Epic
    print("\n2. Create Epic")
    print("-" * 20)
    epic_data = {
        "title": "User Authentication System",
        "description": "Implement comprehensive user authentication and authorization system with OAuth2, JWT tokens, "
        "and role-based access control",
        "business_value": "Enables secure user access, protects sensitive data, and provides foundation for "
        "personalized features",
        "acceptance_criteria": [
            "Users can register with email/password",
            "Users can login with OAuth providers (Google, GitHub)",
            "JWT tokens are issued and validated properly",
            "Role-based permissions control access to features",
            "Password reset functionality works",
            "Account verification via email works",
        ],
        "target_repositories": ["backend-api", "frontend-app"],
        "estimated_duration_weeks": 6,
    }

    response = requests.post(f"{base_url}/epics", json=epic_data)
    if response.status_code == 201:
        epic = response.json()
        epic_id = epic["id"]
        print("✅ Epic created successfully!")
        print(f"Epic ID: {epic_id}")
        print(f"Title: {epic['title']}")
        print(f"Status: {epic['status']}")
        print(f"Business Value: {epic['business_value']}")
    else:
        print(f"❌ Failed to create epic: {response.status_code}")
        print(response.text)
        return

    # 3. Get Epic
    print("\n3. Get Epic by ID")
    print("-" * 20)
    response = requests.get(f"{base_url}/epics/{epic_id}")
    if response.status_code == 200:
        epic = response.json()
        print("✅ Epic retrieved successfully!")
        print(f"Title: {epic['title']}")
        print(f"Acceptance Criteria ({len(epic['acceptance_criteria'])}):")
        for i, criteria in enumerate(epic["acceptance_criteria"], 1):
            print(f"  {i}. {criteria}")
    else:
        print(f"❌ Failed to get epic: {response.status_code}")

    # 4. Update Epic
    print("\n4. Update Epic")
    print("-" * 20)
    update_data = {
        "status": "in_progress",
        "title": "User Authentication & Authorization System",
    }

    response = requests.put(f"{base_url}/epics/{epic_id}", json=update_data)
    if response.status_code == 200:
        updated_epic = response.json()
        print("✅ Epic updated successfully!")
        print(f"New Title: {updated_epic['title']}")
        print(f"New Status: {updated_epic['status']}")
    else:
        print(f"❌ Failed to update epic: {response.status_code}")

    # 5. Create another Epic for listing demo
    print("\n5. Create Second Epic")
    print("-" * 20)
    epic_data_2 = {
        "title": "Recipe Search & Discovery",
        "description": "Advanced recipe search with filters, recommendations, and discovery features",
        "business_value": "Improves user experience and helps users find recipes faster",
        "acceptance_criteria": [
            "Full-text search across recipes",
            "Filter by dietary restrictions",
            "Ingredient-based search",
            "AI-powered recommendations",
        ],
        "target_repositories": ["backend-api", "frontend-app", "ai-service"],
        "estimated_duration_weeks": 4,
    }

    response = requests.post(f"{base_url}/epics", json=epic_data_2)
    if response.status_code == 201:
        epic_2 = response.json()
        epic_2_id = epic_2["id"]
        print("✅ Second epic created!")
        print(f"Epic ID: {epic_2_id}")
        print(f"Title: {epic_2['title']}")
    else:
        print(f"❌ Failed to create second epic: {response.status_code}")
        return

    # 6. List Epics
    print("\n6. List All Epics")
    print("-" * 20)
    response = requests.get(f"{base_url}/epics")
    if response.status_code == 200:
        epics_data = response.json()
        print(f"✅ Found {epics_data['total']} epics:")
        for epic in epics_data["epics"]:
            print(f"  • {epic['title']} (Status: {epic['status']})")
    else:
        print(f"❌ Failed to list epics: {response.status_code}")

    # 7. Filter Epics by Status
    print("\n7. Filter Epics by Status")
    print("-" * 20)
    response = requests.get(f"{base_url}/epics?status=in_progress")
    if response.status_code == 200:
        epics_data = response.json()
        print(f"✅ Found {epics_data['total']} in-progress epics:")
        for epic in epics_data["epics"]:
            print(f"  • {epic['title']}")
    else:
        print(f"❌ Failed to filter epics: {response.status_code}")

    # 8. Get Epic Hierarchy
    print("\n8. Get Epic Hierarchy")
    print("-" * 20)
    response = requests.get(f"{base_url}/epics/{epic_id}/hierarchy")
    if response.status_code == 200:
        hierarchy = response.json()
        print("✅ Epic hierarchy retrieved!")
        print(f"Epic: {hierarchy['epic']['title']}")
        print(f"User Stories: {len(hierarchy['user_stories'])}")
        print(f"Progress: {hierarchy['progress']['percentage']}% complete")
    else:
        print(f"❌ Failed to get hierarchy: {response.status_code}")

    # 9. Delete Epic
    print("\n9. Delete Epic")
    print("-" * 20)
    print("⚠️  Demonstrating cascade delete...")
    response = requests.delete(f"{base_url}/epics/{epic_2_id}")
    if response.status_code == 200:
        result = response.json()
        print(f"✅ {result['message']}")
    else:
        print(f"❌ Failed to delete epic: {response.status_code}")

    # 10. Verify Deletion
    print("\n10. Verify Deletion")
    print("-" * 20)
    response = requests.get(f"{base_url}/epics/{epic_2_id}")
    if response.status_code == 404:
        print("✅ Epic successfully deleted (404 as expected)")
    else:
        print(f"❌ Epic still exists: {response.status_code}")

    print("\n🎉 Demo completed!")
    print(f"✅ Remaining epic ID for further testing: {epic_id}")


if __name__ == "__main__":
    print("Epic Management API Demo")
    print("\nTo run this demo:")
    print("1. Start the API server: python main.py api start")
    print("2. Run this script: python demo_api.py")
    print("\nTesting against localhost:8000...")

    try:
        demo_epic_api()
    except requests.ConnectionError:
        print("\n❌ Could not connect to API server.")
        print("Please make sure the API server is running:")
        print("   python main.py api start")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
