#!/bin/sh
set -e
alembic upgrade head
# One worker, no reload: the live calls are held in this process's memory.
exec uvicorn hr_screener.app.api:create_app --factory --host 0.0.0.0 --port 7860
