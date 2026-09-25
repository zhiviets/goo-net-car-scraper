"""Сколько машин на сайте по странам (для проверки заполнения). Ничего не меняет."""

import collections
import json
import os
import re

import httpx

URL = os.environ["BN_AUTO_URL"].rstrip("/")
TOKEN = os.environ["BN_AUTO_IMPORT_TOKEN"]

for source in ("goonet", "encar", "che168"):
    r = httpx.get(f"{URL}/api/live-listings/known", params={"source": source, "all": "1"},
                  headers={"Authorization": f"Bearer {TOKEN}"}, timeout=120)
    items = r.json().get("items") or []
    pub = [i for i in items if i.get("published")]
    print(f"{source}: всего {len(items)}, опубликовано {len(pub)}, полных опубликованных "
          f"{sum(1 for i in pub if i.get('complete'))}, с комплектацией {sum(1 for i in items if i.get('has_options'))}, "
          f"обновлены сегодня {sum(1 for i in items if (i.get('seen_days') or 0) == 0)}")

    ok = [i for i in pub if i.get("complete")]
    bands = [("2022–2024", 2022, 2024), ("2025–2026", 2025, 2026), ("2017–2021", 2017, 2021), ("2010–2016", 2010, 2016)]
    years = {name: sum(1 for i in ok if i.get("year") and lo <= int(i["year"]) <= hi) for name, lo, hi in bands}
    hp = [i.get("power") or int(re.sub(r"\D", "", str(i.get("hp") or "")) or 0) for i in ok]
    le = sum(1 for h, i in zip(hp, ok) if 0 < h <= 160 and not i.get("electric") and "электро" not in (i.get("text") or ""))
    n = max(len(ok), 1)
    print("   по годам: " + ", ".join(f"{k} — {v} ({v * 100 // n}%)" for k, v in years.items())
          + f", прочие {len(ok) - sum(years.values())}; до 160 л.с. {le} ({le * 100 // n}%), мощность не указана {hp.count(0)}")

    bad = [i for i in pub if not i.get("complete")]
    for i in bad[:12]:
        print(f"   неполная: {i.get('id')} {i.get('make')} {i.get('model')} {i.get('year')} cc={i.get('cc')} hp={i.get('hp')} "
              f"фото {i.get('photo_kb')} КБ, точная мощность {i.get('exact_power')}, «{(i.get('text') or '')[:60]}»")

    # Модели без точной мощности (мощность только оценена) — для сопоставления с drom.ru
    rough = collections.Counter(f"{i.get('make')}|{i.get('model')}" for i in ok if not i.get("exact_power"))
    print(f"   без точной мощности {sum(rough.values())}: " + json.dumps(dict(rough.most_common()), ensure_ascii=False))
