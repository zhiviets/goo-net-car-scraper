"""
Разовая проверка строк электромобиля на странице комплектации drom.ru (drom_specs.parse_trim):
названия строк (30-минутная мощность, мощность электромотора, запас хода, ёмкость батареи) и что из них
разобралось, плюс подбор drom.power для BYD Song Plus EV. Ничего не отправляет.
"""
import json

import drom_specs
from japan_scraper import open_drom

PAGES = ["https://www.drom.ru/catalog/byd/song_plus/460214/"]


def main():
    drom, close = open_drom()
    try:
        for url in PAGES:
            got = drom._get(url)
            if not got:
                print(url, "— не открылась"); continue
            lines = drom_specs.text_lines(got[1])
            print(f"\n{url}: строк {len(lines)}")
            for i, ln in enumerate(lines):
                if any(w in ln.lower() for w in ("электр", "запас хода", "батаре", "зарядк", "30-минут", "мощност")):
                    print(f"   {ln!r} → {lines[i + 1] if i + 1 < len(lines) else ''!r}")
            print("   parse_trim:", json.dumps(drom_specs.parse_trim(got[1]), ensure_ascii=False))
        q = {"make": "BYD", "model": "Song PLUS", "market": "china", "year": 2023, "cc": None, "fuel": "electric",
             "drive": None, "trans": None, "trim": "EV 605KM"}
        found = drom.power(q)
        print("\npower():", {k: v for k, v in (found or {}).items() if k != "trim"}, (found or {}).get("trim", {}).get("name"))
        if found:
            print("tech():", json.dumps(drom.tech(found.get("trim")), ensure_ascii=False)[:1500])
        print("страниц drom.ru:", drom.requests)
    finally:
        close()


if __name__ == "__main__":
    main()
