# InstaClone (minimal)
Development-only Instagram-style clone built with Flask and SQLite.

## Quickstart (local)
1. Create a virtualenv: `python3 -m venv venv && venv\Scripts\activate`
2. Install: `pip install -r requirements.txt`
3. Initialize DB: `make init`  (or `python3 -c "from app import init_db; init_db()"`)
4. Run: `make run`  (or `python3 app.py`)
5. Open http://127.0.0.1:5000 in your browser.
