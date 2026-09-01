# Multi-stage build for the single-origin deploy (spec Section 7, step 10).
#
#   stage 1 (node:22)   — build the React SPA -> frontend/dist/
#   stage 2 (python:3.13)— install the backend, copy the built SPA where
#                          settings.py expects it (BASE_DIR.parent/frontend/dist),
#                          run collectstatic, serve with gunicorn.
#
# A Dockerfile (not a native Render Python service) because Render's Python
# runtime ships Node 18 and can't pin it — Vite 8 needs Node >= 20.19.
# `migrate` runs in the start command (below), not at build (no DB then) and
# not as a pre-deploy command (paid-plan only on Render).

# ---------------------------------------------------------------------------
FROM node:22-bookworm-slim AS frontend

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
FROM python:3.13-slim-bookworm AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# psycopg2-binary and Pillow ship self-contained manylinux wheels, so no
# apt build deps are needed on slim-bookworm.
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ ./backend/
# the built SPA at BASE_DIR.parent/frontend/dist (settings.FRONTEND_DIST)
COPY --from=frontend /app/frontend/dist ./frontend/dist

WORKDIR /app/backend

# collectstatic imports settings, which requires DJANGO_SECRET_KEY to be set.
# This value is used ONLY to run the build command — it is never referenced
# at runtime (Render injects the real secret then).
RUN DJANGO_SECRET_KEY="build-only-not-a-runtime-secret" \
    DJANGO_DEBUG="False" \
    python manage.py collectstatic --noinput

EXPOSE 10000
# Free plan has no pre-deploy hook, so apply migrations here then hand off to
# gunicorn (exec -> gunicorn is PID 1, gets signals). `migrate --noinput` is a
# ~1s no-op when there is nothing to apply; a failed migration crashes the
# container and Render keeps the previous version live.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-10000} --workers 2 --timeout 60"]
