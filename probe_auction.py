"""
Разовая проверка: статистика цен японских аукционов на drom.ru — где ссылка на странице модели,
как устроен адрес, какие данные на странице (годы, пробег, цены) и какие JSON грузит страница.
Ничего не отправляет.
"""
import json
import re

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
MODELS = ["honda/fit", "toyota/prius", "toyota/aqua", "honda/n-box", "bmw/3-series"]


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, locale="ru-RU")
        page = ctx.new_page()
        for m in MODELS:
            url = f"https://www.drom.ru/catalog/{m}/"
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(3000)
            links = page.eval_on_selector_all("a", "els => els.map(e => [e.innerText.trim(), e.href])")
            auc = [(t, h) for t, h in links if re.search(r"аукцион", t, re.I) or re.search(r"auc|stat", h or "", re.I)]
            print(f"\n######## {m}: ссылок про аукционы {len(auc)}")
            for t, h in auc[:10]:
                print("   ", t[:80].replace("\n", " "), "→", h)
            target = next((h for t, h in auc if "аукцион" in t.lower()), None)
            if not target:
                continue
            responses = []
            page.on("response", lambda r: responses.append(r))
            page.goto(target, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(5000)
            print("  страница:", page.url, "|", page.title())
            text = page.inner_text("body")
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            print("  строк:", len(lines))
            for ln in lines[:220]:
                print("   |", ln[:150])
            forms = page.eval_on_selector_all("select, input", "els => els.map(e => [e.name, e.id, (e.options ? [...e.options].slice(0, 8).map(o => o.value + ':' + o.text) : e.value)])")
            print("  поля:", json.dumps(forms, ensure_ascii=False)[:1500])
            for r in responses:
                ct = r.headers.get("content-type", "")
                if "json" in ct and "drom" in r.url:
                    try:
                        body = r.text()
                    except Exception:
                        continue
                    print("  JSON:", r.url[:200], body[:600].replace("\n", " "))
            page.remove_listener("response", responses.append) if False else None
        browser.close()


if __name__ == "__main__":
    main()
