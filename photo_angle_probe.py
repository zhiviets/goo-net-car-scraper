"""Проверка точности: ракурс главного фото машин сайта (перед / зад / сбоку / салон / другое) — нейросеть
CLIP без обучения. Листы с примерами по классам — в ветку probe-out (out/*.jpg). Ничего на сайте не меняет."""
import io
import json
import os
import random
import subprocess
import sys

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "torch", "--index-url", "https://download.pytorch.org/whl/cpu"], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "open_clip_torch"], check=True)

import httpx
import open_clip
import torch
from PIL import Image, ImageDraw

URL = os.environ["BN_AUTO_URL"].rstrip("/")
PER_COUNTRY = int(os.environ.get("PROBE_N") or "100")

PROMPTS = {
    "перед": ["a photo of the front of a car", "a car photographed from the front left side",
              "a car photographed from the front right side", "front three-quarter view of a car showing headlights and grille"],
    "зад": ["a photo of the back of a car", "rear view of a car showing taillights and trunk",
            "rear three-quarter view of a car"],
    "сбоку": ["side profile view of a car"],
    "салон": ["car interior with steering wheel and dashboard", "car seats inside a car", "close-up of a car dashboard",
              "the trunk or cargo area of a car"],
    "другое": ["a car engine bay", "a close-up of a car wheel", "a document with text", "a car key"],
}

model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k")
tok = open_clip.get_tokenizer("ViT-B-32")
labels = [(cls, p) for cls, ps in PROMPTS.items() for p in ps]
with torch.no_grad():
    tf = model.encode_text(tok([p for _, p in labels]))
    tf /= tf.norm(dim=-1, keepdim=True)


def classify(img: Image.Image) -> tuple[str, float, dict]:
    with torch.no_grad():
        f = model.encode_image(preprocess(img).unsqueeze(0))
        f /= f.norm(dim=-1, keepdim=True)
        probs = (100 * f @ tf.T).softmax(dim=-1)[0].tolist()
    agg = {}
    for (cls, _), p in zip(labels, probs):
        agg[cls] = agg.get(cls, 0) + p
    best = max(agg, key=agg.get)
    return best, agg[best], agg


client = httpx.Client(timeout=60)
results = []
random.seed(7)
for country in ("Япония", "Корея", "Китай"):
    first = client.get(f"{URL}/api/live-listings/search", params={"country": country, "per": 60, "page": 1}).json()
    pages = max(1, (first.get("total") or 0) // 60)
    picked = []
    for page in random.sample(range(1, pages + 1), min(pages, 4)):
        data = first if page == 1 else client.get(f"{URL}/api/live-listings/search",
                                                     params={"country": country, "per": 60, "page": page}).json()
        picked += data.get("listings") or data.get("items") or []
    random.shuffle(picked)
    for l in picked[:PER_COUNTRY]:
        if not l.get("photo_url"):
            continue
        try:
            raw = client.get(URL + l["photo_url"] if l["photo_url"].startswith("/") else l["photo_url"]).content
            img = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as e:
            print("фото не открылось", l.get("id"), e)
            continue
        cls, p, agg = classify(img)
        results.append({"country": country, "id": l["id"], "title": l.get("title"), "cls": cls, "p": round(p, 2),
                        "agg": {k: round(v, 2) for k, v in agg.items()}, "img": img})
    got = [r for r in results if r["country"] == country]
    print(f"{country}: " + ", ".join(f"{c} — {sum(1 for r in got if r['cls'] == c)}" for c in PROMPTS))

os.makedirs("out", exist_ok=True)
for cls in PROMPTS:
    rows = [r for r in results if r["cls"] == cls]
    if not rows:
        continue
    rows = rows[:60]
    cols, w, h = 6, 260, 210
    sheet = Image.new("RGB", (cols * w, ((len(rows) + cols - 1) // cols) * h), "white")
    d = ImageDraw.Draw(sheet)
    for i, r in enumerate(rows):
        t = r["img"].copy()
        t.thumbnail((w - 10, h - 34))
        x, y = (i % cols) * w, (i // cols) * h
        sheet.paste(t, (x + 5, y + 5))
        d.text((x + 5, y + h - 27), f"{r['country'][:2]} {r['id']} {cls} {r['p']:.2f}", fill="black")
        d.text((x + 5, y + h - 15), (r["title"] or "")[:38], fill="black")
    sheet.save(f"out/{cls}.jpg", quality=80)
with open("out/results.json", "w", encoding="utf-8") as f:
    json.dump([{k: v for k, v in r.items() if k != "img"} for r in results], f, ensure_ascii=False, indent=1)
print("Неуверенные (перед < 0.6, но выбран перед): " + str(sum(1 for r in results if r["cls"] == "перед" and r["p"] < 0.6)))

subprocess.run("git config user.name probe && git config user.email probe@users.noreply.github.com && "
               "git checkout -q --orphan probe-out && git rm -rq --cached . && git add out && "
               "git commit -qm 'photo angle probe' && git push -qf origin probe-out", shell=True, check=True)
print("Листы — в ветке probe-out")
