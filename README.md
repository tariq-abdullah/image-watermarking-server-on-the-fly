# Watermark Image Server

Fast on-the-fly image watermarking server with:

- JWT-secured requests
- DigitalOcean Spaces support
- Local image caching
- HTTPS support
- Auto-start on reboot
- Nginx reverse proxy
- libvips high-performance image processing

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
✅ Supports:
- JPG
- PNG
- WEBP

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
| App | `/opt/watermark-server` |
| Cache | `/opt/watermark-server/cache` |
| Config | `/etc/watermark-server.env` |
| Service | `/etc/systemd/system/watermark-server.service` |

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

