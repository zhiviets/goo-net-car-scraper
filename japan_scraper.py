"""
Япония для bn-auto: объявления goo-net.com → раздел «Авто из Японии».

Запускается в GitHub Actions (.github/workflows/scrape.yml), 2 раза в неделю:
  1) обход марок (/usedcar/brand-TOYOTA/) и их моделей (/usedcar/brand-TOYOTA/car-NOAH/) —
     первые страницы моделей, машины с MIN_YEAR года;
  2) выбор: хотя бы по машине на модель, 75% до 160 л.с., по годам 70% 2022–2024,
     15% 2025–2026, 15% 2017–2021. Мощность — «最高出力» со страницы объявления
     (каталог нового автомобиля), её открываем только для машин, которые выбираем;
  3) порции по BATCH машин: страница объявления, фото, отправка в bn-auto (источник
     goonet) — и пауза BATCH_PAUSE минут.

Переменные окружения: BN_AUTO_URL, BN_AUTO_IMPORT_TOKEN (секреты репозитория),
GOONET_TOTAL (0 — само), GOONET_SCAN_MINUTES (90), GOONET_BATCH (100), GOONET_BATCH_PAUSE (1.5).
Без BN_AUTO_* скрипт собирает и печатает, но ничего не отправляет.
"""

import base64
import io
import json
import math
import os
import random
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from bs4 import BeautifulSoup

BASE = "https://www.goo-net.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
BN_AUTO_URL = os.environ.get("BN_AUTO_URL", "").rstrip("/")
BN_AUTO_IMPORT_TOKEN = os.environ.get("BN_AUTO_IMPORT_TOKEN", "")
# Сколько новых машин за прогон (0 — само: до FILL_TARGET на сайте, потом раз в неделю)
TOTAL = int(os.environ.get("GOONET_TOTAL") or "0")
# Заполнение каталога: пока машин на сайте меньше FILL_TARGET — каждый прогон (раз в 8 часов)
# добавляет до FILL_PER_RUN новых порциями по BATCH с паузой BATCH_PAUSE. Потом — обновление
# два раза в неделю (UPDATE_DAYS, 0 — понедельник, первый прогон дня): до UPDATE_NEW новых
# порциями по UPDATE_BATCH с паузой UPDATE_PAUSE минут; в остальное время прогон сразу заканчивается.
FILL_TARGET = int(os.environ.get("GOONET_FILL_TARGET") or "6000")
FILL_PER_RUN = int(os.environ.get("GOONET_FILL_PER_RUN") or "1000")
UPDATE_DAYS = {int(d) for d in (os.environ.get("GOONET_UPDATE_DAYS") or "2,5").split(",") if d.strip()}
UPDATE_NEW = int(os.environ.get("GOONET_UPDATE_NEW") or "600")
UPDATE_BATCH = int(os.environ.get("GOONET_UPDATE_BATCH") or "150")
UPDATE_PAUSE = float(os.environ.get("GOONET_UPDATE_PAUSE") or "30")
# Разнообразие: не больше стольких машин одной модели за прогон
PER_MODEL_RUN = int(os.environ.get("GOONET_PER_MODEL_RUN") or "4")
# Сколько машин с сайта, не встреченных при обходе, проверить заново (жива ли, дополнить)
VERIFY_LIMIT = int(os.environ.get("GOONET_VERIFY") or "300")
SHARE_160 = float(os.environ.get("GOONET_SHARE_160") or "0.75")
MIN_YEAR = int(os.environ.get("GOONET_MIN_YEAR") or "2017")
SCAN_MINUTES = float(os.environ.get("GOONET_SCAN_MINUTES") or "90")
WORKERS = int(os.environ.get("GOONET_WORKERS") or "2")
BATCH = int(os.environ.get("GOONET_BATCH") or "100")
# При заполнении — короткая пауза между порциями (1–2 мин), при обновлении — UPDATE_PAUSE
BATCH_PAUSE = float(os.environ.get("GOONET_BATCH_PAUSE") or "1.5")
# Для проверки: не больше стольких моделей (0 — все)
MAX_MODELS = int(os.environ.get("GOONET_MAX_MODELS") or "0")
# Сколько объявлений модели открывать, чтобы найти машину до 160 л.с.
RESOLVE_PER_MODEL = 4
# Фото: WebP до 960 px и до 150 КБ (храним в базе bn-auto, диск ограничен)
MAX_PHOTO_BYTES = 150 * 1024
PHOTO_MAX_WIDTH = 960
PHOTO_QUALITY = 72
YEAR_BANDS = [("2022–2024", 2022, 2024, 0.70), ("2025–2026", 2025, 2026, 0.15), ("2017–2021", 2017, 2021, 0.15)]

