#!/bin/bash
exec uvicorn api:app --host 0.0.0.0 --port 9000 --workers 4 --timeout-keep-alive 120
```

Y edita `Dockerfile`, cambia la línea EXPOSE:
```
EXPOSE 9000
