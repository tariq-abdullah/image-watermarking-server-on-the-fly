# Watermark Image Server

Fast on-the-fly image watermarking server with OCR text extraction:

- JWT-secured requests
- DigitalOcean Spaces support
- Local image caching
- HTTPS support
- Auto-start on reboot
- Nginx reverse proxy
- libvips high-performance image processing
- **PaddleOCR text extraction (Port 5001)**

Designed for:
- E-Paper systems
- Paywalled newspaper platforms
- Dynamic watermarking
- Leak tracing
- CDN-backed image delivery

---

# Features

✅ High-performance `libvips` image processing  
✅ JWT signed URLs  
✅ Prevents watermark tampering  
✅ Prevents open proxy abuse  
✅ HTTPS with Let's Encrypt  
✅ Auto restart on crash  
✅ Auto start on reboot  
✅ Local disk cache  
✅ **PaddleOCR text extraction via REST API**  
✅ **Markdown-formatted OCR results**  
✅ Supports:
- JPG
- PNG
- WEBP
- TIFF
- BMP

✅ Position presets:
- top-left
- top-right
- bottom-left
- bottom-right
- center
- custom x/y

---

# Requirements

Recommended VM:

| Traffic | Recommended |
|---|---|
| Low/Medium | 1 vCPU / 2GB RAM |
| High | 2 vCPU / 4GB RAM |

Recommended Cloud providers:

- ServerMango
- DigitalOcean
- Hetzner
- Vultr

OS:
- Ubuntu 22.04+
- Debian 12+

---

# One-line Installation

## HTTP only

```bash
curl -fsSL https://raw.githubusercontent.com/tariq-abdullah/image-watermarking-server-on-the-fly/main/install-watermark-server.sh | sudo bash
```

## HTTPS enabled

```bash
curl -fsSL https://raw.githubusercontent.com/tariq-abdullah/image-watermarking-server-on-the-fly/main/install-watermark-server.sh | sudo bash -s wm.yourdomain.com
```

Example:

```bash
curl -fsSL https://raw.githubusercontent.com/tariq-abdullah/image-watermarking-server-on-the-fly/main/install-watermark-server.sh | sudo bash -s wm.example.com
```

Before HTTPS install:
- Point DNS `A` record to VM IP
- Port 80 and 443 must be open

---

# After Installation

Edit config:

```bash
sudo nano /etc/watermark-server.env
```

Restart:

```bash
sudo systemctl restart watermark-server
```

Check health:

```bash
curl https://wm.yourdomain.com/health
```

Expected output:

```text
ok
```

---

# Generate JWT Token

```bash
/opt/watermark-server/venv/bin/python /opt/watermark-server/generate-token.py \
  --img "https://your-bucket.sgp1.digitaloceanspaces.com/page1.jpg" \
  --text "user@email.com | 2026-05-20 06:30" \
  --pos "bottom-right" \
  --size "42" \
  --opacity "0.55"
```

---

# Example Request

```text
https://wm.yourdomain.com/watermark?img=https://your-bucket.sgp1.digitaloceanspaces.com/page1.jpg&text=user@email.com%20%7C%202026-05-20%2006%3A30&pos=bottom-right&size=42&opacity=0.55&token=TOKEN_HERE
```

---

# Security Model

JWT token is tied to:

- image URL
- watermark text
- position
- coordinates
- opacity
- size
- expiry time

Users cannot:
- remove watermark
- move watermark
- reduce opacity
- change text
- use arbitrary images

without server secret.

---

# PaddleOCR API Server

A companion OCR service running on **port 5001** for extracting text from images.

## Features

✅ Fast PaddleOCR-based text extraction  
✅ Returns results in **Markdown format**  
✅ Supports file uploads and URLs  
✅ Auto-restart on failure  
✅ Auto-start on reboot  
✅ Confidence score reporting  
✅ Supports: JPG, PNG, WEBP, BMP, TIFF  

## API Endpoints

### Health Check
```bash
curl http://localhost:5001/health
```

### Extract text from file
```bash
curl -F "image=@image.jpg" http://localhost:5001/ocr
```

### Extract text from URL
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/image.jpg"}' \
  http://localhost:5001/ocr/url
```

## Response Format

All responses include extracted text in **Markdown format** with confidence scores:

```json
{
  "success": true,
  "markdown": "# OCR Result\n\nExtracted text organized by lines\n\n---\n*Average confidence: 95.2%*",
  "raw_detections": 42
}
```

## Configuration

Edit `/etc/watermark-server.env`:

```bash
OCR_PORT=5001              # Default: 5001
CACHE_DIR=/opt/watermark-server/cache
MAX_IMAGE_BYTES=8000000    # 8MB max image size
```

## Service Management

```bash
# Start the OCR service
systemctl start ocr-api.service

# Stop the OCR service
systemctl stop ocr-api.service

# Restart the OCR service
systemctl restart ocr-api.service

# Check status
systemctl status ocr-api.service

# View logs
journalctl -u ocr-api.service -f
```

## Performance

- **First request**: 3-5 seconds (model initialization)
- **Subsequent requests**: 1-2 seconds
- **Memory usage**: ~350MB (models cached in memory)
- **Request handling**: Sequential processing

## Example Usage

### Test OCR on file:
```bash
curl -F "image=@invoice.jpg" http://localhost:5001/ocr | python3 -m json.tool
```

### Test OCR on remote image:
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/document.png"}' \
  http://localhost:5001/ocr/url | python3 -m json.tool
```

---

# Recommended Production Setup

```text
Cloudflare CDN
        ↓
Watermark VM
        ↓
DigitalOcean Spaces
```

Benefits:
- CDN caching
- lower VM CPU usage
- lower bandwidth cost
- DDoS protection

Recommended Cloudflare SSL mode:
- Full (Strict)

---

# Service Management

Check status:

```bash
systemctl status watermark-server
```

Restart:

```bash
systemctl restart watermark-server
```

View logs:

```bash
journalctl -u watermark-server -f
```

---

# Auto-start on Reboot

Enabled automatically using systemd:

```bash
systemctl enable watermark-server
systemctl enable nginx
```

---

# Default Paths

| Item | Path |
|---|---|
| Watermark App | `/opt/watermark-server/app.py` |
| OCR API App | `/opt/watermark-server/ocr-api.py` |
| Cache | `/opt/watermark-server/cache` |
| Config | `/etc/watermark-server.env` |
| Watermark Service | `/etc/systemd/system/watermark-server.service` |
| OCR API Service | `/etc/systemd/system/ocr-api.service` |

---

# Performance Notes

This project uses:
- Python
- Gunicorn
- libvips

`libvips` is significantly faster and more memory efficient than:
- ImageMagick
- GD
- Imagick

for large-scale image watermarking workloads.

---

# Credits

Developed with assistance from OpenAI ChatGPT.

Architecture and deployment workflow customized for large-scale E-Paper systems by IQL Technologies and E-Paper Pro.

