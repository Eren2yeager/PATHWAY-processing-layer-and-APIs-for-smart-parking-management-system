# Quick Start Guide - Pathway Smart Parking System

## 🚀 Get Started in 5 Minutes

### Step 1: Setup Environment

**Windows:**
```bash
cd pathway-work
setup.bat
```

**Linux/Mac:**
```bash
cd pathway-work
chmod +x setup.sh
./setup.sh
```

### Step 2: Configure API Keys

Edit `.env` file and add your Roboflow API key:

```bash
ROBOFLOW_API_KEY=your_actual_api_key_here
ROBOFLOW_WORKSPACE=your_workspace
ROBOFLOW_LICENSE_PLATE_PROJECT=license-plate-recognition-rxg4e
ROBOFLOW_LICENSE_PLATE_VERSION=11
ROBOFLOW_PARKING_SLOT_PROJECT=car-space-find
ROBOFLOW_PARKING_SLOT_VERSION=2
```

### Step 3: Run the Application

**Activate virtual environment:**

Windows:
```bash
venv\Scripts\activate
```

Linux/Mac:
```bash
source venv/bin/activate
```

**Start the server:**
```bash
python main.py
```

The server will start on `http://localhost:8000`

### Step 4: Test the APIs

**Health Check:**
```bash
curl http://localhost:8000/api/health
```

**Test License Plate Detection:**
```bash
curl -X POST http://localhost:8000/api/recognize-plate \
  -F "file=@test_image.jpg"
```

**Test Parking Slot Detection:**
```bash
curl -X POST http://localhost:8000/api/detect-parking-slots \
  -F "file=@parking_lot.jpg"
```

### Step 5: Connect Next.js

Your Next.js app should already be configured to connect to `http://localhost:8000`.

The WebSocket endpoints are:
- `ws://localhost:8000/ws/gate-monitor` - License plate detection stream
- `ws://localhost:8000/ws/lot-monitor` - Parking capacity stream

## 📊 API Documentation

Once running, visit:
- API Docs: `http://localhost:8000/docs`
- Alternative Docs: `http://localhost:8000/redoc`

## 🔧 Troubleshooting

### Issue: "Module not found"
**Solution:** Make sure virtual environment is activated and dependencies are installed:
```bash
pip install -r requirements.txt
```

### Issue: "Roboflow API key invalid"
**Solution:** Check your `.env` file and ensure `ROBOFLOW_API_KEY` is set correctly.

### Issue: "CUDA not available" (EasyOCR)
**Solution:** EasyOCR will automatically fall back to CPU mode. This is normal if you don't have a GPU.

### Issue: Port 8000 already in use
**Solution:** Change the port in `.env`:
```bash
PATHWAY_PORT=8001
```

## 📝 Next Steps

1. ✅ Test with your camera feeds
2. ✅ Integrate with Next.js frontend
3. ✅ Monitor performance and logs
4. 🔜 Add Pathway stateful processing features

## 🆘 Need Help?

Check the logs in `logs/pathway.log` for detailed error messages.

For more information, see the main [README.md](README.md) and [pathwayplan.md](../pathwayplan.md).
