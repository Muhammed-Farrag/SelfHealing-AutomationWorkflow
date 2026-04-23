FROM python:3.10-slim

WORKDIR /app

# Install git for rollback support
RUN apt-get update && apt-get install -y --no-install-recommends git curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" python-multipart sse-starlette httpx groq

# Copy source code
COPY . .

# Create data directories if they don't exist
RUN mkdir -p data results models

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
