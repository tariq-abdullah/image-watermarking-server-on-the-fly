import os, time, hashlib
from urllib.parse import urlparse
from io import BytesIO
import jwt, requests, pyvips
from flask import Flask, request, send_file, abort
from dotenv import load_dotenv

load_dotenv("/etc/watermark-server.env")
app = Flask(__name__)

JWT_SECRET = os.getenv("JWT_SECRET", "")
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_IMAGE_HOSTS", "").split(",") if h.strip()]
CACHE_DIR = os.getenv("CACHE_DIR", "/opt/watermark-server/cache")
MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", "8000000"))

os.makedirs(CACHE_DIR, exist_ok=True)
SOURCE_CACHE_DIR = os.path.join(CACHE_DIR, "source")
SOURCE_CACHE_TTL = 86400

os.makedirs(SOURCE_CACHE_DIR, exist_ok=True)

def cleanup_old_cache():
    now = time.time()

    for folder in [CACHE_DIR, SOURCE_CACHE_DIR]:
        for name in os.listdir(folder):
            path = os.path.join(folder, name)

            if not os.path.isfile(path):
                continue

            if now - os.path.getmtime(path) > SOURCE_CACHE_TTL:
                try:
                    os.remove(path)
                except OSError:
                    pass

def source_cache_path(url):
    parsed = urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lower()

    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        ext = ".img"

    return os.path.join(
        SOURCE_CACHE_DIR,
        hashlib.sha256(url.encode()).hexdigest() + ext
    )
def verify_host(url):
    parsed = urlparse(url)
    host = parsed.netloc
    path = parsed.path.lower()

    if parsed.scheme not in ["https", "http"]:
        abort(403, "Only http/https allowed")

    if ALLOWED_HOSTS and host not in ALLOWED_HOSTS:
        abort(403, "Image host not allowed")

    if not path.endswith((".jpg", ".jpeg", ".png", ".webp")):
        abort(403, "File type not allowed")

def verify_jwt(token, params):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        abort(403, "Invalid token")

    for key in ["text", "pos", "x", "y", "size", "opacity"]:
        if str(payload.get(key, "")) != str(params.get(key, "")):
            abort(403, f"Tampered parameter: {key}")

    params["img"] = str(payload.get("img", ""))

    if not params["img"]:
        abort(403, "Missing image in token")

    return payload

def cache_key(params):
    raw = "|".join(str(params.get(k, "")) for k in ["img","text","pos","x","y","size","opacity"])
    return hashlib.sha256(raw.encode()).hexdigest() + ".jpg"

def download_image(url):
    verify_host(url)

    cached_source = source_cache_path(url)

    if os.path.exists(cached_source):
        if time.time() - os.path.getmtime(cached_source) <= SOURCE_CACHE_TTL:
            with open(cached_source, "rb") as f:
                return f.read()
        else:
            try:
                os.remove(cached_source)
            except OSError:
                pass

    r = requests.get(url, timeout=15, stream=True)
    r.raise_for_status()

    ctype = r.headers.get("content-type", "")
    if not ctype.startswith("image/"):
        abort(403, "Remote file is not image")

    data = BytesIO()
    total = 0

    for chunk in r.iter_content(chunk_size=1024 * 256):
        total += len(chunk)
        if total > MAX_IMAGE_BYTES:
            abort(413, "Image too large")
        data.write(chunk)

    image_bytes = data.getvalue()

    with open(cached_source, "wb") as f:
        f.write(image_bytes)

    return image_bytes

def position_xy(w, h, tw, th, pos, x, y):
    m = 30
    if pos == "top-left": return m, m
    if pos == "top-right": return w - tw - m, m
    if pos == "bottom-left": return m, h - th - m
    if pos == "bottom-right": return w - tw - m, h - th - m
    if pos == "center": return int((w - tw) / 2), int((h - th) / 2)
    if pos == "custom": return int(x or 0), int(y or 0)
    return w - tw - m, h - th - m

def watermark_image(image_bytes, text, pos, x, y, size, opacity):
    base = pyvips.Image.new_from_buffer(image_bytes, "", access="sequential").colourspace("srgb")

    if base.width > 10000 or base.height > 10000:
        abort(413, "Image dimensions too large")

    font_size = int(size or 42)
    text_opacity = float(opacity or 0.55)
    bg_opacity = 0.5
    pad = 18

    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    text_mask = pyvips.Image.text(escaped, font=f"Sans {font_size}", rgba=False, dpi=72)
    svg_width = text_mask.width + (pad * 2)
    svg_height = text_mask.height + (pad * 2)
    text_y = pad + font_size

    svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width}" height="{svg_height}">
  <rect x="0" y="0" width="100%" height="100%" fill="yellow" fill-opacity="{bg_opacity}"/>
  <text x="{pad}" y="{text_y}" font-family="Sans" font-size="{font_size}" fill="black" fill-opacity="{text_opacity}">{escaped}</text>
</svg>
"""

    watermark = pyvips.Image.svgload_buffer(svg.encode("utf-8")).colourspace("srgb")

    px, py = position_xy(base.width, base.height, watermark.width, watermark.height, pos, x, y)
    out = base.composite2(watermark, "over", x=px, y=py)

    return out.jpegsave_buffer(Q=82, strip=True, optimize_coding=True)

@app.route("/watermark")
def watermark():
    cleanup_old_cache()
    params = {
        "img": "",
        "text": request.args.get("text", ""),
        "pos": request.args.get("pos", "bottom-right"),
        "x": request.args.get("x", ""),
        "y": request.args.get("y", ""),
        "size": request.args.get("size", "42"),
        "opacity": request.args.get("opacity", "0.55"),
    }

    token = request.args.get("token", "")

    if not JWT_SECRET or JWT_SECRET == "change-this-to-a-long-random-secret":
        abort(500, "JWT_SECRET not configured")

    if not token:
        abort(403, "Missing token")

    verify_jwt(token, params)


    output = watermark_image(
        download_image(params["img"]),
        params["text"],
        params["pos"],
        params["x"],
        params["y"],
        params["size"],
        params["opacity"]
    )

    return send_file(
        BytesIO(output),
        mimetype="image/jpeg",
        max_age=0
    )




@app.route("/health")
def health():
    return "ok"
