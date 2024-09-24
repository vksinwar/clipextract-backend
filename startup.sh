#!/bin/bash
gunicorn --bind=0.0.0.0 --timeout 600 --workers 4 --worker-class uvicorn.workers.UvicornWorker app:app