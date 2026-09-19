import json
import time

import httpx

BASE = "http://localhost:8000/api/v1"

r = httpx.post(f"{BASE}/tasks", json={"name": "ping", "payload": {"source": "acceptance"}}).json()
print("created:", r)

status = None
for _ in range(20):
    s = httpx.get(f"{BASE}/tasks/{r['id']}").json()
    if s["status"] != "queued":
        status = s
        break
    time.sleep(0.5)

print("status:", json.dumps(status, ensure_ascii=False))

# error path: unknown task
bad = httpx.post(f"{BASE}/tasks", json={"name": "no_such_task"}).json()
for _ in range(20):
    s = httpx.get(f"{BASE}/tasks/{bad['id']}").json()
    if s["status"] != "queued":
        break
    time.sleep(0.5)
print("unknown task ->", s["status"], "|", s.get("error"))
