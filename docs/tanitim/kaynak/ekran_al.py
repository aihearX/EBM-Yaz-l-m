import re
import httpx
from playwright.sync_api import sync_playwright

B = "http://127.0.0.1:8000"
c = httpx.Client(base_url=B, follow_redirects=True)
c.post("/giris", data={"kullanici_adi": "admin", "parola": "Demo2026!sc", "sonraki": "/"})
r = c.get("/calismalar/1/eslestirme")
ids = re.findall(r'/calismalar/1/eslestirme/(\d+)"><b>', r.text)
detay_id = ids[0] if ids else "1"
r = c.get("/gonulluler/5")
fids = re.findall(r"/gonulluler/5/form/(\d+)\?vizit_id=(\d+)", r.text)
form_url = f"/gonulluler/5/form/{fids[2][0]}?vizit_id={fids[2][1]}" if len(fids) > 2 else "/gonulluler/5"
tam = [("04_calisma_ozet", "/calismalar/1"), ("05_protokol_kriterler", "/calismalar/1/protokol"), ("07_basvurular", "/calismalar/1/basvurular"),
       ("09_eslestirme_detay", f"/calismalar/1/eslestirme/{detay_id}"), ("10_merkez_zekasi", "/calismalar/1/merkez-zekasi"), ("14_ecrf_form", form_url),
       ("15_veri", "/calismalar/2/veri"), ("17_izlem", "/calismalar/2/izlem"), ("19_bdm_konsol", "/araclar/bdm"), ("20_kimliksizlestirme", "/araclar/kimliksizlestirme"),
       ("22_golge_mod", "/calismalar/1/eslestirme-golge"), ("23_merkez_kayit", "/merkezler"), ("24_sistem", "/yonetim/sistem"), ("25_arge_gostergeleri", "/arge"),
       ("26_fizibilite_raporu", "/calismalar/1/merkez-zekasi/rapor"), ("29_merkez_endeksi", "/merkezler/endeks")]
gorunum = [("02_pano", "/"), ("03_calismalar", "/calismalar"), ("06_merkezler", "/calismalar/1/merkezler"), ("08_eslestirme", "/calismalar/1/eslestirme"),
           ("11_rbm", "/calismalar/2/rbm"), ("12_gonulluler", "/calismalar/1/gonulluler"), ("13_gonullu_detay", "/gonulluler/5"), ("16_guvenlik", "/calismalar/1/guvenlik"),
           ("18_tmf", "/calismalar/1/belgeler"), ("21_denetim_izi", "/yonetim/denetim"), ("30_api_anahtarlari", "/yonetim/api-anahtarlari"), ("31_csv_yukleme", "/merkezler/1/hasta-yukle")]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
    ctx = b.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1.5, locale="tr-TR")
    pg = ctx.new_page()
    pg.goto(B + "/giris")
    pg.screenshot(path="docs/tanitim/ekran/01_giris.png")
    pg.fill("input[name=kullanici_adi]", "admin")
    pg.fill("input[name=parola]", "Demo2026!sc")
    pg.click("button[type=submit]")
    pg.wait_for_load_state("networkidle")
    for ad, url in tam + gorunum:
        pg.goto(B + url)
        pg.wait_for_load_state("networkidle")
        if ad in ("20_kimliksizlestirme", "19_bdm_konsol"):
            pg.click("button.btn.birincil")
            pg.wait_for_load_state("networkidle")
        pg.screenshot(path=f"docs/tanitim/ekran/{ad}.png", full_page=(ad, url) in tam)
    ctx2 = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5, locale="tr-TR")
    pg = ctx2.new_page()
    pg.goto(B + "/giris")
    pg.fill("input[name=kullanici_adi]", "sponsor.gorunum")
    pg.fill("input[name=parola]", "Demo2026!sc")
    pg.click("button[type=submit]")
    pg.wait_for_load_state("networkidle")
    pg.goto(B + "/sponsor")
    pg.wait_for_load_state("networkidle")
    pg.screenshot(path="docs/tanitim/ekran/27_sponsor_portali.png", full_page=False)
    pg.goto(B + "/merkezler/endeks")
    pg.wait_for_load_state("networkidle")
    pg.screenshot(path="docs/tanitim/ekran/28_merkez_endeksi_anonim.png", full_page=True)
    b.close()
print("ok")
