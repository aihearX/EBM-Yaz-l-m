"""Tanitim dokumani ekran goruntuleri. Demo verisi (CRO modu) yuklu sunucu gerekir.

python docs/tanitim/kaynak/ekran_al.py [chrome_yolu]
SC_EKRAN_URL: sunucu adresi (varsayilan http://127.0.0.1:8000)
SC_EKRAN_KURULUM_URL: bos veritabaniyla calisan ikinci sunucu; verilirse ilk kurulum ekrani da alinir
"""
import os
import re
import sys

import httpx
from playwright.sync_api import sync_playwright

B = os.environ.get("SC_EKRAN_URL", "http://127.0.0.1:8000")
KURULUM = os.environ.get("SC_EKRAN_KURULUM_URL", "")
HEDEF = "docs/tanitim/ekran"
# Ayarlar sayfasindaki surum satiri gizlenir
SURUM_GIZLE = "document.querySelectorAll('th').forEach(t => { if (t.textContent.trim() === 'Sürüm') t.parentElement.remove(); })"
# Fizibilite raporunun alt bilgisindeki surum ibaresi gizlenir
RAPOR_SURUM_GIZLE = "document.querySelectorAll('.gizli').forEach(e => { e.textContent = e.textContent.replace(/EBM SmartClinical v\\S+ · /, ''); })"
PROTOKOL = """5.1 Dahil Etme Kriterleri
1. 18-75 yaş arası hastalar
2. Romatoid artrit tanısı (ACR/EULAR 2010 ölçütleri)
3. DAS28-CRP > 3,2
4. En az bir konvansiyonel sentetik DMARD'a yetersiz yanıt

5.2 Hariç Tutma Kriterleri
a) Gebe veya emziren kadınlar
b) Aktif tüberküloz öyküsü
c) eGFR < 30 mL/dk

Çalışma Kolları
Kol A: JAK inhibitörü 5 mg günde iki kez; Kol B: Standart tedavi

Vizit Takvimi
Tarama (-28 gün ± 7), Vizit 1 (Gün 0), Vizit 2 (Gün 28 ± 3), Hafta 12, Hafta 24

Değerlendirmeler
Her vizitte vital bulgular, laboratuvar ve eşlik eden ilaçlar kaydedilir; VAS ağrı ölçeği doldurulur."""

c = httpx.Client(base_url=B, follow_redirects=True)
c.post("/giris", data={"kullanici_adi": "admin", "parola": "Demo2026!sc", "sonraki": "/"})
r = c.get("/calismalar/1/eslestirme")
ids = re.findall(r'/calismalar/1/eslestirme/(\d+)"><b>', r.text)
detay_id = ids[0] if ids else "1"
r = c.get("/gonulluler/5")
fids = re.findall(r"/gonulluler/5/form/(\d+)\?vizit_id=(\d+)", r.text)
form_url = f"/gonulluler/5/form/{fids[2][0]}?vizit_id={fids[2][1]}" if len(fids) > 2 else "/gonulluler/5"
r = c.get("/calismalar/1/tasarim")
form_ids = re.findall(r'/calismalar/1/tasarim/form/(\d+)"', r.text)
tasarimci_url = f"/calismalar/1/tasarim/form/{form_ids[3]}" if len(form_ids) > 3 else "/calismalar/1/tasarim"
r = c.get("/calismalar/1/izlem")
zids = sorted(set(re.findall(r"/calismalar/1/izlem/ziyaret/(\d+)", r.text)), key=int)
ziyaret_url = f"/calismalar/1/izlem/ziyaret/{zids[0]}" if zids else "/calismalar/1/izlem"
sapma_url = "/calismalar/1/izlem"
for s in sorted(set(re.findall(r"/calismalar/1/izlem/sapma/(\d+)", r.text)), key=int):
    t = c.get(f"/calismalar/1/izlem/sapma/{s}").text
    if re.search(r'rozet kirmizi">Majör', t) and re.search(r'rozet sari">Açık', t):
        sapma_url = f"/calismalar/1/izlem/sapma/{s}"
        break

# (ad, url, tam sayfa)
sayfalar = [
    ("02_pano", "/", False), ("03_calismalar", "/calismalar", False), ("04_calisma_ozet", "/calismalar/1", True),
    ("05_protokol_kriterler", "/calismalar/1/protokol", True), ("06_merkezler", "/calismalar/1/merkezler", False),
    ("07_basvurular", "/calismalar/1/basvurular", True), ("08_eslestirme", "/calismalar/1/eslestirme", False),
    ("09_eslestirme_detay", f"/calismalar/1/eslestirme/{detay_id}", True), ("10_merkez_zekasi", "/calismalar/1/merkez-zekasi", True),
    ("11_rbm", "/calismalar/2/rbm", False), ("12_gonulluler", "/calismalar/1/gonulluler", False),
    ("13_gonullu_detay", "/gonulluler/5", False), ("14_ecrf_form", form_url, True), ("15_veri", "/calismalar/2/veri", True),
    ("16_guvenlik", "/calismalar/1/guvenlik", False), ("17_izlem", "/calismalar/2/izlem", True),
    ("18_tmf", "/calismalar/1/belgeler", False), ("19_tasarim", "/calismalar/1/tasarim", True),
    ("20_kimliksizlestirme", "/araclar/kimliksizlestirme", True), ("21_denetim_izi", "/yonetim/denetim", False),
    ("22_golge_mod", "/calismalar/1/eslestirme-golge", True), ("23_merkez_kayit", "/merkezler", True),
    ("24_sistem", "/yonetim/sistem", False), ("25_analiz", "/calismalar/1/analiz", True),
    ("26_fizibilite_raporu", "/calismalar/1/merkez-zekasi/rapor", True), ("29_merkez_endeksi", "/merkezler/endeks", True),
    ("30_api_anahtarlari", "/yonetim/api-anahtarlari", False), ("31_csv_yukleme", "/merkezler/1/hasta-yukle", False),
    ("35_ecrf_tasarimci", tasarimci_url, True), ("37_ekip", "/calismalar/1/ekip", False),
    ("39_ziyaret_raporu", ziyaret_url, False), ("40_sapma_kapatma", sapma_url, False),
    ("41_tablo1", "/calismalar/1/analiz/tablo1", True),
]


