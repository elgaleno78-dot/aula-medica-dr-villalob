#!/bin/sh
python3 -m pip install -r requirements.txt
export AULA_ADMIN_PASSWORD="CambiarEstaClave2026"
python3 -m uvicorn app:app --host 0.0.0.0 --port 8765
