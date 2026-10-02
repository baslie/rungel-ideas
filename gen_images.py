"""Картинки для лендингов: images.json -> RoyalTechno nano-banana-pro -> assets/img/.

  python gen_images.py hero section-1 --takes 3   снять дубли в assets/img/src/<key>-<n>.jpg
  python gen_images.py --all --takes 2            все картинки из images.json
  python gen_images.py --pick hero 2              дубль 2 -> assets/img/hero.webp (≤1600px)
  python gen_images.py --sheet                    контактный лист assets/img/src/_sheet.jpg

Платит только план nano_banana (баланс $0): чужая модель упадёт в 402, поэтому модель
зашита. Ключ: env ROYALTECHNO_API_KEY или ../golosom-razuma/secrets.env, в репозиторий
не копируется. Правила API — golosom-razuma/CLAUDE.md, раздел «RoyalTechno API».
"""
import argparse
import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

ROOT = Path(__file__).parent
SRC = ROOT / "assets" / "img" / "src"
OUT = ROOT / "assets" / "img"
BASE = "https://api.royaltechno.cc"
MODEL = "nano-banana-pro"
CFG = json.loads((ROOT / "images.json").read_text(encoding="utf-8"))


def api_key() -> str:
    if os.environ.get("ROYALTECHNO_API_KEY"):
        return os.environ["ROYALTECHNO_API_KEY"]
    env = ROOT.parent / "golosom-razuma" / "secrets.env"
    for line in env.read_text(encoding="utf-8").splitlines():
        k, sep, v = line.partition("=")
        if sep and k.strip() == "ROYALTECHNO_API_KEY":
            return v.strip().strip('"')
    sys.exit("нет ROYALTECHNO_API_KEY")


HDR = {"Authorization": f"Bearer {api_key()}"}


def shoot(key: str, take: int) -> str:
    spec = CFG["images"][key]
    dst = SRC / f"{key}-{take}.jpg"
    if dst.exists():
        return f"{dst.name}: уже есть"
    body = {"model": MODEL, "input": {
        "prompt": f"{spec['prompt']} {CFG['style']}",
        "aspect_ratio": spec["aspect"], "resolution": spec["resolution"]}}
    idem = str(uuid.uuid4())
    for attempt in range(3):  # ретраим только 503, с тем же Idempotency-Key
        r = httpx.post(f"{BASE}/v1/jobs", json=body, timeout=60,
                       headers={**HDR, "Idempotency-Key": idem})
        if r.status_code != 503:
            break
        time.sleep(20)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"{key}-{take}: {r.status_code} {r.text[:300]}")
    job = r.json()
    if job.get("cost_usd_cents"):
        print(f"  ! {key}-{take}: платная генерация {job['cost_usd_cents']}¢", flush=True)
    t0 = time.time()
    while job["status"] in ("queued", "processing"):
        if time.time() - t0 > 900:
            httpx.post(f"{BASE}/v1/jobs/{job['id']}/cancel", headers=HDR, timeout=30)
            raise RuntimeError(f"{key}-{take}: таймаут")
        time.sleep(5)
        job = httpx.get(f"{BASE}/v1/jobs/{job['id']}", headers=HDR, timeout=30).json()
    if job["status"] != "succeeded":
        raise RuntimeError(f"{key}-{take}: {job['status']} {job.get('error')}")
    for _ in range(3):
        try:
            data = httpx.get(job["output"]["url"], timeout=120).content
            break
        except httpx.HTTPError:
            time.sleep(5)
    dst.write_bytes(data)
    return f"{dst.name}: {len(data) // 1024} КБ за {time.time() - t0:.0f} с"


def pick(key: str, take: int):
    im = Image.open(SRC / f"{key}-{take}.jpg").convert("RGB")
    im.thumbnail((1600, 1600), Image.LANCZOS)
    dst = OUT / f"{key}.webp"
    for q in (80, 72, 64, 56):
        im.save(dst, "WEBP", quality=q, method=6)
        if dst.stat().st_size <= 320 * 1024:
            break
    print(f"{dst.name}: {im.size[0]}x{im.size[1]}, {dst.stat().st_size // 1024} КБ, q={q}")


def sheet():
    files = sorted(SRC.glob("*-*.jpg"))
    cell, cols = 420, 4
    rows = (len(files) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * cell, rows * (cell + 24)), "white")
    d = ImageDraw.Draw(canvas)
    for i, f in enumerate(files):
        im = Image.open(f)
        im.thumbnail((cell - 8, cell - 8))
        x, y = (i % cols) * cell, (i // cols) * (cell + 24)
        canvas.paste(im, (x + 4, y + 4))
        d.text((x + 6, y + cell + 4), f.stem, fill="black")
    canvas.save(SRC / "_sheet.jpg", quality=85)
    print(SRC / "_sheet.jpg")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--takes", type=int, default=2)
    ap.add_argument("--pick", nargs=2, metavar=("KEY", "N"))
    ap.add_argument("--sheet", action="store_true")
    a = ap.parse_args()
    SRC.mkdir(parents=True, exist_ok=True)
    if a.pick:
        return pick(a.pick[0], int(a.pick[1]))
    if a.sheet:
        return sheet()
    keys = list(CFG["images"]) if a.all else a.keys
    tasks = [(k, n) for k in keys for n in range(1, a.takes + 1)]
    with ThreadPoolExecutor(5) as ex:  # nano_banana: 5 одновременно
        for fut in [ex.submit(shoot, k, n) for k, n in tasks]:
            try:
                print(fut.result(), flush=True)
            except Exception as e:
                print("ОШИБКА", e, flush=True)


if __name__ == "__main__":
    main()