def giris(pg, kullanici):
    pg.goto(B + "/giris")
    pg.fill("input[name=kullanici_adi]", kullanici)
    pg.fill("input[name=parola]", "Demo2026!sc")
    pg.click("button[type=submit]")
    pg.wait_for_load_state("networkidle")


def git(pg, url):
    pg.goto(B + url)
    pg.wait_for_load_state("networkidle")


exe = sys.argv[1] if len(sys.argv) > 1 else None
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1.5, locale="tr-TR")
    pg = ctx.new_page()
    git(pg, "/giris")
    pg.screenshot(path=f"{HEDEF}/01_giris.png")
    giris(pg, "admin")
    for ad, url, tam in sayfalar:
        git(pg, url)
        if ad == "20_kimliksizlestirme":
            pg.click("button.btn.birincil")
            pg.wait_for_load_state("networkidle")
        if ad == "24_sistem":
            pg.evaluate(SURUM_GIZLE)
        if ad == "26_fizibilite_raporu":
            pg.evaluate(RAPOR_SURUM_GIZLE)
        pg.screenshot(path=f"{HEDEF}/{ad}.png", full_page=tam)

    # Randomizasyon: liste yoksa merkeze gore strata ile uretilir (e-imza)
    git(pg, "/calismalar/1/randomizasyon")
    if pg.locator("text=Liste yok").count():
        pg.select_option("select[name=strata]", index=1)
        pg.fill("input[name=parola]", "Demo2026!sc")
        pg.click("form[action$='/uret'] button")
        pg.wait_for_load_state("networkidle")
    pg.screenshot(path=f"{HEDEF}/38_randomizasyon.png", full_page=False)

    # Protokolden taslak: tasarim asamasindaki calisma, yalnizca oneri (uygulanmaz)
    git(pg, "/calismalar/6/tasarim/protokol-taslak")
    pg.fill("textarea[name=metin]", PROTOKOL)
    pg.click("form[action$='/protokol-taslak'] button.birincil")
    pg.wait_for_load_state("networkidle")
    pg.screenshot(path=f"{HEDEF}/36_protokol_taslak.png", full_page=True)

    # Sihirbaz: 1. adim doldurulur, 2. adim (kollar, vizit sablonu) alinir, taslak silinir
    git(pg, "/sihirbaz/1")
    pg.fill("input[name=kisa_ad]", "KOAH sabit doz inhaler")
    pg.fill("input[name=baslik]", "Orta-ağır KOAH'ta sabit doz üçlü inhaler tedavinin etkinliği")
    pg.select_option("select[name=faz]", index=3)
    pg.fill("input[name=terapotik_alan]", "Göğüs hastalıkları")
    pg.fill("input[name=hedef_hasta]", "240")
    pg.screenshot(path=f"{HEDEF}/33_sihirbaz_1.png", full_page=False)
    pg.click("form button.birincil")
    pg.wait_for_load_state("networkidle")
    if "/sihirbaz/2" in pg.url:
        pg.click("#kol-ekle")
        pg.locator("input[name=kol_ad]").nth(0).fill("Kol A: Üçlü inhaler")
        pg.locator("input[name=kol_ad]").nth(1).fill("Kol B: İkili inhaler")
        pg.fill("textarea[name=dahil]", "40 yaş ve üzeri\nFEV1 %30-70 arası\nSon 12 ayda en az bir alevlenme")
        pg.fill("textarea[name=haric]", "Astım tanısı\nSon 4 haftada alevlenme")
        pg.screenshot(path=f"{HEDEF}/34_sihirbaz_2.png", full_page=True)
    git(pg, "/sihirbaz/iptal")

    # Sponsor rolu: Genel Bakis'ta kendi kurumunun salt okunur ozeti
    ctx2 = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5, locale="tr-TR")
    pg = ctx2.new_page()
    giris(pg, "sponsor.gorunum")
    git(pg, "/")
    pg.screenshot(path=f"{HEDEF}/27_sponsor_gorunumu.png", full_page=False)
    git(pg, "/merkezler/endeks")
    pg.screenshot(path=f"{HEDEF}/28_merkez_endeksi_anonim.png", full_page=True)

    if KURULUM:
        pg = b.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1.5, locale="tr-TR").new_page()
        pg.goto(KURULUM + "/kurulum")
        pg.wait_for_load_state("networkidle")
        pg.screenshot(path=f"{HEDEF}/32_kurulum.png", full_page=True)
    b.close()
print("ok")
