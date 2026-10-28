# Team 5103 documentation proxy

This Raspberry Pi service forwards `/api` reads and writes to the Apps Script backend. It does not store Firebase tokens, maintain a second copy of the documentation, or report a save before Google accepts it.

Set `APPS_SCRIPT_URL` to the deployed Apps Script URL ending in `/exec`, and set `ALLOWED_ORIGINS` to the frontend origin. Then install and run:

```sh
pip install -r requirements.txt
gunicorn --bind 127.0.0.1:3000 --workers 1 --threads 4 server:app
```

Keep port 3000 private behind the existing Cloudflare Tunnel. Point `https://api.team5103.com/api` at `http://127.0.0.1:3000/api`.

The old JSON cache and background queue were removed because they could expose unapproved edits and lose concurrent saves.
