import json
import time
import requests

BASE_URL = "http://localhost:8000"


def print_json(title, data):
    print(f"\n=== {title} ===")
    print(json.dumps(data, indent=2))


def test_memory_poc():
    # 1. Add Memory
    add_payload = {
        "user_id": "demo_user",
        "message": "I am learning ArangoDB and building an Agentic Memory system.",
    }
    print(f"Adding memory: {add_payload['message']}")
    try:
        response = requests.post(f"{BASE_URL}/memory/add", json=add_payload)
        response.raise_for_status()
        print_json("Add Memory Response", response.json())
        print("Waiting 7 seconds for asynchronous processing to complete...")
        time.sleep(7)
    except Exception as e:
        print(f"Error adding memory: {e}")
        return

    # 2. Get Graph
    print("Fetching User Graph...")
    try:
        response = requests.get(f"{BASE_URL}/graph/demo_user")
        response.raise_for_status()
        print_json("User Graph Response", response.json())
    except Exception as e:
        print(f"Error fetching graph: {e}")

    # 3. Search Memory
    search_payload = {"query": "What database am I learning?", "user_id": "demo_user"}
    print(f"Searching memory for: '{search_payload['query']}'")
    try:
        response = requests.post(f"{BASE_URL}/memory/search", json=search_payload)
        response.raise_for_status()
        print_json("Search Results", response.json())
    except Exception as e:
        print(f"Error searching memory: {e}")


if __name__ == "__main__":
    test_memory_poc()
