"""
Проверка goo-net.com с сервера GitHub Actions (2): страницы марки и модели (ссылки,
карточки, пагинация) и таблица характеристик объявления — ищем код кузова (型式),
поколение (モデル), привод, КПП, турбо. Всё печатается в лог.
"""

import asyncio
import re
import sys
from collections import Counter

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, "src")
from goonet import fetch_page, parse_page  # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")


def lines_of(html):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return [ln.strip() for ln in soup.get_text("\n").splitlines() if ln.strip()]


def link_patterns(html, prefix="/usedcar/"):
    links = re.findall(rf'href="(?:https://www\.goo-net\.com)?({re.escape(prefix)}[^"#?]+)"', html)
    return links, Counter(re.sub(r"[A-Z0-9_]{2,}", "X", l) for l in links)


async def main():
    async with httpx.AsyncClient(headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"}, timeout=40) as client:
        top = await fetch_page(client, "https://www.goo-net.com/")
        links, pats = link_patterns(top or "", "/")
        print("главная — виды ссылок:", [p for p in pats.most_common(40) if "usedcar" in p[0] or "catalog" in p[0]])
        print("примеры марок:", [l for l in dict.fromkeys(links) if re.search(r"brand|maker", l)][:20])

        for url in ("https://www.goo-net.com/usedcar/brand-TOYOTA/", "https://www.goo-net.com/usedcar/brand-TOYOTA/car-NOAH/"):
            html = await fetch_page(client, url)
            print(f"\n######## {url}: {len(html or '')} символов, title {re.findall(r'<title>(.*?)</title>', html or '', re.S)[:1]}")
            if not html:
                continue
            cards = parse_page(html)
            print(f"карточек: {len(cards)}; первая: {cards[0] if cards else None}")
            links, pats = link_patterns(html)
            print("виды ссылок:", pats.most_common(30))
            print("ссылки на модели:", [l for l in dict.fromkeys(links) if "car-" in l][:25])
            print("всего машин (件):", re.findall(r"([\d,]+)\s*件", html)[:5])

        noah = await fetch_page(client, "https://www.goo-net.com/usedcar/brand-TOYOTA/car-NOAH/")
        cards = parse_page(noah or "") or parse_page(await fetch_page(client, "https://www.goo-net.com/usedcar/") or "")
        for c in cards[:2]:
            d = await fetch_page(client, c["detailUrl"])
            if not d:
                continue
            ls = lines_of(d)
            print(f"\n=== Объявление {c['detailUrl']}")
            try:
                i = next(k for k, ln in enumerate(ls) if ln.startswith("年式(初度登録)"))
                print("--- таблица характеристик ---\n", " | ".join(ls[max(0, i - 40): i + 120]))
            except StopIteration:
                print("таблицы «年式(初度登録)» нет")
            for k, ln in enumerate(ls):
                if "型式" in ln or "車台番号" in ln or "モデル（" in ln or "過給" in ln:
                    print(f"   [{ln}] → {' | '.join(ls[k + 1:k + 3])}")
            print("型式 в HTML:", re.findall(r".{0,80}型式.{0,120}", d)[:5])


if __name__ == "__main__":
    asyncio.run(main())
