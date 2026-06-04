#!/usr/bin/env python3
"""
PaddleOCR API Server
Extracts text from images and returns in markdown format
"""

import os
import time
from io import BytesIO
from paddleocr import PaddleOCR
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv("/etc/watermark-server.env")

app = Flask(__name__)

# Configuration
OCR_PORT = int(os.getenv("OCR_PORT", "5001"))
CACHE_DIR = os.getenv("CACHE_DIR", "/opt/watermark-server/cache")
MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", "8000000"))
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "bmp", "tiff"}

# Initialize PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang="en")

os.makedirs(CACHE_DIR, exist_ok=True)


def allowed_file(filename):
    """Check if file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_to_markdown(ocr_result):
    """
    Convert PaddleOCR result to markdown format
    
    Args:
        ocr_result: List of tuples from PaddleOCR containing (bbox, (text, confidence))
    
    Returns:
        Markdown formatted string with extracted text
    """
    if not ocr_result:
        return "# OCR Result\n\nNo text detected in image."
    
    markdown = "# OCR Result\n\n"
    
    # Group results by approximate line (y-coordinate)
    lines = {}
    for detection in ocr_result:
        bbox, (text, confidence) = detection
        # Get y-coordinate of the top of the bounding box
        y_coord = int(bbox[0][1])
        
        # Group by line with some tolerance (within 20 pixels)
        line_key = (y_coord // 20) * 20
        if line_key not in lines:
            lines[line_key] = []
        lines[line_key].append({
            "text": text,
            "confidence": confidence,
            "x": bbox[0][0]
        })
    
    # Sort lines by y-coordinate
    for line_key in sorted(lines.keys()):
        # Sort text within line by x-coordinate
        line_items = sorted(lines[line_key], key=lambda x: x["x"])
        line_text = " ".join([item["text"] for item in line_items])
        avg_confidence = sum([item["confidence"] for item in line_items]) / len(line_items)
        
        markdown += f"{line_text}\n"
    
    markdown += f"\n---\n*Average confidence: {(avg_confidence * 100):.1f}%*\n"
    
    return markdown


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "ocr-api"}), 200


@app.route("/ocr", methods=["POST"])
def ocr_endpoint():
    """
    OCR endpoint that accepts image files
    
    Accepts:
        - multipart form data with 'image' file
        - base64 encoded image in 'image' field
    
    Returns:
        JSON with markdown formatted text extraction
    """
    try:
        # Check if image file is provided
        if "image" not in request.files and "image" not in request.form:
            return jsonify({
                "error": "No image provided",
                "instructions": "Send image as multipart form data with key 'image' or as base64 in 'image' field"
            }), 400
        
        image_data = None
        
        # Handle file upload
        if "image" in request.files:
            file = request.files["image"]
            
            if file.filename == "":
                return jsonify({"error": "No file selected"}), 400
            
            if not allowed_file(file.filename):
                return jsonify({
                    "error": f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
                }), 400
            
            # Check file size
            file.seek(0, 2)  # Seek to end
            file_size = file.tell()
            file.seek(0)  # Seek back to start
            
            if file_size > MAX_IMAGE_BYTES:
                return jsonify({
                    "error": f"File too large. Maximum size: {MAX_IMAGE_BYTES} bytes"
                }), 413
            
            image_data = file.read()
        
        # Handle base64 image
        elif "image" in request.form:
            import base64
            image_b64 = request.form.get("image")
            try:
                image_data = base64.b64decode(image_b64)
            except Exception as e:
                return jsonify({"error": f"Invalid base64 encoding: {str(e)}"}), 400
        
        if not image_data:
            return jsonify({"error": "Failed to process image"}), 400
        
        # Save to temporary file for PaddleOCR processing
        temp_path = os.path.join(CACHE_DIR, f"ocr_temp_{int(time.time() * 1000)}.tmp")
        with open(temp_path, "wb") as f:
            f.write(image_data)
        
        try:
            # Run OCR
            result = ocr.ocr(temp_path)
            
            # Convert to markdown
            markdown_text = extract_text_to_markdown(result[0] if result else [])
            
            return jsonify({
                "success": True,
                "markdown": markdown_text,
                "raw_detections": len(result[0]) if result else 0
            }), 200
        
        finally:
            # Clean up temp file
            try:
                os.remove(temp_path)
            except OSError:
                pass
    
    except Exception as e:
        return jsonify({
            "error": f"OCR processing failed: {str(e)}"
        }), 500


@app.route("/ocr/url", methods=["POST"])
def ocr_url_endpoint():
    """
    OCR endpoint that accepts image URLs
    
    POST data:
        {
            "url": "https://example.com/image.jpg"
        }
    
    Returns:
        JSON with markdown formatted text extraction
    """
    try:
        import requests
        from urllib.parse import urlparse
        
        data = request.get_json() or {}
        url = data.get("url", "")
        
        if not url:
            return jsonify({"error": "No URL provided"}), 400
        
        # Validate URL
        parsed = urlparse(url)
        if parsed.scheme not in ["https", "http"]:
            return jsonify({"error": "Only http/https URLs allowed"}), 400
        
        if not parsed.path.lower().endswith(tuple(f".{ext}" for ext in ALLOWED_EXTENSIONS)):
            return jsonify({
                "error": f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            }), 400
        
        # Download image
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            image_data = r.content
        except requests.RequestException as e:
            return jsonify({"error": f"Failed to download image: {str(e)}"}), 400
        
        # Check file size
        if len(image_data) > MAX_IMAGE_BYTES:
            return jsonify({
                "error": f"Image too large. Maximum size: {MAX_IMAGE_BYTES} bytes"
            }), 413
        
        # Check content type
        ctype = r.headers.get("content-type", "")
        if not ctype.startswith("image/"):
            return jsonify({"error": "Remote file is not an image"}), 400
        
        # Save to temporary file
        temp_path = os.path.join(CACHE_DIR, f"ocr_temp_{int(time.time() * 1000)}.tmp")
        with open(temp_path, "wb") as f:
            f.write(image_data)
        
        try:
            # Run OCR
            result = ocr.ocr(temp_path)
            
            # Convert to markdown
            markdown_text = extract_text_to_markdown(result[0] if result else [])
            
            return jsonify({
                "success": True,
                "markdown": markdown_text,
                "raw_detections": len(result[0]) if result else 0,
                "url": url
            }), 200
        
        finally:
            # Clean up temp file
            try:
                os.remove(temp_path)
            except OSError:
                pass
    
    except Exception as e:
        return jsonify({
            "error": f"OCR processing failed: {str(e)}"
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=OCR_PORT, debug=False)