# Марки goo-net → как их пишем на сайте. Грузовики и спецтехнику не берём.
MAKES = {
    "TOYOTA": "Toyota", "LEXUS": "Lexus", "NISSAN": "Nissan", "HONDA": "Honda", "MAZDA": "Mazda",
    "SUBARU": "Subaru", "MITSUBISHI": "Mitsubishi", "SUZUKI": "Suzuki", "DAIHATSU": "Daihatsu",
    "MITSUOKA": "Mitsuoka", "MERCEDES_BENZ": "Mercedes-Benz", "BMW": "BMW", "VOLKSWAGEN": "Volkswagen",
    "AUDI": "Audi", "PORSCHE": "Porsche", "MINI": "MINI", "VOLVO": "Volvo", "PEUGEOT": "Peugeot",
    "LAND_ROVER": "Land Rover", "JAGUAR": "Jaguar", "JEEP": "Jeep", "FIAT": "Fiat", "ABARTH": "Abarth",
    "ALFA_ROMEO": "Alfa Romeo", "RENAULT": "Renault", "CITROEN": "Citroen", "FERRARI": "Ferrari",
    "LAMBORGHINI": "Lamborghini", "MASERATI": "Maserati", "BENTLEY": "Bentley", "ROLLS_ROYCE": "Rolls-Royce",
    "ASTON_MARTIN": "Aston Martin", "TESLA": "Tesla", "CHEVROLET": "Chevrolet", "CADILLAC": "Cadillac",
    "FORD": "Ford", "DS": "DS", "SMART": "Smart", "HYUNDAI": "Hyundai", "BYD": "BYD",
}
SKIP_BRANDS = {"ISUZU", "MITSUBISHI_FUSO", "HINO", "UD_TRUCKS", "NISSAN_DIESEL"}


def log(*a):
    print(*a, flush=True)


# ---------- загрузка ----------

def decode(resp: httpx.Response) -> str:
    """goo-net отдаёт страницы и в UTF-8, и в EUC-JP (страницы марок и моделей)."""
    raw = resp.content
    head = raw[:3000].decode("ascii", "ignore").lower()
    m = re.search(r"charset=([\w-]+)", resp.headers.get("content-type", "").lower()) or re.search(r"charset=[\"']?([\w-]+)", head)
    enc = m.group(1) if m else "utf-8"
    if enc in ("euc-jp", "eucjp", "x-euc-jp"):
        return raw.decode("euc_jis_2004", errors="replace")
    try:
        return raw.decode(enc)
    except (UnicodeDecodeError, LookupError):
        return raw.decode("euc_jis_2004", errors="replace")


