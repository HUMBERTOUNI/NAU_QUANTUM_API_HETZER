#!/bin/bash
# Sentinel Quantum Edge v5.3 - Hetzner/Coolify
exec uvicorn api:app \
    --host 0.0.0.0 \
    --port 9000 \
    --workers 8 \
    --timeout-keep-alive 300 \
    --timeout-graceful-shutdown 300
