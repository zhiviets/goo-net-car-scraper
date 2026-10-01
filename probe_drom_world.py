"""Есть ли на drom.ru статистика продаж машин Кореи и Китая (как «Аукционы Японии»)? Ничего не меняет."""
import re

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_context(user_agent=UA, locale="ru-RU").new_page()
    for url in ("https://www.drom.ru/world/", "https://www.drom.ru/world/korea/", "https://www.drom.ru/world/china/",
                "https://www.drom.ru/world/korea/kia/", "https://www.drom.ru/world/china/haval/",
                "https://www.drom.ru/world/japan/toyota/prius/"):
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2500)
            html = page.content()
            text = page.inner_text("body")
        except Exception as e:
            print(f"== {url}: ошибка {e!r}")
            continue
        links = sorted(set(re.findall(r'href="(https://www\.drom\.ru/world/[^"?#]*|/world/[^"?#]*)"', html)))
        print(f"== {url}: HTTP {resp.status if resp else '?'}, итоговый адрес {page.url}, заголовок «{page.title()}»")
        print("   ссылки world: " + ", ".join(links[:40]))
        snippet = " ".join(text.split())[:700]
        print("   текст: " + snippet)
    browser.close()