class Fetcher:
    def __init__(self):
        self.client = httpx.Client(headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"}, timeout=40,
                                   follow_redirects=True)
        self.count = 0
        # После обхода списков — темп человека, листающего объявления: 2–5 с между страницами
        # и перерыв 1–2,5 мин каждые 25–40 страниц
        self.human = False
        self.next_break = random.randint(25, 40)

    def pace(self):
        if not self.human:
            time.sleep(random.uniform(0.8, 2.0))
            return
        if self.count >= self.next_break:
            pause = random.uniform(60, 150)
            log(f"  перерыв {pause / 60:.1f} мин (как человек)")
            time.sleep(pause)
            self.next_break = self.count + random.randint(25, 40)
        else:
            time.sleep(random.uniform(2.0, 5.0))

    def get(self, url: str) -> str | None:
        for attempt in range(3):
            self.pace()
            try:
                resp = self.client.get(url if url.startswith("http") else BASE + url)
            except httpx.HTTPError:
                time.sleep(3 * (attempt + 1))
                continue
            self.count += 1
            if resp.status_code == 429 or resp.status_code >= 500:
                # Сайт просит сбавить темп — долгая пауза, а не повтор сразу
                time.sleep(60 * (attempt + 1))
                continue
            return decode(resp)
        return None

    def photo(self, url: str) -> str | None:
        """Фото → сжатый data-URL (как у Кореи и Китая: храним у себя, а не ссылкой)."""
        from PIL import Image
        try:
            resp = self.client.get(url, headers={"Referer": BASE + "/"})
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        except Exception:
            return None
        # WebP: при том же качестве на ~40 % легче JPEG. 960 px по ширине хватает
        # для страницы объявления; тяжёлые снимки сжимаем сильнее, затем уменьшаем.
        quality, max_width = PHOTO_QUALITY, PHOTO_MAX_WIDTH
        while True:
            resized = img
            if resized.width > max_width:
                resized = resized.resize((max_width, max(1, round(resized.height * max_width / resized.width))), Image.LANCZOS)
            buf = io.BytesIO()
            resized.save(buf, format="WEBP", quality=quality, method=6)
            data = buf.getvalue()
            if len(data) <= MAX_PHOTO_BYTES or max_width <= 640:
                return "data:image/webp;base64," + base64.b64encode(data).decode("ascii")
            if quality > 55:
                quality -= 8
            else:
                max_width = int(max_width * 0.85)


def text_lines(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return [ln.strip() for ln in soup.get_text("\n").splitlines() if ln.strip()]


def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "").strip()


# ---------- марки и модели ----------

def model_name(slug: str) -> str:
    """car-CROWN_HYBRID → «Crown Hybrid», car-RAV4 → «RAV4», car-C_HR → «C-HR»."""
    words = slug.split("_")
    if len(words) == 2 and (all(len(w) <= 2 for w in words) or len(words[0]) == 1):
        return "-".join(words)
    return " ".join(w if (len(w) <= 3 or re.search(r"\d", w)) else w.capitalize() for w in words)


def brands(f: Fetcher) -> list[str]:
    html = f.get(BASE + "/") or ""
    found = list(dict.fromkeys(re.findall(r'href="(?:https://www\.goo-net\.com)?/usedcar/brand-([A-Z0-9_]+)/"', html)))
    return [b for b in found if b not in SKIP_BRANDS and b in MAKES]


def models_of(f: Fetcher, brand: str) -> list[str]:
    html = f.get(f"{BASE}/usedcar/brand-{brand}/") or ""
    return list(dict.fromkeys(re.findall(rf'href="(?:https://www\.goo-net\.com)?/usedcar/brand-{brand}/car-([A-Za-z0-9_\-]+)/"', html)))


