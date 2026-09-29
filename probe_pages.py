"""
Разовая проверка списка goo-net: как устроены следующие страницы модели и фильтр по году.
Печатает ссылки пагинации и сколько карточек/годов на страницах. Ничего не отправляет.
"""
import re
from collections import Counter

from japan_scraper import BASE, Fetcher, parse_cards

MODELS = ["brand-TOYOTA/car-AQUA", "brand-HONDA/car-N_BOX", "brand-DAIHATSU/car-TANTO"]


def years(cards):
    return dict(sorted(Counter(c["year"] for c in cards).items()))


def main():
    f = Fetcher()
    for m in MODELS:
        url = f"{BASE}/usedcar/{m}/"
        html = f.get(url) or ""
        cards = parse_cards(html)
        print(f"\n#### {m}: карточек {len(cards)}, годы {years(cards)}")
        links = sorted(set(re.findall(r'href="([^"]*' + re.escape(m.split("/")[1]) + r'[^"]*)"', html)))
        print("ссылки модели:", [l for l in links if re.search(r"index|page|\d\.html|\?", l)][:40])
        forms = re.findall(r'<(?:select|input)[^>]*name="([^"]+)"', html)
        print("поля формы:", sorted(set(forms))[:60])
        for cand in [f"{url}index-2.html", f"{url}?page=2", f"{url}2/", f"{url}index.html?pg=2",
                     f"{url}?nenshiki_min=2022", f"{url}?year_min=2022", f"{url}?nenshiki_from=2022"]:
            h = f.get(cand) or ""
            c = parse_cards(h)
            print(f"  {cand}: {len(h)} симв., карточек {len(c)}, годы {years(c)}, первая {c[0]['id'] if c else None}")
        print("  первая карточка стр.1:", cards[0]["id"] if cards else None)


if __name__ == "__main__":
    main()
