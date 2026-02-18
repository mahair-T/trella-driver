# 📄 Trella POD Capture App

Driver-facing Streamlit app for capturing Proof of Delivery documents at drop-off points.

## Features

- **Multi-language**: Arabic, Urdu, English with full RTL support
- **Driver verification**: Shows shipment details from Redash API for driver confirmation
- **Image quality checking**: Detects blurry, dark, overexposed, and low-resolution images using OpenCV
- **Smart fallback**: After 3 failed quality attempts, prompts driver to upload 3 photos from different angles
- **Mobile-first**: Optimized for phone cameras with `st.camera_input`
- **Metadata tracking**: Saves POD images with full shipment metadata JSON

## How It Works

```
Driver receives link → Language selection → Confirm details → Take photo
                                                                  ↓
                                                         Quality check passes? ──→ Submit ✅
                                                                  ↓ (fail)
                                                         Retry (up to 3 attempts)
                                                                  ↓ (3 fails)
                                                         Upload 3 photos → Submit ✅
```

## Driver Link Format

```
https://<your-app-url>/?shipment=<shipment_key>
```

Example:
```
https://your-app.streamlit.app/?shipment=shp51018426a3d0d370
```

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment (Streamlit Cloud)

1. Push this folder to a GitHub repo
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo and deploy
4. Update `APP_BASE_URL` in `send_links.py` with your deployed URL

## Sending Links to Drivers

```bash
# Print all driver links for shipments at drop-off
python send_links.py

# Generate WhatsApp links in Arabic (default)
python send_links.py --send-whatsapp --lang ar
```

## Image Quality Thresholds

| Check | Threshold | What it detects |
|-------|-----------|----------------|
| Blur (Laplacian) | < 80.0 variance | Blurry/out-of-focus photos |
| Darkness | < 40.0 mean brightness | Too dark / low light |
| Overexposure | > 240.0 mean brightness | Washed out / glare |
| Resolution | < 640×480 | Too-small images |
| Edge ratio | < 2% edge pixels | No document detected |
| Block blur | > 60% blocks blurry | Smudges / partial lens obstruction |

Adjust these in `app.py` config section if needed based on your drivers' typical phone cameras.

## Storage

By default, POD images are saved locally under `pod_uploads/<shipment_key>/`:
```
pod_uploads/
  shp51018426a3d0d370/
    pod_0_20260218_143022.jpg
    metadata.json
```

**For production**, replace `save_pod_image()` with your cloud storage (S3, GCS, Azure Blob). The metadata JSON contains all shipment details for matching.

## File Structure

```
pod_capture/
├── app.py              # Main Streamlit app
├── send_links.py       # Driver link generator + WhatsApp integration
├── requirements.txt    # Python dependencies
└── README.md           # This file
```
