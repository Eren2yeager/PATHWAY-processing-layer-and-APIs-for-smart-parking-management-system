# Quick Start Guide — Pathway Smart Parking Backend

Get the Pathway-powered parking backend running in Docker in under 5 minutes.

## Prerequisites

- **Docker Desktop** installed and running
- **Roboflow API Key** — sign up at [roboflow.com](https://roboflow.com) (free tier works)
- **Next.js frontend** running on `http://localhost:3000` (see `next.js-work/` folder)

## Step 1: Configure Environment

Copy or edit the `.env` file in the `pathway-work/` directory:

```bash
# Required — your Roboflow API key
ROBOFLOW_API_KEY=your_api_key_here
ROBOFLOW_WORKSPACE=your_workspace_name

# Roboflow model projects (these are the default models)
ROBOFLOW_LICENSE_PLATE_PROJECT=license-plate-recognition-rxg4e
ROBOFLOW_LICENSE_PLATE_VERSION=11
ROBOFLOW_PARKING_SLOT_PROJECT=car-space-find
ROBOFLOW_PARKING_SLOT_VERSION=2

# Detection confidence thresholds (0-100)
PLATE_DETECTION_CONFIDENCE=20
PARKING_SLOT_CONFIDENCE=20

# Frame skip (higher = less CPU, lower = more responsive)
GATE_FRAME_SKIP=10
LOT_FRAME_SKIP=20

# Pathway webhook secret (must match PATHWAY_WEBHOOK_SECRET in next.js-work/.env.local)
PATHWAY_WEBHOOK_SECRET=your_shared_secret

# Next.js URL (Docker uses host.docker.internal to reach your host machine)
NEXTJS_API_URL=http://host.docker.internal:3000
```

> **Important:** The `PATHWAY_WEBHOOK_SECRET` must match the value in `next.js-work/.env.local` for webhook authentication to work.

## Step 2: Build & Start the Container

```bash
cd pathway-work
docker-compose up --build -d
```

First build takes ~2-3 minutes (downloads Python packages). Subsequent builds are cached.

## Step 3: Verify It's Running

**Check logs:**

```bash
docker logs -f pathway-smart-parking
```

You should see:

```
✓ License Plate Detector
✓ Parking Slot Detector
✓ Vehicle Detector
✅ Input tables created
✅ Vehicle pipeline built
✅ Capacity pipeline built
🚀 Pathway engine started in background thread
Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:8000
```

**Health check:**

```bash
curl http://localhost:8000/api/health
```

**API docs:**

```
http://localhost:8000/docs
```

## Step 4: Connect to Next.js

Make sure your Next.js frontend (in `next.js-work/`) has these in `.env.local`:

```bash
PYTHON_BACKEND_URL=http://localhost:8000
PATHWAY_WEBHOOK_SECRET=your_shared_secret   # Must match pathway-work/.env
```

The frontend connects to the Pathway backend via:

- **WebSocket** `ws://localhost:8000/ws/gate-monitor` — live plate detection
- **WebSocket** `ws://localhost:8000/ws/lot-monitor` — live slot detection
- **REST** `http://localhost:8000/api/detect-parking-slots` — slot detection for parking lot creation

## Common Commands

```bash
# Start in background
docker-compose up -d

# View live logs
docker logs -f pathway-smart-parking

# Restart (picks up code changes via volume mount)
docker-compose restart

# Stop
docker-compose down

# Rebuild (only needed if requirements.txt changes)
docker-compose up --build -d
```

## Test the APIs

**License Plate Detection:**

```bash
curl -X POST http://localhost:8000/api/recognize-plate \
  -F "file=@test_image.jpg"
```

**Parking Slot Detection:**

```bash
curl -X POST http://localhost:8000/api/detect-parking-slots \
  -F "file=@parking_lot.jpg"
```

## Troubleshooting

| Issue                                            | Solution                                                              |
| ------------------------------------------------ | --------------------------------------------------------------------- |
| `failed to resolve source metadata` during build | Check your internet connection — Docker needs to pull the base image  |
| `WITHOUT model (will retry on first request)`    | Roboflow API unreachable at startup — models auto-retry on first use  |
| `connect ECONNREFUSED 127.0.0.1:3000` in logs    | Start the Next.js frontend first: `cd next.js-work && npm run dev`    |
| `X-Pathway-Secret mismatch` in Next.js logs      | Ensure `PATHWAY_WEBHOOK_SECRET` matches in both `.env` files          |
| `Port 8000 already in use`                       | Change `PATHWAY_PORT` in `.env` and update `docker-compose.yml` ports |
| `CUDA not available`                             | Normal — EasyOCR auto-falls back to CPU mode                          |

## Architecture Overview

For full technical details, see [README.md](README.md).
