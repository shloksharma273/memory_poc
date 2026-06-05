import json
import time
import requests

BASE_URL = "http://localhost:8000"

memories = [
    {
        "user_id": "alice_dev",
        "message": "I am working on the new authentication module called AuthShield for the Helios project.",
    },
    {
        "user_id": "alice_dev",
        "message": "Bob is the product manager for Helios, and he set the release deadline to October 15th.",
    },
    {
        "user_id": "alice_dev",
        "message": "We decided to use Redis for session caching because speed is a critical requirement.",
    },
    {
        "user_id": "alice_dev",
        "message": "I ran into a severe bug in the Redis client today, ticket ID is AUTH-9921.",
    },
]


def print_json(title, data):
    print(f"\n=== {title} ===")
    print(json.dumps(data, indent=2))


def test_complex_scenario():
    # 1. Ingest complex memories sequentially
    print("Ingesting complex narrative...")
    for item in memories:
        print(f"\nAdding memory: '{item['message']}'")
        res = requests.post(f"{BASE_URL}/memory/add", json=item)
        print(f"-> Result: {res.json()}")
        time.sleep(0.5)  # small pause to separate timestamps

    print("\nWaiting 15 seconds for background worker to process all memories...")
    time.sleep(15)

    # 2. View Alice's Knowledge Graph
    print("\nFetching Knowledge Graph for Alice...")
    graph_res = requests.get(f"{BASE_URL}/graph/alice_dev")
    print_json("Alice's Graph", graph_res.json())

    # 3. Test Hybrid Retrieval
    queries = [
        "What database or cache tool are we using for sessions?",  # Semantic + Graph focus
        "Show me information about the ticket AUTH-9921",  # BM25 focus
        "Who is the product manager for project Helios?",  # Graph traversal focus
    ]

    for query in queries:
        print(f"\n\n🔍 Running Hybrid Search for: '{query}'")
        search_res = requests.post(
            f"{BASE_URL}/memory/search",
            json={"query": query, "user_id": "alice_dev"},
        )
        print_json(f"Results for '{query}'", search_res.json())


if __name__ == "__main__":
    test_complex_scenario()
