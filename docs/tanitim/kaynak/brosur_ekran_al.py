"""Brosur icin ekran goruntuleri (surum bilgisi gizlenir). python docs/tanitim/kaynak/brosur_ekran_al.py [chrome_yolu]

SC_EKRAN_URL: demo verisi (CRO modu) yuklu sunucu (varsayilan http://127.0.0.1:8000)
"""
import os
import re
import sys

import httpx
from playwright.sync_api import sync_playwright

B = os.environ.get("SC_EKRAN_URL", "http://127.0.0.1:8000")
HEDEF = "docs/tanitim/brosur/ekran"
GIZLE = ".yan .alt div { display:none } .yan .alt a { display:none }"
# Fizibilite raporunun alt bilgisindeki surum ibaresi gizlenir
RAPOR_SURUM_GIZLE = "document.querySelectorAll('.gizli').forEach(e => { e.textContent = e.textContent.replace(/EBM SmartClinical v\\S+ · /, ''); })"
c = httpx.Client(base_url=B, follow_redirects=True)
c.post("/giris", data={"kullanici_adi": "admin", "parola": "Demo2026!sc", "sonraki": "/"})
r = c.get("/calismalar/1/eslestirme")
ids = re.findall(r'/calismalar/1/eslestirme/(\d+)"><b>', r.text)
detay = ids[0] if ids else "1"
r = c.get("/gonulluler/5")
fids = re.findall(r"/gonulluler/5/form/(\d+)\?vizit_id=(\d+)", r.text)
form_url = f"/gonulluler/5/form/{fids[2][0]}?vizit_id={fids[2][1]}" if len(fids) > 2 else "/gonulluler/5"
r = c.get("/calismalar/1/tasarim")
form_ids = re.findall(r'/calismalar/1/tasarim/form/(\d+)"', r.text)
tasarimci_url = f"/calismalar/1/tasarim/form/{form_ids[3]}" if len(form_ids) > 3 else "/calismalar/1/tasarim"
sayfalar = [
    ("pano", "/", 1000), ("calisma", "/calismalar/1", 1000), ("protokol", "/calismalar/1/protokol", 1000),
    ("eslestirme", "/calismalar/1/eslestirme", 1000), ("eslestirme_detay", f"/calismalar/1/eslestirme/{detay}", 1150),
    ("merkez_zekasi", "/calismalar/1/merkez-zekasi", 1150), ("rbm", "/calismalar/2/rbm", 1000),
    ("gonullu", "/gonulluler/5", 1000), ("form", form_url, 1000), ("guvenlik", "/calismalar/1/guvenlik", 1000),
    ("tmf", "/calismalar/1/belgeler", 1000), ("denetim", "/yonetim/denetim", 1000),
    ("tasarim", "/calismalar/1/tasarim", 1150), ("deid", "/araclar/kimliksizlestirme", 1000), ("analiz", "/calismalar/1/analiz", 1000),
    ("ecrf_tasarimci", tasarimci_url, 1000),
    ("endeks", "/merkezler/endeks", 1100), ("fizibilite", "/calismalar/1/merkez-zekasi/rapor", 1150),
]
exe = sys.argv[1] if len(sys.argv) > 1 else None
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=2, locale="tr-TR")
    pg = ctx.new_page()
    pg.goto(B + "/giris")
    pg.fill("input[name=kullanici_adi]", "admin")
    pg.fill("input[name=parola]", "Demo2026!sc")
    pg.click("button[type=submit]")
    pg.wait_for_load_state("networkidle")
    for ad, url, yuk in sayfalar:
        pg.set_viewport_size({"width": 1440, "height": yuk})
        pg.goto(B + url)
        pg.wait_for_load_state("networkidle")
        pg.add_style_tag(content=GIZLE)
        if ad == "fizibilite":
            pg.evaluate(RAPOR_SURUM_GIZLE)
        if ad == "deid":
            pg.click("button.btn.birincil")
            pg.wait_for_load_state("networkidle")
            pg.add_style_tag(content=GIZLE)
        pg.screenshot(path=f"{HEDEF}/{ad}.png", full_page=False)
    ctx2 = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2, locale="tr-TR")
    pg = ctx2.new_page()
    pg.goto(B + "/giris")
    pg.fill("input[name=kullanici_adi]", "sponsor.gorunum")
    pg.fill("input[name=parola]", "Demo2026!sc")
    pg.click("button[type=submit]")
    pg.wait_for_load_state("networkidle")
    pg.goto(B + "/")
    pg.wait_for_load_state("networkidle")
    # sponsor rolu: Genel Bakis'ta kendi kurumunun salt okunur ozeti
    pg.add_style_tag(content=GIZLE)
    pg.screenshot(path=f"{HEDEF}/sponsor_genel.png", full_page=False)
    b.close()
print("ok")
