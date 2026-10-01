"""Почему у машин нет шкалы: возраст статистики, группа, примеры. Ничего не меняет."""
import collections
import os

import httpx

URL = os.environ["BN_AUTO_URL"].rstrip("/")
TOKEN = os.environ["BN_AUTO_IMPORT_TOKEN"]
for source in ("encar", "che168"):
    items = httpx.get(f"{URL}/api/live-listings/known", params={"source": source, "all": "1"},
                      headers={"Authorization": f"Bearer {TOKEN}"}, timeout=120).json()["items"]
    pub = [i for i in items if i.get("published")]
    days = collections.Counter("нет" if i.get("stats_days") is None else min(i["stats_days"], 30) for i in pub)
    print(f"== {source}: опубликовано {len(pub)}, со шкалой {sum(1 for i in pub if i.get('has_gauge'))}, "
          f"с ключом {sum(1 for i in pub if i.get('stats_key'))}; возраст статистики: {dict(sorted(days.items(), key=str))}")
    fresh_no = [i for i in pub if i.get("stats_days") == 0 and not i.get("has_gauge")]
    print(f"   статистика сегодня, а шкалы нет: {len(fresh_no)}")
    for i in fresh_no[:8]:
        print(f"   {i['id']} {i.get('make')} {i.get('model')} {i.get('year')} цена {i.get('price')} ключ {i.get('stats_key')}")
