# A Dockerfile is a recipe for a "container image": a mini computer with
# exactly the right Python version and libraries, identical everywhere.

# 1. Start from an official, small image that already has Python installed.
FROM python:3.11-slim

# 2. Don't write .pyc files; print logs immediately instead of buffering them.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 3. All following commands run inside /app.
WORKDIR /app

# 4. Install libraries first. Docker caches this layer, so rebuilding after a
#    code change is fast as long as requirements.txt didn't change.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the project code.
COPY . .

# 6. Default command: run the pipeline. docker-compose overrides it for the dashboard.
CMD ["python", "-m", "pipeline.run_pipeline"]
