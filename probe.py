"""
Проверка goo-net.com с сервера GitHub Actions: пускает ли, разбираются ли
карточки списка (src/goonet.py), что есть на странице объявления (год, пробег,
объём, привод, КПП, код кузова 型式) и как устроены ссылки на марки и модели.
Всё печатается в лог; ничего никуда не отправляет.
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
LABELS = ["年式", "走行距離", "排気量", "駆動", "ミッション", "型式", "燃料", "車検", "修復歴", "馬力", "エンジン",
          "ボディタイプ", "色", "グレード", "支払総額", "車両本体価格", "ハンドル", "乗車定員", "ドア"]


def lines_of(html):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return [ln.strip() for ln in soup.get_text("\n").splitlines() if ln.strip()]


async def main():
    async with httpx.AsyncClient(headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"}, timeout=40) as client:
        for url in ("https://www.goo-net.com/usedcar/", "https://www.goo-net.com/usedcar/brand-TOYOTA/"):
            html = await fetch_page(client, url)
            print(f"\n######## {url}: {len(html or '')} символов")
            if not html:
                continue
            print("title:", re.findall(r"<title>(.*?)</title>", html, re.S)[:1])
            cards = parse_page(html)
            print(f"карточек: {len(cards)}")
            for c in cards[:3]:
                print("  ", c)
            links = re.findall(r'href="(/usedcar/[^"#?]+)"', html)
            pats = Counter(re.sub(r"[A-Z0-9_]{2,}", "X", l) for l in links)
            print("виды ссылок /usedcar/:", pats.most_common(25))
            print("примеры brand/car:", [l for l in dict.fromkeys(links) if "brand-" in l][:15])
            if cards and cards[0].get("detailUrl"):
                d = await fetch_page(client, cards[0]["detailUrl"])
                print(f"\n=== Объявление {cards[0]['detailUrl']}: {len(d or '')} символов")
                if d:
                    ls = lines_of(d)
                    for i, ln in enumerate(ls):
                        if any(ln.startswith(lab) for lab in LABELS) and len(ln) < 40:
                            print(f"   {ln} → {' | '.join(ls[i + 1:i + 3])}")
                    print("--- начало текста ---\n", "\n".join(ls[:120]))
                    imgs = re.findall(r'https?://picture1\.goo-net\.com/[^"\']+\.(?:jpg|jpeg|webp)', d)
                    print("фото:", list(dict.fromkeys(imgs))[:6])
                break


if __name__ == "__main__":
    asyncio.run(main())
