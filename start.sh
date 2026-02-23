#!/bin/bash
# Sentinel Quantum Edge v5.0 - Hetzner
exec uvicorn api:app --host 0.0.0.0 --port 9000 --workers 4 --timeout-keep-alive 120
