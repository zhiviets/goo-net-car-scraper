"""
Проверка подбора мощности с drom.ru на настоящих объявлениях goo-net: берёт по несколько
машин популярных моделей, ищет комплектацию на drom.ru так же, как основной сборщик,
и сравнивает с мощностью из объявления (где она есть). Печатает каждую машину и итог:
сколько найдено, сколько совпало, почему не найдено. Ничего не отправляет на сайт.
"""

import re
import sys
from collections import Counter

from japan_scraper import (BASE, MAKES, Fetcher, drom_car, model_name, open_drom, parse_cards, parse_detail,
                           text_lines)

MODELS = [
    ("DAIHATSU", "TANTO"), ("DAIHATSU", "MOVE"), ("HONDA", "N_BOX"), ("SUZUKI", "SPACIA"), ("NISSAN", "DAYZ"),
    ("SUZUKI", "WAGON_R"), ("HONDA", "N_WGN"), ("DAIHATSU", "TAFT"),
    ("TOYOTA", "PRIUS"), ("TOYOTA", "AQUA"), ("TOYOTA", "VOXY"), ("TOYOTA", "HARRIER"), ("TOYOTA", "ALPHARD"),
    ("TOYOTA", "COROLLA_CROSS"), ("TOYOTA", "YARIS_CROSS"), ("TOYOTA", "RAV4"), ("TOYOTA", "SIENTA"),
    ("HONDA", "VEZEL"), ("HONDA", "STEPWGN"), ("HONDA", "FREED"), ("HONDA", "FIT"),
    ("NISSAN", "NOTE"), ("NISSAN", "SERENA"), ("NISSAN", "X_TRAIL"),
    ("MAZDA", "CX_5"), ("MAZDA", "CX_30"), ("SUBARU", "FORESTER"), ("SUBARU", "IMPREZA_SPORT"), ("SUBARU", "LEVORG"),
    ("MITSUBISHI", "DELICA_D5"), ("MITSUBISHI", "EK_X"), ("LEXUS", "NX"),
    ("BMW", "3_SERIES"), ("MERCEDES_BENZ", "C_CLASS"), ("VOLKSWAGEN", "GOLF"), ("AUDI", "A4"),
    ("MINI", "MINI"), ("VOLVO", "XC60"), ("PORSCHE", "MACAN"),
]
PER_MODEL = 4


def main():
    f = Fetcher()
    drom, close = open_drom()
    if not drom:
        sys.exit("нет Playwright")
    stats, reasons = Counter(), Counter()
    try:
        for brand, slug in MODELS:
            html = f.get(f"{BASE}/usedcar/brand-{brand}/car-{slug}/")
            cards = parse_cards(html or "")
            print(f"\n######## {MAKES[brand]} {model_name(slug)}: карточек {len(cards)}", flush=True)
            for c in cards[:PER_MODEL]:
                page = f.get(c["url"])
                if not page:
                    continue
                d = parse_detail(page)
                car = {"id": c["id"], "url": c["url"], "make": MAKES[brand], "model": model_name(slug),
                       "year": d.get("year") or c.get("year"), "cc": c.get("cc"), "card_text": c.get("card_text"),
                       "detail": d}
                q = drom_car(car)
                before = dict(drom.stats)
                found = drom.power(q)
                why = next((k for k, v in drom.stats.items() if v != before.get(k, 0)), "?")
                lines = text_lines(page)
                grade_jp = next((lines[i + 1] for i, ln in enumerate(lines[:-1]) if ln == "グレード"), "")
                code = next((lines[i + 1] for i, ln in enumerate(lines[:-1]) if ln in ("型式", "車両型式")), "")
                real = d.get("hp")
                got = found["hp"] if found else None
                stats["машин"] += 1
                if got:
                    stats["найдено на drom"] += 1
                    if real:
                        stats["есть в объявлении"] += 1
                        stats["совпало" if abs(got - real) <= 3 else "НЕ совпало"] += 1
                else:
                    reasons[why] += 1
                mark = "OK" if got and (not real or abs(got - real) <= 3) else ("РАЗНИЦА" if got else "нет")
                print(f"[{mark}] {q['year']} {q.get('cc')} см³ {q.get('fuel')} {q.get('drive')} {q.get('trans')} "
                      f"турбо={q.get('turbo')} | грейд «{grade_jp}» → «{q.get('trim')}» |型式 {code} | "
                      f"в объявлении {real} л.с., drom {got} ({why}) "
                      f"{found['trim']['name'] if found and found.get('trim') else ''}", flush=True)
                if not got or (real and abs(got - real) > 3):
                    print(f"      кандидаты drom: {drom.last_candidates[:6]}", flush=True)
    finally:
        close()
    print("\n===== ИТОГ =====")
    print(dict(stats))
    print("не найдено, причины:", dict(reasons))
    print("совпадения drom:", drom.stats, "страниц drom.ru:", drom.requests)


if __name__ == "__main__":
    main()
