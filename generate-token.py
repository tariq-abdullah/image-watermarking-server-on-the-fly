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
