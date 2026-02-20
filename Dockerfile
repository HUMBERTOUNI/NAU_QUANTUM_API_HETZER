FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api.py .
COPY nau_quantum_engine.py .
COPY start.sh .
RUN chmod +x start.sh

COPY static/ ./static/

EXPOSE 8080

ENTRYPOINT ["/app/start.sh"]
