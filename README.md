# CloudStorageBackend

This folder contains the FastAPI backend for the Cloud Data Storage project.

Quick start (local):

1. Create and activate a Python virtualenv
```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

2. Run the server
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

3. Environment variables
- `SECRET_KEY` — secret for JWT
- `DATABASE_URL` — optional, default uses sqlite `sqlite:///./cloud.db`
- `CLOUDINARY_URL` — optional, e.g. `cloudinary://API_KEY:API_SECRET@CLOUD_NAME`

Local compose (Postgres):
```bash
docker-compose up --build
# then access backend at http://127.0.0.1:8001
```

Deployment notes:
- Render: create a Web Service, set build command and start command: `gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT`
- Vercel for frontend; set `REACT_APP_API_URL` to the backend public URL.
