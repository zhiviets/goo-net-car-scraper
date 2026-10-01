"""Как на странице статистики аукционов drom.ru записана дата продажи лота. Ничего не меняет."""
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_context(user_agent=UA, locale="ru-RU").new_page()
    for url in ("https://www.drom.ru/world/japan/toyota/prius/?yearFrom=2015&yearTo=2015",
                "https://www.drom.ru/world/japan/mitsuoka/viewt/page3/"):
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2500)
        lines = [ln.strip() for ln in page.inner_text("body").split("\n") if ln.strip()]
        idx = [i for i, ln in enumerate(lines) if ln.startswith("Лот ")]
        print(f"== {url}: лотов {len(idx)}")
        for i in idx[:3] + idx[-2:]:
            print("   " + " | ".join(lines[max(0, i - 3): i + 4]))
    browser.close()
