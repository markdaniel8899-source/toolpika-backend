FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/pytest.ini ./pytest.ini
COPY backend/scripts ./scripts
COPY backend/tests ./tests
# Self-contained: the canonical template is versioned inside backend/markdown.
COPY backend/markdown/UNIVERSAL_TOOL_TEMPLATE.md /app/markdown/UNIVERSAL_TOOL_TEMPLATE.md

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
