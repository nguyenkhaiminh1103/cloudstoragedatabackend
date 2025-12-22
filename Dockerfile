FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default port inside container (can be overridden by environment)
ENV PORT=8001

# Bind to the container PORT environment variable (use shell so $PORT is expanded at runtime)
CMD ["sh", "-c", "gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT"]
