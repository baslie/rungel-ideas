"""reviews.json + work/<id>.json -> reviews.html (видео подтягиваются из media/)."""
import json
from pathlib import Path

ROOT = Path(__file__).parent
data = json.loads((ROOT / "reviews.json").read_text(encoding="utf-8"))
for st in data["stories"]:
    for r in st["clips"]:
        raw = json.loads((ROOT / "work" / f"{r['id']}.json").read_text(encoding="utf-8"))
        r["file"], r["duration"] = raw["file"], raw["duration"]

payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
html = (ROOT / "template.html").read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
(ROOT / "reviews.html").write_text(html, encoding="utf-8")
print("reviews.html:", len(html) // 1024, "KB")
