"""Brosuru PDF'e cevirir: python docs/tanitim/kaynak/brosur_pdf.py [chrome_yolu]"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

KOK = pathlib.Path(__file__).resolve().parents[3]
html = (KOK / "docs/tanitim/kaynak/brosur.html").as_uri()
cikti = KOK / "docs/tanitim/EBM_SmartClinical_Tanitim_Brosuru.pdf"
exe = sys.argv[1] if len(sys.argv) > 1 else None
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    pg = b.new_page()
    pg.goto(html)
    pg.wait_for_load_state("networkidle")
    pg.pdf(path=str(cikti), width="297mm", height="210mm", print_background=True,
           margin={"top": "0", "bottom": "0", "left": "0", "right": "0"}, prefer_css_page_size=True)
    b.close()
print(cikti)
