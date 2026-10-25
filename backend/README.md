# MovieDude FastAPI backend

This backend wraps the original MovieDude content-based recommendation engine and adds a simple API for the React frontend.

## Run

```bash
python -m venv venv
# Windows PowerShell: .\\venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Swagger docs: `http://127.0.0.1:8000/docs`

Poster thumbnails are fetched best-effort from Wikipedia's public APIs and cached in memory.
