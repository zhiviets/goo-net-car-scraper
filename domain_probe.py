"""Разовая проверка домена bn-auto-dv.ru: DNS, сертификат, страницы. Ничего не отправляет."""
import re
import socket
import ssl
import subprocess

import httpx

DOMAIN = "bn-auto-dv.ru"

for args in (["NS", DOMAIN], ["CNAME", DOMAIN], ["A", DOMAIN], ["CNAME", "www." + DOMAIN], ["A", "www." + DOMAIN],
             ["TXT", "_railway-verify." + DOMAIN], ["TXT", "_railway-verify.www." + DOMAIN]):
    for server in ("8.8.8.8", "77.88.8.8"):
        out = subprocess.run(["dig", "+short", "@" + server, args[0], args[1]], capture_output=True, text=True).stdout
        print(f"DNS {args[0]:5} {args[1]:40} @{server:10} -> {' '.join(out.split()) or '(пусто)'}")

for host in (DOMAIN, "www." + DOMAIN):
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=15) as s, ctx.wrap_socket(s, server_hostname=host) as t:
            c = t.getpeercert()
            print(f"SSL {host}: выдан {dict(x[0] for x in c['issuer']).get('organizationName')}, "
                  f"для {[v for k, v in c.get('subjectAltName', [])]}, до {c['notAfter']}")
    except Exception as e:
        print(f"SSL {host}: ОШИБКА {e!r}")

for url in (f"https://{DOMAIN}/", f"https://www.{DOMAIN}/", f"http://{DOMAIN}/", f"https://{DOMAIN}/robots.txt",
            f"https://{DOMAIN}/sitemap.xml", f"https://{DOMAIN}/auto/japan", f"https://{DOMAIN}/api/live-listings?limit=1",
            "https://bn-auto.up.railway.app/"):
    try:
        r = httpx.get(url, timeout=30, follow_redirects=False)
        body = r.text
        info = [str(r.status_code), r.headers.get("location", ""), r.headers.get("server", "")]
        m = re.search(r"<title>([^<]*)", body)
        if m:
            info.append("title=" + m.group(1))
        m = re.search(r'rel="canonical" href="([^"]*)', body)
        if m:
            info.append("canonical=" + m.group(1))
        m = re.search(r'og:image" content="([^"]*)', body)
        if m:
            info.append("og:image=" + m.group(1))
        if url.endswith((".txt", ".xml")):
            info.append(repr(body[:300]))
        if "/api/" in url:
            info.append(repr(body[:150]))
        print(f"GET {url}: " + " | ".join(i for i in info if i))
    except Exception as e:
        print(f"GET {url}: ОШИБКА {e!r}")
