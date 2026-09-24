"""
Проверка goo-net.com (3): раздел оборудования на странице объявления — какие пункты
и как отмечено «есть / нет». Печатает текст и HTML вокруг «装備». Ничего не отправляет.
"""

import re

from japan_scraper import BASE, Fetcher, parse_cards, text_lines

MODELS = ["brand-TOYOTA/car-NOAH", "brand-HONDA/car-N_WGN", "brand-TOYOTA/car-HARRIER", "brand-LEXUS/car-RX"]


def main():
    f = Fetcher()
    for m in MODELS:
        html = f.get(f"{BASE}/usedcar/{m}/")
        cards = parse_cards(html or "")
        print(f"\n######## {m}: карточек {len(cards)}")
        for c in cards[:2]:
            d = f.get(c["url"])
            if not d:
                continue
            lines = text_lines(d)
            print(f"\n=== {c['url']} ({len(d)} символов)")
            idx = [i for i, ln in enumerate(lines) if "装備" in ln]
            print("строки с «装備»:", [lines[i] for i in idx][:20])
            for i in idx[:4]:
                print(f"--- текст после «{lines[i]}» ---")
                print(" | ".join(lines[i:i + 90]))
            for mt in list(re.finditer(r"装備", d))[:3]:
                print("--- HTML ---")
                print(d[max(0, mt.start() - 300): mt.start() + 2500].replace("\n", " "))
            break


if __name__ == "__main__":
    main()
