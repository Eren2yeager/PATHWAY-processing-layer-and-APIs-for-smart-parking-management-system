# Pathway-based Smart Parking Management System

AI/ML processing layer built with Pathway framework for real-time video stream processing, license plate detection, and parking capacity monitoring.

## 🚀 Features

- **Real-time Stream Processing**: Process multiple camera feeds simultaneously
- **Stateful Vehicle Tracking**: Track vehicles from entry to exit with automatic duration calculation
- **Incremental Capacity Monitoring**: Real-time parking slot occupancy with efficient updates
- **License Plate Detection**: Roboflow + EasyOCR integration
- **Duplicate Prevention**: Automatic deduplication of detections
- **High Performance**: Rust-powered Pathway engine for low-latency processing

## 📋 Prerequisites

- Python 3.9+
- Roboflow API key
- Next.js backend running (for webhook integration)

## 🛠️ Installation

1. Create virtual environment:
```bash
cd pathway-work
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Setup environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

## 🏃 Running

Start the Pathway application:
```bash
python main.py
```

The server will start on `http://localhost:8000`

## 📡 API Endpoints

### REST APIs

- `GET /api/health` - Health check (includes backend=pathway, active_streams)
- `POST /api/recognize-plate` - Detect license plates in image (multipart)
- `POST /api/detect-parking-slots` - Detect parking slot occupancy (multipart)
- `POST /api/detect-vehicle` - Detect vehicles (multipart)
- `POST /api/process-frame` - Process one frame (JSON: image base64, camera_id, parking_lot_id, type=gate|lot)
- `GET /api/capacity/current/{parking_lot_id}` - Current capacity from Pathway state

### WebSocket Streams

- `WS /ws/gate-monitor` - Real-time license plate detections (send JSON with data/image, camera_id, parking_lot_id)
- `WS /ws/lot-monitor` - Real-time capacity updates
- `WS /ws/webrtc-signaling` - WebRTC signaling for camera streaming

## 🏗️ Architecture

```
Camera Feeds → Pathway Pipeline → Next.js APIs → MongoDB
                     ↓
              WebSocket Streams → Frontend
```

## 📁 Project Structure

```
pathway-work/
├── main.py                 # Entry point
├── config/                 # Configuration
├── connectors/             # Input/output connectors
├── models/                 # AI model integrations
├── schemas/                # Data schemas
├── transformations/        # Stateful processing logic
└── utils/                  # Utilities
```

## 🔧 Configuration

Edit `.env` file to configure:
- Roboflow API credentials
- Detection confidence thresholds
- Frame processing settings
- Next.js webhook URLs

## 📊 Performance

- Processing: ~50-100 fps per stream
- Latency: <100ms per frame
- Concurrent streams: Up to 10 (configurable)

## 🧪 Testing

Run tests:
```bash
pytest tests/
```

## 📝 License

MIT
