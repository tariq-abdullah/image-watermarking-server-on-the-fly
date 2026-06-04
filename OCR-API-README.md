# PaddleOCR API Server

A fast OCR API service using PaddleOCR running on port **5001**.

## Features

- **Port**: 5001 (unique port)
- **Format**: Returns extracted text in **Markdown** format
- **File Upload**: Accept image files (JPG, PNG, WEBP, BMP, TIFF)
- **URL Support**: Accept image URLs for remote processing
- **Systemd Service**: Auto-restart on failure, runs on system startup
- **Text Extraction**: Line-based text grouping with confidence scores

## API Endpoints

### 1. Health Check
```bash
GET /health
```

**Response:**
```json
{
  "status": "ok",
  "service": "ocr-api"
}
```

### 2. OCR from File Upload
```bash
POST /ocr
```

**Request:**
```bash
curl -F "image=@/path/to/image.jpg" http://localhost:5001/ocr
```

**Response:**
```json
{
  "success": true,
  "markdown": "# OCR Result\n\nExtracted text from image\n\n---\n*Average confidence: 95.2%*",
  "raw_detections": 42
}
```

### 3. OCR from URL
```bash
POST /ocr/url
```

**Request:**
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/image.jpg"}' \
  http://localhost:5001/ocr/url
```

**Response:**
```json
{
  "success": true,
  "markdown": "# OCR Result\n\nExtracted text...",
  "raw_detections": 42,
  "url": "https://example.com/image.jpg"
}
```

## Supported Image Formats

- JPG / JPEG
- PNG
- WEBP
- BMP
- TIFF

## Configuration

Configuration is read from `/etc/watermark-server.env`:

```bash
OCR_PORT=5001              # Port (default: 5001)
CACHE_DIR=/opt/watermark-server/cache
MAX_IMAGE_BYTES=8000000    # 8MB max image size
```

## Service Management

### Start the service
```bash
systemctl start ocr-api.service
```

### Stop the service
```bash
systemctl stop ocr-api.service
```

### Restart the service
```bash
systemctl restart ocr-api.service
```

### Check status
```bash
systemctl status ocr-api.service
```

### View logs
```bash
journalctl -u ocr-api.service -f
```

## Installation Details

- **Location**: `/opt/watermark-server/ocr-api.py`
- **Virtual Environment**: `/opt/watermark-server/venv`
- **Service File**: `/etc/systemd/system/ocr-api.service`
- **Dependencies**: PaddleOCR, PaddlePaddle, Flask

## Testing

### Test health endpoint
```bash
curl http://localhost:5001/health | python3 -m json.tool
```

### Test with sample image
```bash
curl -F "image=@test_image.jpg" http://localhost:5001/ocr | python3 -m json.tool
```

## Markdown Output Format

The OCR results are returned in markdown format with:

1. **Header**: `# OCR Result`
2. **Text content**: Extracted text grouped by lines
3. **Confidence**: Average confidence percentage at the bottom
4. **Separator**: Dividing line for clarity

Example output:
```markdown
# OCR Result

The quick brown fox
jumps over the lazy dog

---
*Average confidence: 92.5%*
```

## Error Handling

The API returns appropriate HTTP status codes:

- **200**: Success
- **400**: Bad request (missing image, invalid format)
- **413**: Payload too large
- **500**: Server error (OCR processing failed)

## Performance

- **First request**: ~3-5 seconds (model loading)
- **Subsequent requests**: ~1-2 seconds (depends on image size)
- **Memory usage**: ~350MB (PaddleOCR models in memory)
- **Concurrent requests**: Handled sequentially

## Notes

- Models are downloaded and cached automatically on first run
- The service will auto-restart on failure
- Temporary files are cleaned up after processing
- All requests are logged to systemd journal
