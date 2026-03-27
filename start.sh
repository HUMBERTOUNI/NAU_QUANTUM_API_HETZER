#!/bin/bash
# Sentinel Quantum Edge v5.3 - Optimized for Hetzner CX43 (8 CPU, 16GB RAM)
exec uvicorn api:app --host 0.0.0.0 --port 9000 --workers 8 --timeout-keep-alive 180
