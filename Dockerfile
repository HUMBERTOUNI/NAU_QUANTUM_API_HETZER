FROM python:3.9-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar los requerimientos de Python PRIMERO
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de tu código
COPY . .

# Exponer el puerto
EXPOSE 8000

# El comando a prueba de fallos para arrancar la API
CMD ["python", "api.py"]
