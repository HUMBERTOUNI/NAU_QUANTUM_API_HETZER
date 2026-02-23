FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api.py .
COPY nau_quantum_engine.py .
COPY start.sh .
RUN chmod +x start.sh

COPY static/ ./static/

EXPOSE 9000

ENTRYPOINT ["/app/start.sh"]
