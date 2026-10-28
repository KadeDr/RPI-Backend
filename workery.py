import os
import json
import time
import requests

QUEUE_FILE = 'save_queue.json'
CACHE_FILE = 'docs_cache.json'
GOOGLE_APPS_SCRIPT_URL = 'https://script.google.com/macros/s/AKfycbz3b2ncvEKcdHMvsdwukIR9EATgIPZG0pk4ry-NpyIHFYWxZAPqJY1Va9b6vuVuoSf5jw/exec'

PERIODIC_PULL_INTERVAL = 300  # 5 minutes

def process_queue():
    if not os.path.exists(QUEUE_FILE):
        return False

    try:
        with open(QUEUE_FILE, 'r') as f:
            queue = json.load(f)
    except Exception:
        return False

    pending = [item for item in queue if item['status'] == 'pending']
    if not pending:
        return False

    item = pending[0]
    print(f"Syncing item {item['id']} to Google Sheets...")

    try:
        response = requests.post(
            GOOGLE_APPS_SCRIPT_URL,
            headers={'Content-Type': 'text/plain;charset=utf-8'},
            data=json.dumps(item['payload']),
            timeout=15
        )
        result = response.json()
        if result.get('status') == 'success':
            print(f"Successfully synced item {item['id']}!")
            queue = [q for q in queue if q['id'] != item['id']]
            with open(QUEUE_FILE, 'w') as f:
                json.dump(queue, f, indent=2)
        else:
            print(f"Apps Script error: {result.get('message')}")
    except Exception as err:
        print(f"Worker sync error: {err}")

    return True

def pull_full_cache():
    # Only pull if no pending local edits exist
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE, 'r') as f:
                if any(i.get('status') == 'pending' for i in json.load(f)):
                    return
        except Exception:
            pass

    print("Pulling full master dataset from Google Sheets...")
    try:
        resp = requests.get(f"{GOOGLE_APPS_SCRIPT_URL}?full=true", timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'success':
                with open(CACHE_FILE, 'w') as f:
                    json.dump(data, f, indent=2)
                print("docs_cache.json successfully updated from Sheets!")
    except Exception as e:
        print(f"Full pull error: {e}")

if __name__ == '__main__':
    print("Python sync worker started...")
    if not os.path.exists(CACHE_FILE):
        pull_full_cache()

    last_pull = time.time()
    while True:
        has_pending = process_queue()

        if not has_pending and (time.time() - last_pull > PERIODIC_PULL_INTERVAL):
            pull_full_cache()
            last_pull = time.time()

        time.sleep(5)
