"""Сколько машин на сайте по странам (для проверки заполнения). Ничего не меняет."""

import os

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
