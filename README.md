# 🅿️ Pathway Smart Parking — Real-Time Stream Processing Backend

Real-time parking management powered by **[Pathway](https://pathway.com/)** — a Rust-based stream processing framework for Python. This backend processes live camera feeds through Pathway's dataflow engine for vehicle plate detection, duplicate filtering, capacity aggregation, and instant webhook delivery to the Next.js frontend.

## Architecture

```
┌─────────────────────┐     WebSocket      ┌──────────────────────────────────────────┐
│   Browser / Camera   │ ──────────────────▶│           FastAPI (main.py)               │
│   (Live Video Feed)  │                    │   Gate Monitor  ·  Lot Monitor            │
└─────────────────────┘                    └───────────┬──────────────┬───────────────┘
                                                       │              │
                                            ┌──────────▼──────────────▼───────────────┐
                                            │     Pathway Pipeline (pw.run())          │
                                            │                                          │
                                            │  ┌─────────────────┐ ┌────────────────┐  │
                                            │  │ Vehicle Pipeline │ │Capacity Pipeline│ │
                                            │  │                 │ │                 │  │
                                            │  │ ConnectorSubject│ │ ConnectorSubject│  │
                                            │  │   ↓ pw.Table    │ │   ↓ pw.Table    │  │
                                            │  │ Confidence Filter│ │Confidence Filter│ │
                                            │  │   ↓ deduplicate │ │   ↓ groupby     │  │
                                            │  │ ConnectorObserver│ │   ↓ reduce      │  │
                                            │  │   ↓ HTTP POST   │ │ ConnectorObserver│ │
                                            │  └────────┬────────┘ │   ↓ HTTP POST   │  │
                                            │           │          └────────┬────────┘  │
                                            └───────────┼───────────────────┼───────────┘
                                                        │                   │
                                              ┌─────────▼───────────────────▼──────────┐
                                              │        Next.js Webhook Routes           │
                                              │   /api/pathway/webhook/entry            │
                                              │   /api/pathway/webhook/exit             │
                                              │   /api/pathway/webhook/capacity          │
                                              │         ↓ MongoDB  ↓ SSE Broadcast      │
                                              └────────────────────────────────────────┘
```

## Pathway Transformations Used

| Transformation        | API                           | Purpose                                                     |
| --------------------- | ----------------------------- | ----------------------------------------------------------- |
| **Table creation**    | `pw.io.python.read()`         | Ingest live detections from `ConnectorSubject`              |
| **Confidence filter** | `pw.Table.filter()`           | Drop low-confidence detections below threshold              |
| **Deduplication**     | `pw.Table.deduplicate()`      | Suppress repeated plate detections within time window       |
| **Groupby + Reduce**  | `pw.Table.groupby().reduce()` | Aggregate per-slot status into per-lot capacity totals      |
| **Type casting**      | `pw.cast()`, `pw.if_else()`   | Typed column computation for sum/avg reducers               |
| **Output**            | `pw.io.python.write()`        | Push processed results to `ConnectorObserver` for webhooks  |
| **Engine**            | `pw.run()`                    | Rust-based incremental dataflow engine in background thread |

## Key Files

```
pathway-work/
├── main.py                          # FastAPI server, WebSocket handlers, Pathway lifecycle
├── pathway_pipeline.py              # Orchestrates full dataflow: input → transform → output
├── connectors/
│   ├── camera_input.py              # ConnectorSubject classes (data enters Pathway)
│   └── nextjs_output.py             # ConnectorObserver classes (data exits via sync HTTP)
├── transformations/
│   ├── duplicate_filter.py          # deduplicate() with custom time-window acceptor
│   ├── capacity_aggregation.py      # groupby().reduce() for real-time slot aggregation
│   └── vehicle_tracking.py          # Vehicle event classification and tracking
├── models/
│   ├── license_plate_detector.py    # Roboflow + EasyOCR plate detection (lazy retry)
│   ├── parking_slot_detector.py     # Roboflow slot occupancy detection (lazy retry)
│   └── vehicle_detector.py          # Vehicle type detection
├── config/
│   └── settings.py                  # Pydantic settings from .env
└── schemas/
    └── detection_result.py          # Typed result models
```

## Data Flow

### Vehicle Pipeline (Gate Monitor)

```
Camera frame → AI plate detection → ConnectorSubject.next()
  → pw.Table → filter(confidence > threshold)
  → deduplicate(value=timestamp, instance=plate, acceptor=time_window)
  → ConnectorObserver.on_change() → POST /webhook/entry|exit
  → MongoDB VehicleRecord + SSE broadcast to dashboard
```

### Capacity Pipeline (Lot Monitor)

```
Camera frame → AI slot detection → ConnectorSubject.next()
  + slot data stored in module-level slot store
  → pw.Table → filter(confidence > threshold)
  → groupby(lot_id, slot_id).reduce(latest status)
  → groupby(lot_id).reduce(count, sum occupied/empty)
  → select(occupancy_rate = occupied / total)
  → ConnectorObserver.on_change()
    → reads slot store for individual slot data
    → POST /webhook/capacity (with slot array + aggregated totals)
  → MongoDB CapacityLog + SSE broadcast to dashboard (real-time)
```

## API Endpoints

| Method | Endpoint                    | Description                                       |
| ------ | --------------------------- | ------------------------------------------------- |
| `GET`  | `/api/health`               | Health check with pipeline status                 |
| `POST` | `/api/recognize-plate`      | Detect & OCR license plates from uploaded image   |
| `POST` | `/api/detect-parking-slots` | Detect parking slot occupancy from uploaded image |
| `WS`   | `/ws/gate-monitor`          | Live gate camera → plate detection via Pathway    |
| `WS`   | `/ws/lot-monitor`           | Live lot camera → slot detection via Pathway      |
| `WS`   | `/ws/webrtc-signaling`      | WebRTC signaling for camera streams               |

> **Note:** REST APIs (`/api/recognize-plate`, `/api/detect-parking-slots`) are used for image testing and parking lot creation. All real-time processing flows through WebSocket → Pathway pipeline.

## Configuration

| Variable                     | Default                            | Description                              |
| ---------------------------- | ---------------------------------- | ---------------------------------------- |
| `ROBOFLOW_API_KEY`           | —                                  | Roboflow API key for AI models           |
| `PLATE_DETECTION_CONFIDENCE` | `20`                               | Min confidence % for plate detections    |
| `PARKING_SLOT_CONFIDENCE`    | `20`                               | Min confidence % for slot detections     |
| `DUPLICATE_DETECTION_WINDOW` | `10`                               | Seconds to suppress duplicate plates     |
| `GATE_FRAME_SKIP`            | `10`                               | Process every Nth gate camera frame      |
| `LOT_FRAME_SKIP`             | `20`                               | Process every Nth lot camera frame       |
| `PATHWAY_WEBHOOK_SECRET`     | —                                  | Shared secret for webhook authentication |
| `NEXTJS_API_URL`             | `http://host.docker.internal:3000` | Next.js base URL                         |

## Running

```bash
# Start with Docker
docker-compose up --build -d

# View logs
docker logs -f pathway-smart-parking

# Restart (code changes auto-mount via volume)
docker-compose restart

# Health check
curl http://localhost:8000/api/health
```

### Expected Startup Logs

```
✓ License Plate Detector
✓ Parking Slot Detector
✓ Vehicle Detector
✅ Input tables created
✅ Vehicle pipeline built (filter → dedup → webhook)
✅ Capacity pipeline built (filter → aggregate → webhook)
🚀 Pathway engine started in background thread
```

> If models fail to load (network issue), you'll see `WITHOUT model (will retry on first request)`. The models auto-retry on the next API call.

## Resilience Features

- **Lazy model retry** — If Roboflow models fail to load at startup (network issues), they auto-retry on the next request
- **Webhook authentication** — `X-Pathway-Secret` header secures all webhook calls to Next.js
- **Sync HTTP observers** — Pathway observers use synchronous `httpx.Client` to avoid event loop conflicts
- **Slot data passthrough** — Individual slot data stored in module-level dict, included in aggregated capacity webhooks
- **SSE real-time** — Capacity updates broadcast via SSE using `globalThis` singleton (survives Next.js HMR)

## Why Pathway?

| Aspect            | Traditional Python                | With Pathway                                |
| ----------------- | --------------------------------- | ------------------------------------------- |
| **Processing**    | Sequential dict lookups           | Incremental dataflow engine (Rust)          |
| **Deduplication** | Manual timestamp tracking         | `deduplicate()` with typed acceptor         |
| **Aggregation**   | `Counter()` / manual loops        | `groupby().reduce()` with typed columns     |
| **State**         | In-memory dicts (lost on restart) | Pathway tables with persistent semantics    |
| **Scalability**   | Single-threaded                   | Multi-threaded Rust engine via `pw.run()`   |
| **Output**        | Polling / manual push             | Reactive `ConnectorObserver` on data change |
