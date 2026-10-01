"""Состав каталога по странам: сколько разных моделей и моделей-лет, сколько машин на модель. Ничего не меняет."""
import collections
import os

import httpx

URL = os.environ["BN_AUTO_URL"].rstrip("/")
TOKEN = os.environ["BN_AUTO_IMPORT_TOKEN"]
for source in ("goonet", "encar", "che168"):
    items = httpx.get(f"{URL}/api/live-listings/known", params={"source": source, "all": "1"},
                      headers={"Authorization": f"Bearer {TOKEN}"}, timeout=120).json()["items"]
    pub = [i for i in items if i.get("published") and (i.get("complete") or i.get("no_auction"))]
    models = collections.Counter(f"{i['make']} {i['model']}" for i in pub)
    my = collections.Counter(f"{i['make']} {i['model']} {i['year']}" for i in pub)
    per = collections.Counter(min(v, 21) for v in models.values())
    print(f"== {source}: машин {len(pub)}, моделей {len(models)}, моделей-лет {len(my)}, марок {len(set(i['make'] for i in pub))}")
    print("   машин на модель (модели): " + ", ".join(f"{k if k < 21 else '21+'} — {v}" for k, v in sorted(per.items())))
    print("   больше всего: " + ", ".join(f"{k} {v}" for k, v in models.most_common(25)))
    print("   больше всего одной модели одного года: " + ", ".join(f"{k} {v}" for k, v in my.most_common(15)))
    print(f"   со шкалой {sum(1 for i in pub if i.get('has_gauge'))}")