def parse_cards(html: str) -> list[dict]:
    """Карточки страницы модели: номер, ссылка, год, пробег, объём, цена, фото — что есть в карточке."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for card in soup.select("div.search-card, div.section_body"):
        a = card.select_one('a[href*="/usedcar/spread/"]')
        if not a:
            continue
        m = re.search(r"/usedcar/spread/goo/\d+/(\d+)\.html", a.get("href", ""))
        if not m:
            continue
        text = nfkc(card.get_text(" ", strip=True))
        year = re.search(r"年式\s*(\d{4})", text) or re.search(r"(20\d{2}|19\d{2})\s*\([RH]\d+\)\s*年", text)
        km = re.search(r"走行(?:距離)?\s*([\d.,]+)\s*(万)?\s*km", text)
        cc = re.search(r"排気量\s*([\d,]+)\s*cc", text)
        img = card.select_one("img")
        src = (img.get("data-src") or img.get("src") or "") if img else ""
        out.append({
            "id": m.group(1),
            "url": BASE + a["href"] if a["href"].startswith("/") else a["href"],
            "year": int(year.group(1)) if year else None,
            "mileage_km": (round(float(km.group(1).replace(",", "")) * (10000 if km.group(2) else 1)) if km else None),
            "cc": int(cc.group(1).replace(",", "")) if cc else None,
            "image": src if "goo-net.com" in src else None,
            "card_text": text[:400],
        })
    return out


# ---------- страница объявления ----------

FUEL = [("プラグイン", "подключаемый гибрид"), ("ハイブリッド", "гибрид (бензин + электро)"), ("ディーゼル", "дизель"),
        ("軽油", "дизель"), ("電気", "электро"), ("EV", "электро"), ("LPG", "газ (LPG)"), ("ガソリン", "бензин")]
COLORS = [("パール", "белый перламутр"), ("ホワイト", "белый"), ("白", "белый"), ("ブラック", "чёрный"), ("黒", "чёрный"),
          ("シルバー", "серебристый"), ("銀", "серебристый"), ("グレー", "серый"), ("ガンメタ", "тёмно-серый"),
          ("レッド", "красный"), ("赤", "красный"), ("ブルー", "синий"), ("青", "синий"), ("紺", "тёмно-синий"),
          ("ブラウン", "коричневый"), ("ベージュ", "бежевый"), ("グリーン", "зелёный"), ("緑", "зелёный"),
          ("イエロー", "жёлтый"), ("オレンジ", "оранжевый"), ("ゴールド", "золотистый"), ("パープル", "фиолетовый"),
          ("ピンク", "розовый")]
KATAKANA_WORDS = {"ハイブリッド": "Hybrid", "ターボ": "Turbo", "プレミアム": "Premium", "スポーツ": "Sport",
                  "ラグジュアリー": "Luxury", "エディション": "Edition", "パッケージ": "Package", "ブラック": "Black",
                  "ホワイト": "White", "リミテッド": "Limited", "カスタム": "Custom", "ディーゼル": "Diesel"}


def _after(lines, label, n=1):
    for i, ln in enumerate(lines):
        if ln == label and i + n < len(lines):
            return lines[i + n]
    return None


def parse_detail(html: str) -> dict:
    all_lines = [nfkc(x).replace("\u2212", "-") for x in text_lines(html)]
    text = "\n".join(all_lines)
    # Характеристики — после заголовка «基本仕様»: выше те же слова есть в блоке диагностики
    start = next((i for i, ln in enumerate(all_lines) if ln == "基本仕様"), 0)
    lines = all_lines[start:]
    d = {}
    y = _after(lines, "年式(初度登録)")
    if y and re.match(r"\d{4}", y):
        d["year"] = int(y[:4])
    cc = _after(lines, "排気量")
    if cc and re.match(r"[\d,]+\s*cc", cc):
        d["cc"] = int(re.sub(r"\D", "", cc))
    power = re.search(r"最高出力\n(\d{2,4})\s*ps", text, re.I)
    if power:
        d["hp"] = int(power.group(1))
    price = re.search(r"車両本体価格\n\(税込\)\n([\d.,]+)\n万円", text)
    if price:
        d["price_jpy"] = round(float(price.group(1).replace(",", "")) * 10000)
    km = re.search(r"走行距離\n([\d.,]+)\n?(万)?km", text)
    if km:
        d["mileage_km"] = round(float(km.group(1).replace(",", "")) * (10000 if km.group(2) else 1))
    fuel = _after(lines, "燃料") or ""
    d["fuel"] = next((ru for jp, ru in FUEL if jp in fuel), None)
    drive = (_after(lines, "駆動形式") or "") + " " + (_after(lines, "駆動方式") or "")
    d["drive"] = ("полный" if re.search(r"4WD|AWD|フルタイム|パートタイム", drive) else
                  "задний" if re.search(r"\bFR\b|\bMR\b|\bRR\b", drive) else "передний" if "FF" in drive else None)
    trans = _after(lines, "ミッション") or ""
    d["trans"] = ("вариатор" if "CVT" in trans else "механика" if "MT" in trans else "автомат" if "AT" in trans else None)
    d["turbo"] = bool(re.search(r"ターボ|スーパーチャージャー", _after(lines, "過給器") or ""))
    color = _after(lines, "車体色") or ""
    d["color"] = next((ru for jp, ru in COLORS if jp in color), None)
    seats = re.search(r"(\d+)", _after(lines, "乗車定員") or "")
    d["seats"] = int(seats.group(1)) if seats else None
    gen = re.search(r"モデル\((.+?)\)", text)
    d["generation"] = re.sub(r"^\S+\s+", "", gen.group(1)).replace("系", " series").strip() if gen else None
    grade = re.search(r"グレード\((.+?)\)", text)
    if grade:
        g = re.sub(r"^\S+\s+", "", grade.group(1))
        for jp, en in KATAKANA_WORDS.items():
            g = g.replace(jp, f" {en} ")
        g = " ".join(w for w in g.split() if not re.search(r"[぀-ヿ一-鿿]", w))
        d["grade"] = g or None
    photos = re.findall(r'https?://picture1\.goo-net\.com/[^"\'\s]+/J/[^"\'\s]+\.jpg', html)
    d["photos"] = list(dict.fromkeys(photos))[:3]
    return d


def power_class(d: dict) -> str | None:
    if d.get("fuel") == "электро":
        return "gt160"          # электромобили — в группе «любой мощности»
    if d.get("hp"):
        return "le160" if d["hp"] <= 160 else "gt160"
    return None                 # мощность не указана — не берём


# ---------- выбор ----------

def year_band(year):
    return next((name for name, lo, hi, _ in YEAR_BANDS if year and lo <= year <= hi), None)


def pick(groups: dict, total: int, resolve, on_site: dict | None = None) -> list[dict]:
    """Как у Кореи: по машине на модель (до 160 л.с., если есть), затем добор по кругу по
    моделям — «до 160» до 75%, мощных до 25%, внутри — по долям лет.

    Модели, которых на сайте меньше (on_site — сколько машин модели уже есть), идут первыми:
    сначала появляются модели, которых ещё нет, потом добираются редкие."""
    on_site = on_site or {}
    order = sorted(groups, key=lambda k: (on_site.get(k, 0), random.random()))
    groups = {k: groups[k] for k in order}
    picked, used, count, per_group = [], set(), {}, {}
    rank = {name: i for i, (name, *_) in enumerate(YEAR_BANDS)}
    quota = {"le160": round(total * SHARE_160), "gt160": total - round(total * SHARE_160)}

    def power(car, key):
        if car.get("power") is None and not car.get("_resolved") and per_group.get(key, 0) < RESOLVE_PER_MODEL * 3:
            car["_resolved"] = True
            per_group[key] = per_group.get(key, 0) + 1
            car["power"] = resolve(car)
        return car.get("power")

    taken = {}

    def take(car, key):
        taken[key] = taken.get(key, 0) + 1
        picked.append(car)
        used.add(car["id"])
        k = (car["power"], year_band(car["year"]))
        count[k] = count.get(k, 0) + 1

    def total_of(kind):
        return sum(v for (k, _), v in count.items() if k == kind)

    for key, cars in groups.items():
        cars.sort(key=lambda c: rank.get(year_band(c["year"]), 9))
    for key, cars in groups.items():
        # По машине — только моделям, которых на сайте ещё нет, и в пределах долей
        if on_site.get(key) or len(picked) >= total:
            continue
        best = None
        if total_of("le160") < quota["le160"]:
            best = next((c for c in cars[:RESOLVE_PER_MODEL] if power(c, key) == "le160"), None)
        if not best and total_of("gt160") < quota["gt160"]:
            best = next((c for c in cars if c.get("power") == "gt160"), None)
        if best:
            take(best, key)
    covered = len(picked)

    def fill(kind, band, need):
        pos = {k: 0 for k in groups}
        progress = True
        while need() and progress:
            progress = False
            for key, cars in groups.items():
                if not need():
                    break
                if taken.get(key, 0) >= PER_MODEL_RUN:
                    continue
                i = pos[key]
                while i < len(cars):
                    c = cars[i]
                    i += 1
                    if c["id"] in used or (band and year_band(c["year"]) != band):
                        continue
                    if power(c, key) == kind:
                        take(c, key)
                        progress = True
                        break
                pos[key] = i

    def fill_kind(kind, target):
        for name, _, _, w in YEAR_BANDS:
            want = round(target * w)
            fill(kind, name, lambda: count.get((kind, name), 0) < want and total_of(kind) < target)
        fill(kind, None, lambda: total_of(kind) < target)

    ratio = (1 - SHARE_160) / SHARE_160
    fill_kind("le160", max(round(total * SHARE_160), math.ceil(total_of("gt160") / ratio)))
    fill_kind("gt160", min(total - total_of("le160"), math.floor(total_of("le160") * ratio)))
    years = {name: sum(v for (_, b), v in count.items() if b == name) for name, *_ in YEAR_BANDS}
    log(f"Выбрано: новых моделей {covered} (на сайте нет {sum(1 for k in groups if not on_site.get(k))} из {len(groups)}), машин {len(picked)} — до 160 л.с. {total_of('le160')}, "
        f"мощнее {total_of('gt160')}; по годам: " + ", ".join(f"{k} — {v}" for k, v in years.items()))
    return picked


# ---------- bn-auto ----------

def fetch_known() -> dict:
    if not BN_AUTO_URL or not BN_AUTO_IMPORT_TOKEN:
        return {}
    try:
        resp = httpx.get(f"{BN_AUTO_URL}/api/live-listings/known", params={"source": "goonet", "all": "1"},
                         headers={"Authorization": f"Bearer {BN_AUTO_IMPORT_TOKEN}"}, timeout=60)
        resp.raise_for_status()
        items = {str(i["id"]): i for i in resp.json().get("items") or []}
        good = sum(1 for i in items.values() if i.get("complete"))
        log(f"На сайте: {len(items)}, из них с полной информацией {good}, "
            f"в каталоге {sum(1 for i in items.values() if i.get('published'))}")
        return items
    except Exception as error:
        log(f"Список машин с сайта не получен ({error})")
        return {}


def to_listing(car: dict, f: Fetcher) -> dict:
    d = car.get("detail") or {}
    spec = {
        "Лот": car["id"],
        "Выпуск": str(d.get("year") or car.get("year") or ""),
        "Поколение": d.get("generation"),
        "Комплектация": d.get("grade"),
        "Трансмиссия": d.get("trans"),
        "Привод": d.get("drive"),
        "Мощность, л.с.": str(d["hp"]) if d.get("hp") else None,
        "Объём, см³": str(d.get("cc") or car.get("cc") or "") or None,
        "Турбо": "да" if d.get("turbo") else None,
        "Пробег": f"{d.get('mileage_km') or car.get('mileage_km'):,} км".replace(",", " ")
                  if (d.get("mileage_km") or car.get("mileage_km")) is not None else None,
        "Топливо": d.get("fuel"),
        "Цвет": d.get("color"),
        "Мест": str(d["seats"]) if d.get("seats") else None,
        "Руль": "правый",
    }
    photo = None
    for url in d.get("photos") or []:
        photo = f.photo(url)
        if photo:
            break
    if not photo and car.get("image"):
        photo = f.photo(car["image"].replace("/Q/", "/J/")) or f.photo(car["image"])
    return {
        "external_id": car["id"], "make": car["make"], "model": car["model"],
        "title": f"{car['make']} {car['model']}", "year": d.get("year") or car.get("year"),
        "mileage_km": d.get("mileage_km") or car.get("mileage_km"),
        "price_value": d.get("price_jpy"), "photo_url": photo,
        "spec": {k: v for k, v in spec.items() if v}, "source_url": car["url"],
    }


def push(listings: list[dict]):
    if not listings:
        return
    if not BN_AUTO_URL or not BN_AUTO_IMPORT_TOKEN:
        log(f"BN_AUTO_URL / BN_AUTO_IMPORT_TOKEN не заданы — {len(listings)} машин не отправлены")
        return
    light = [x for x in listings if "spec" not in x]
    full = [x for x in listings if "spec" in x]
    for batch in [light[i:i + 200] for i in range(0, len(light), 200)] + [full[i:i + 10] for i in range(0, len(full), 10)]:
        resp = httpx.post(f"{BN_AUTO_URL}/api/live-listings/import", json={"source": "goonet", "listings": batch},
                          headers={"Authorization": f"Bearer {BN_AUTO_IMPORT_TOKEN}"}, timeout=90)
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if resp.status_code >= 400:
            log(f"Отправка на сайт не удалась: HTTP {resp.status_code} {data}")
            resp.raise_for_status()
        log(f"  на сайт: {data.get('stats')}, пропущено {data.get('skipped', 0)}")


# ---------- прогон ----------

def scan(f: Fetcher, known: dict) -> tuple[dict, list]:
    """({(марка, модель): [новые машины с MIN_YEAR года]}, [машины с сайта, встреченные в обходе]) —
    первые страницы всех моделей всех марок. Машины с сайта с полной информацией не выбираются
    заново — им только отметка «ещё в продаже»; неполные — кандидаты на обновление."""
    started = time.time()
    deadline = started + SCAN_MINUTES * 60
    bl = brands(f)
    log(f"Марок: {len(bl)} — {', '.join(bl)}")
    jobs = []
    for b in bl:
        ms = models_of(f, b)
        log(f"  {MAKES[b]}: моделей {len(ms)}")
        jobs += [(b, m) for m in ms]
    if MAX_MODELS:
        # Проверка: несколько моделей разных марок, а не все модели первой марки
        by_brand = {}
        for b, m in jobs:
            by_brand.setdefault(b, []).append((b, m))
        jobs = [x for group in zip(*[v[:MAX_MODELS] for v in by_brand.values()]) for x in group][:MAX_MODELS]
        log(f"Проверка: только {len(jobs)} моделей")
    groups, touched, shown = {}, [], False
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = {pool.submit(f.get, f"{BASE}/usedcar/brand-{b}/car-{m}/"): (b, m) for b, m in jobs}
        for n, fut in enumerate(as_completed(futures), 1):
            b, m = futures[fut]
            cards = parse_cards(fut.result() or "")
            if cards and not shown:
                log(f"Пример карточки: {cards[0]}")
                shown = True
            for c in cards:
                info = known.get(c["id"])
                if info and info.get("complete"):
                    touched.append(c)
                    continue
                if info and info.get("year"):
                    c["year"] = c.get("year") or int(info["year"])
                if c["year"] and c["year"] < MIN_YEAR:
                    continue
                c.update(make=MAKES[b], model=model_name(m))
                if info and info.get("hp"):
                    hp = int(re.sub(r"\D", "", str(info["hp"])) or 0)
                    c["power"] = "le160" if 0 < hp <= 160 else "gt160" if hp else None
                groups.setdefault((b, m), []).append(c)
            if n % 100 == 0:
                log(f"  моделей просмотрено {n}/{len(jobs)}, с машинами {len(groups)}, {(time.time() - started) / 60:.0f} мин")
            if time.time() > deadline:
                log(f"Время обхода вышло: просмотрено {n} из {len(jobs)}")
                for x in futures:
                    x.cancel()
                break
    log(f"Обход: моделей с новыми машинами {len(groups)}, новых машин {sum(map(len, groups.values()))}, "
        f"машин с сайта встречено {len(touched)}, страниц {f.count}")
    return groups, touched


def run_size(known: dict) -> int:
    """Сколько новых машин добавить: вручную (GOONET_TOTAL); до заполнения каталога (FILL_TARGET) —
    по FILL_PER_RUN за прогон; потом в дни обновления (первый прогон дня) — UPDATE_NEW порциями
    по UPDATE_BATCH с паузой UPDATE_PAUSE; 0 — сегодня ничего не нужно."""
    global BATCH, BATCH_PAUSE
    if TOTAL:
        return TOTAL
    good = sum(1 for i in known.values() if i.get("complete") and i.get("published"))
    if good < FILL_TARGET:
        n = min(FILL_PER_RUN, FILL_TARGET - good)
        log(f"Заполнение каталога: на сайте {good} из {FILL_TARGET} — добавим {n}")
        # Каталог ещё не заполнен — workflow сразу запустит следующий прогон (без остановки)
        open("continue_fill", "w").close()
        return n
    now = time.gmtime()
    if now.tm_wday in UPDATE_DAYS and now.tm_hour < 8:
        BATCH, BATCH_PAUSE = UPDATE_BATCH, UPDATE_PAUSE
        log(f"Каталог заполнен ({good}) — обновление: до {UPDATE_NEW} новых, порции по {BATCH} с паузой {BATCH_PAUSE:g} мин")
        return UPDATE_NEW
    log(f"Каталог заполнен ({good}), сейчас не время обновления — прогон окончен")
    return 0


def complete(listing: dict) -> bool:
    """Полная информация: фото, цена, год и то, по чему считается таможня (объём и мощность)."""
    spec = listing.get("spec") or {}
    ev = spec.get("Топливо") == "электро"
    return bool(listing.get("photo_url") and listing.get("price_value") and listing.get("year")
                and (spec.get("Мощность, л.с.") or ev) and (spec.get("Объём, см³") or ev))


def verify(f: Fetcher, known: dict, seen: set) -> list[dict]:
    """Машины с сайта, не встреченные в обходе: давно не обновлявшиеся и неполные открываем
    заново. Жива — отметка «ещё в продаже» (а неполную — дополняем); снята — не трогаем,
    через 30 дней сайт её скроет."""
    todo = [(k, i) for k, i in known.items() if k not in seen and i.get("url")
            and (not i.get("complete") or (i.get("seen_days") or 0) >= 7)]
    todo.sort(key=lambda x: (x[1].get("complete", False), -(x[1].get("seen_days") or 0)))
    out, alive = [], 0
    for key, info in todo[:VERIFY_LIMIT]:
        html = f.get(info["url"])
        d = parse_detail(html) if html else {}
        if not d.get("price_jpy"):
            continue
        alive += 1
        car = {"id": key, "url": info["url"], "make": info.get("make"), "model": info.get("model"),
               "year": d.get("year") or info.get("year"), "detail": d}
        if info.get("complete"):
            out.append({"external_id": key, "source_url": info["url"], "price_value": d["price_jpy"],
                        "mileage_km": d.get("mileage_km")})
        elif car["make"] and car["model"]:
            listing = to_listing(car, f)
            if complete(listing):
                out.append(listing)
    log(f"Проверено машин с сайта, не встреченных в обходе: {min(len(todo), VERIFY_LIMIT)} из {len(todo)}, "
        f"в продаже {alive}")
    return out


def main():
    f = Fetcher()
    known = fetch_known()
    total = run_size(known)
    if not total:
        return
    groups, touched = scan(f, known)
    f.human = True
    seen = {c["id"] for c in touched} | {c["id"] for cars in groups.values() for c in cars}
    # Отметка «ещё в продаже» машинам с сайта, встреченным в обходе
    push([{"external_id": c["id"], "source_url": c["url"], "mileage_km": c.get("mileage_km")} for c in touched])
    push(verify(f, known, seen))
    if not total:
        return

    def resolve(car):
        """Страница объявления: мощность (最高出力), год, цена, характеристики."""
        html = f.get(car["url"])
        if not html:
            return None
        d = parse_detail(html)
        car["detail"] = d
        car["year"] = d.get("year") or car["year"]
        if car["year"] and car["year"] < MIN_YEAR:
            return None
        return power_class(d)

    on_site = {}
    by_name = {}
    for info in known.values():
        if info.get("complete") and info.get("published"):
            by_name[(info.get("make"), info.get("model"))] = by_name.get((info.get("make"), info.get("model")), 0) + 1
    for (b, m) in groups:
        on_site[(b, m)] = by_name.get((MAKES[b], model_name(m)), 0)
    cars = pick(groups, total, resolve, on_site)
    chunks = [cars[i:i + BATCH] for i in range(0, len(cars), BATCH)]
    sent = rejected = 0
    for n, chunk in enumerate(chunks, 1):
        log(f"=== Порция {n}/{len(chunks)} ===")
        listings = []
        for car in chunk:
            if "detail" not in car:
                resolve(car)
            listing = to_listing(car, f)
            if complete(listing):
                listings.append(listing)
            else:
                rejected += 1
        push(listings)
        sent += len(listings)
        if n < len(chunks):
            pause = BATCH_PAUSE * random.uniform(0.7, 1.3)
            log(f"Пауза {pause:.1f} мин")
            time.sleep(pause * 60)
    log(f"Готово: отправлено {sent}, отсеяно без фото/цены/мощности {rejected}, запросов к goo-net {f.count}")
    with open("goonet_batch.json", "w", encoding="utf-8") as out:
        json.dump([{k: v for k, v in c.items() if k != "detail"} for c in cars], out, ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
