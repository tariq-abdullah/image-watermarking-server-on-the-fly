#!/usr/bin/env bash
set -e

DOMAIN="$1"
APP_DIR="/opt/watermark-server"
ENV_FILE="/etc/watermark-server.env"
SERVICE_FILE="/etc/systemd/system/watermark-server.service"

apt update
apt install -y python3 python3-venv python3-pip libvips libvips-dev nginx curl certbot python3-certbot-nginx

mkdir -p "$APP_DIR/cache"
cd "$APP_DIR"

python3 -m venv venv
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install flask gunicorn pyvips requests PyJWT python-dotenv

if [ ! -f "$ENV_FILE" ]; then
cat > "$ENV_FILE" <<'EOF'
JWT_SECRET=change-this-to-a-long-random-secret
ALLOWED_IMAGE_HOSTS=your-bucket.sgp1.digitaloceanspaces.com,cdn.yourdomain.com
CACHE_DIR=/opt/watermark-server/cache
MAX_IMAGE_BYTES=8000000
EOF
fi

cat > "$APP_DIR/app.py" <<'PY'
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

    for key in ["img", "text", "pos", "x", "y", "size", "opacity"]:
        if str(payload.get(key, "")) != str(params.get(key, "")):
            abort(403, f"Tampered parameter: {key}")

def cache_key(params):
    raw = "|".join(str(params.get(k, "")) for k in ["img","text","pos","x","y","size","opacity"])
    return hashlib.sha256(raw.encode()).hexdigest() + ".jpg"

def download_image(url):
    verify_host(url)
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

    return data.getvalue()

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
    opacity = float(opacity or 0.55)
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    mask = pyvips.Image.text(escaped, font=f"Sans {font_size}", rgba=False, dpi=150)
    white = pyvips.Image.black(mask.width, mask.height).new_from_image([255, 255, 255])
    watermark = white.bandjoin(mask * opacity)

    px, py = position_xy(base.width, base.height, watermark.width, watermark.height, pos, x, y)
    out = base.composite(watermark, "over", x=px, y=py)

    return out.jpegsave_buffer(Q=82, strip=True, optimize_coding=True)

@app.route("/watermark")
def watermark():
    params = {
        "img": request.args.get("img", ""),
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

    cached = os.path.join(CACHE_DIR, cache_key(params))

    if os.path.exists(cached):
        return send_file(cached, mimetype="image/jpeg", max_age=3600)

    output = watermark_image(
        download_image(params["img"]),
        params["text"],
        params["pos"],
        params["x"],
        params["y"],
        params["size"],
        params["opacity"]
    )

    with open(cached, "wb") as f:
        f.write(output)

    return send_file(cached, mimetype="image/jpeg", max_age=3600)

@app.route("/health")
def health():
    return "ok"
PY

cat > "$APP_DIR/generate-token.py" <<'PY'
import os, time, jwt, argparse
from dotenv import load_dotenv

load_dotenv("/etc/watermark-server.env")

p = argparse.ArgumentParser()
p.add_argument("--img", required=True)
p.add_argument("--text", required=True)
p.add_argument("--pos", default="bottom-right")
p.add_argument("--x", default="")
p.add_argument("--y", default="")
p.add_argument("--size", default="42")
p.add_argument("--opacity", default="0.55")
p.add_argument("--ttl", type=int, default=3600)
a = p.parse_args()

payload = {
    "img": a.img,
    "text": a.text,
    "pos": a.pos,
    "x": a.x,
    "y": a.y,
    "size": a.size,
    "opacity": a.opacity,
    "exp": int(time.time()) + a.ttl
}

print(jwt.encode(payload, os.getenv("JWT_SECRET"), algorithm="HS256"))
PY

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Watermark Image Server
After=network.target

[Service]
User=root
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$APP_DIR/venv/bin/gunicorn -w 2 -b 127.0.0.1:8088 app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

SERVER_NAME="_"
if [ -n "$DOMAIN" ]; then
    SERVER_NAME="$DOMAIN"
fi

cat > /etc/nginx/sites-available/watermark-server <<EOF
server {
    listen 80;
    server_name $SERVER_NAME;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8088;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60;
    }
}
EOF

ln -sf /etc/nginx/sites-available/watermark-server /etc/nginx/sites-enabled/watermark-server
rm -f /etc/nginx/sites-enabled/default

systemctl daemon-reload
systemctl enable watermark-server
systemctl restart watermark-server
nginx -t
systemctl restart nginx

if [ -n "$DOMAIN" ]; then
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect
    systemctl reload nginx
fi

echo ""
echo "Installed successfully."
echo ""
echo "Edit config:"
echo "nano /etc/watermark-server.env"
echo ""
echo "Restart:"
echo "systemctl restart watermark-server"
echo ""
if [ -n "$DOMAIN" ]; then
    echo "HTTPS URL:"
    echo "https://$DOMAIN/health"
else
    echo "HTTP URL:"
    echo "http://YOUR_SERVER_IP/health"
    echo ""
    echo "To enable HTTPS, rerun with domain:"
    echo "sudo ./install-watermark-server.sh wm.yourdomain.com"
fi
