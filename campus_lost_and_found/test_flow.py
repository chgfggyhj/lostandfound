from fastapi.testclient import TestClient
from main import app
import time

client = TestClient(app)

def run_demo():
    print(">>> 1. Creating Users...")
    user_a = client.post("/users/", params={"name": "Alice", "contact": "123"}).json()
    user_b = client.post("/users/", params={"name": "Bob", "contact": "456"}).json()
    print(f"User A: {user_a}")
    print(f"User B: {user_b}")

    print("\n>>> 2. Creating Items...")
    # Alice 丢了
    token = "wallet_xyz" # unique token to identify logic
    lost_item = client.post("/items/", json={
        "title": "黑色皮革钱包",
        "description": "里面有身份证和几张银行卡，颜色是黑色的。",
        "type": "LOST",
        "location": "Library",
        "owner_id": user_a['id']
    }).json()
    print(f"Lost Item: {lost_item['id']} - {lost_item['title']}")

    # Bob 捡到了
    found_item = client.post("/items/", json={
        "title": "黑色钱包",
        "description": "在图书馆二楼捡到的，黑色。",
        "type": "FOUND",
        "location": "Library 2F",
        "owner_id": user_b['id']
    }).json()
    print(f"Found Item: {found_item['id']} - {found_item['title']}")

    print("\n>>> 3. Triggering Negotiation...")
    trigger_resp = client.post(f"/negotiation/trigger/{lost_item['id']}").json()
    print(f"Trigger Response: {trigger_resp}")
    
    if "session_id" not in trigger_resp:
        print("Failed to start negotiation.")
        return

    session_id = trigger_resp["session_id"]
    
    print("\n>>> 4. Stepping through Negotiation Loop...")
    for i in range(10):
        step_resp = client.post(f"/negotiation/step/{session_id}").json()
        status = step_resp.get("status")
        logs = step_resp.get("chat_log", [])
        last_msg = logs[-1] if logs else {}
        print(f"Step {i+1} [{status}]: {last_msg.get('sender')} says '{last_msg.get('content')}' [Action: {last_msg.get('action_type')}]")
        
        if status == "SUCCESS":
            print("\n>>> NEGOTIATION SUCCESSFUL! <<<")
            break
        
    print("\n>>> 5. Final Logs:")
    final_logs = client.get(f"/negotiation/{session_id}/logs").json()
    print(final_logs)

if __name__ == "__main__":
    run_demo()
