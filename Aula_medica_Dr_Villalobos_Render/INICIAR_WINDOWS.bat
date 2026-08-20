@echo off
title Aula medica Dr. Villalobos
python -m pip install -r requirements.txt
set AULA_ADMIN_PASSWORD=CambiarEstaClave2026
python -m uvicorn app:app --host 0.0.0.0 --port 8765
pause
