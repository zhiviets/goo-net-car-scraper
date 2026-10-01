"""Проверка аукционных цен Японии на сайте: аукционная цена против цены объявления goo-net,
сколько продаж в основе, выбросы. Ничего не меняет."""
import os
import statistics as st

import httpx

URL = os.environ["BN_AUTO_URL"].rstrip("/")
TOKEN = os.environ["BN_AUTO_IMPORT_TOKEN"]
items = httpx.get(f"{URL}/api/live-listings/known", params={"source": "goonet", "all": "1"},
                  headers={"Authorization": f"Bearer {TOKEN}"}, timeout=120).json()["items"]
cars = [i for i in items if i.get("auction") and i.get("price")]
print(f"Машин с аукционной ценой: {len(cars)} из {len(items)}")
r = sorted(i["auction"]["price"] / i["price"] for i in cars)
q = lambda p: r[round((len(r) - 1) * p)]
print(f"Аукционная / цена goo-net: медиана {q(.5):.2f}, 10% {q(.1):.2f}, 25% {q(.25):.2f}, 75% {q(.75):.2f}, 90% {q(.9):.2f}")
for lo, hi in ((0, .5), (.5, .7), (.7, .85), (.85, 1), (1, 1.15), (1.15, 9)):
    print(f"   {lo:.2f}–{hi:.2f}: {sum(1 for x in r if lo <= x < hi)}")
n = sorted(i["auction"]["n"] for i in cars)
print(f"Продаж в основе цены: медиана {n[len(n) // 2]}, меньше 6 — {sum(1 for x in n if x < 6)}, от 20 — {sum(1 for x in n if x >= 20)}")
spread = sorted(i["auction"]["hi"] / i["auction"]["lo"] for i in cars)
print(f"Разброс продаж (верхняя / нижняя): медиана {spread[len(spread) // 2]:.2f}, больше 2 раз — {sum(1 for x in spread if x > 2)}")
fmt = lambda i: (f"   {i['make']} {i['model']} {i['year']} {i.get('cc')} см³ {i.get('hp')} л.с.: goo-net {i['price']:,} ¥, "
                 f"аукцион {i['auction']['price']:,} ¥ (продаж {i['auction']['n']}, {i['auction']['lo']:,}–{i['auction']['hi']:,}, "
                 f"средняя {i['auction']['mid']:,}) — {i['auction']['price'] / i['price']:.2f}").replace(",", " ")
cars.sort(key=lambda i: i["auction"]["price"] / i["price"])
print("Самые дешёвые относительно goo-net:")
for i in cars[:12]:
    print(fmt(i))
print("Самые дорогие относительно goo-net:")
for i in cars[-12:]:
    print(fmt(i))
print("Случайные:")
for i in cars[len(cars) // 7::max(1, len(cars) // 7)][:8]:
    print(fmt(i))
