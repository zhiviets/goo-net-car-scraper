"""Почему у японских машин нет аукционной цены (по auction_issue из /known). Ничего не меняет."""
import collections
import os

import httpx

URL = os.environ["BN_AUTO_URL"].rstrip("/")
TOKEN = os.environ["BN_AUTO_IMPORT_TOKEN"]
items = httpx.get(f"{URL}/api/live-listings/known", params={"source": "goonet", "all": "1"},
                  headers={"Authorization": f"Bearer {TOKEN}"}, timeout=180).json()["items"]
pub = [i for i in items if i.get("published")]
no = [i for i in pub if i.get("no_auction")]
kinds = collections.Counter((i.get("auction_issue") or "?").split(" ")[0] for i in no)
print(f"опубликовано {len(pub)}, без аукционной цены {len(no)}: {dict(kinds)}")
below = above = 0
for i in no:
    parts = (i.get("auction_issue") or "").split(" ")
    if parts[0] == "out_of_range" and len(parts) == 3:
        price = int(parts[1]); lo, hi = (int(x) for x in parts[2].split("-"))
        below += price < lo
        above += price > hi
print(f"вне шкалы: ниже нижней границы {below}, выше верхней {above}")
for kind in kinds:
    print(f"-- {kind}:")
    for i in [x for x in no if (x.get("auction_issue") or "?").startswith(kind)][:8]:
        print(f"   {i['id']} {i.get('make')} {i.get('model')} {i.get('year')} цена {i.get('price')} — {i.get('auction_issue')}, "
              f"видели {i.get('seen_days')} дн. назад")
