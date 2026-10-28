import os
import json
import time
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

CACHE_FILE = 'docs_cache.json'
QUEUE_FILE = 'save_queue.json'
GOOGLE_APPS_SCRIPT_URL = 'https://script.google.com/macros/s/AKfycbz3b2ncvEKcdHMvsdwukIR9EATgIPZG0pk4ry-NpyIHFYWxZAPqJY1Va9b6vuVuoSf5jw/exec'

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def ensure_cache():
    """Ensures docs_cache.json exists and contains valid categories data."""
    cache_data = load_cache()
    
    # Check if cache is empty or missing the 'categories' structure
    has_categories = (
        isinstance(cache_data, dict) and 
        isinstance(cache_data.get('data'), dict) and 
        bool(cache_data['data'].get('categories'))
    )

    if not has_categories:
        print("Cache missing or invalid. Fetching full dataset from Google Sheets...")
        try:
            resp = requests.get(f"{GOOGLE_APPS_SCRIPT_URL}?full=true", timeout=30)
            if resp.status_code == 200:
                cache_data = resp.json()
                with open(CACHE_FILE, 'w') as f:
                    json.dump(cache_data, f, indent=2)
                print("docs_cache.json successfully populated with master dataset!")
        except Exception as e:
            print(f"Error fetching initial cache: {e}")
            
    return cache_data

@app.route('/', methods=['GET'])
def get_docs():
    """Smart proxy: serves filtered responses from local cache based on query params."""
    try:
        cache_data = ensure_cache()
        
        category = request.args.get('category', '').strip()
        section = request.args.get('section', '').strip()
        lesson = request.args.get('lesson', '').strip()
        is_toc = request.args.get('toc') == 'true'

        if not category or category == 'Landing Page':
            return jsonify({'data': []}), 200

        categories_dict = cache_data.get('data', {}).get('categories', {})
        
        matched_cat_key = next((k for k in categories_dict if k.strip().lower() == category.lower()), None)
        
        if not matched_cat_key:
            return jsonify({'error': f"Category matching '{category}' was not found."}), 404

        cat_data = categories_dict[matched_cat_key]

        # 1. Handle TOC Request
        if is_toc:
            toc_list = cat_data.get('toc', [])
            return jsonify({'data': toc_list}), 200

        # 2. Handle Page Elements Request
        pages_dict = cat_data.get('pages', {})
        
        matched_sec_key = next((k for k in pages_dict if k.strip().lower() == section.lower()), None)
        if not matched_sec_key:
            return jsonify({'error': f"Section matching '{section}' was not found."}), 404
            
        sec_data = pages_dict[matched_sec_key]
        
        matched_les_key = next((k for k in sec_data if k.strip().lower() == lesson.lower()), None)
        if not matched_les_key:
            return jsonify({'error': f"Lesson matching '{lesson}' was not found."}), 404
            
        page_elements = sec_data[matched_les_key]
        return jsonify({'data': page_elements}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/save', methods=['POST'])
def save_doc():
    """Updates local cache immediately and queues background sync to Sheets."""
    try:
        payload = request.get_json(force=True)
        if not payload:
            return jsonify({'status': 'error', 'message': 'No JSON payload provided'}), 400

        cache_data = load_cache()
        if 'data' in cache_data and 'categories' in cache_data['data']:
            cat = payload.get('category', '')
            sec = payload.get('section', '')
            les = payload.get('lesson', '')
            
            if cat and sec and les:
                if cat not in cache_data['data']['categories']:
                    cache_data['data']['categories'][cat] = {'toc': [], 'pages': {}}
                if sec not in cache_data['data']['categories'][cat]['pages']:
                    cache_data['data']['categories'][cat]['pages'][sec] = {}
                
                cache_data['data']['categories'][cat]['pages'][sec][les] = payload.get('pageElements', [])
                
                with open(CACHE_FILE, 'w') as f:
                    json.dump(cache_data, f, indent=2)

        queue = []
        if os.path.exists(QUEUE_FILE):
            try:
                with open(QUEUE_FILE, 'r') as f:
                    queue = json.load(f)
            except Exception:
                queue = []

        queue.append({
            'id': int(time.time() * 1000),
            'status': 'pending',
            'payload': payload
        })

        with open(QUEUE_FILE, 'w') as f:
            json.dump(queue, f, indent=2)

        return jsonify({'status': 'success', 'message': 'Saved locally and queued for sync'}), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
