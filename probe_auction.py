"""
Разовая проверка чтения статистики японских аукционов drom.ru (drom_specs.auction_lots):
фильтр по году в адресе, вторая страница, сколько лотов и какие. Ничего не отправляет.
"""
from collections import Counter

from japan_scraper import open_drom

CASES = [("Honda", "Fit", 2020), ("Toyota", "Prius", 2019), ("Honda", "N-BOX", 2022), ("BMW", "3-SERIES", 2019),
         ("Toyota", "Aqua", 2015), ("Daihatsu", "Tanto", 2012)]


def main():
    drom, close = open_drom()
    try:
        for make, model, year in CASES:
            lots = drom.auction_lots(make, model, year, pages=3)
            if lots is None:
                print(f"{make} {model} {year}: нет данных")
                continue
            prices = sorted(x["price_jpy"] for x in lots if x.get("price_jpy"))
            print(f"\n{make} {model} {year}: лотов {len(lots)}, годы {dict(Counter(x['year'] for x in lots))}, "
                  f"объёмы {dict(Counter(x.get('cc') for x in lots))}, оценки {dict(Counter(x.get('score') for x in lots))}")
            print("   цены:", prices[:5], "…", prices[-5:])
            for x in lots[:3]:
                print("   ", x)
        print("\nстраниц drom.ru:", drom.requests)
    finally:
        close()


if __name__ == "__main__":
    main()
