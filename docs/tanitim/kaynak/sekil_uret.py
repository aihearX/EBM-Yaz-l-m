"""SVG diyagramlari programatik olarak yazar (kutu/ok yardimcilari), sonra Chromium ile PNG'ye cevirir."""
from pathlib import Path

from playwright.sync_api import sync_playwright

L, T, G, D, LT, LB, Y, R, W = "#16325c", "#0e8a8a", "#e6e8ec", "#3d4350", "#e3f3f3", "#e7eef9", "#fdf3e0", "#b23a3a", "#ffffff"
FONT = 'font-family="Liberation Sans, Arial, sans-serif"'


class Svg:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" {FONT}>',
            f'<defs><marker id="ok" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto" markerUnits="userSpaceOnUse">'
            f'<path d="M0,0 L12,6 L0,12 Z" fill="{D}"/></marker>'
            f'<marker id="okt" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto" markerUnits="userSpaceOnUse">'
            f'<path d="M0,0 L12,6 L0,12 Z" fill="{T}"/></marker>'
            f'<marker id="okr" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto" markerUnits="userSpaceOnUse">'
            f'<path d="M0,0 L12,6 L0,12 Z" fill="{R}"/></marker></defs>',
            f'<rect width="{w}" height="{h}" fill="{W}"/>',
        ]

    def rect(self, x, y, w, h, fill=W, stroke=L, sw=2, r=10, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def text(self, x, y, s, size=22, fill=D, weight="normal", anchor="middle", rotate=None):
        tr = f' transform="rotate({rotate} {x} {y})"' if rotate is not None else ""
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" text-anchor="{anchor}"{tr}>{s}</text>')

    def lines(self, x, y, lines, size=20, fill=D, weight="normal", anchor="middle", lh=None):
        lh = lh or int(size * 1.3)
        for i, s in enumerate(lines):
            self.text(x, y + i * lh, s, size, fill, weight, anchor)

    def box(self, x, y, w, h, title, sub=None, fill=W, stroke=L, tsize=22, ssize=19, tfill=L, sfill=D, r=10, sw=2):
        self.rect(x, y, w, h, fill, stroke, sw, r)
        cx = x + w / 2
        sub = sub or []
        total = tsize * 1.3 + len(sub) * ssize * 1.3
        y0 = y + h / 2 - total / 2 + tsize
        self.text(cx, y0, title, tsize, tfill, "bold")
        self.lines(cx, y0 + tsize * 1.3 + 2, sub, ssize, sfill)

    def arrow(self, x1, y1, x2, y2, color=D, sw=3, marker="ok", dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}" marker-end="url(#{marker})"{d}/>')

    def path(self, d, color=D, sw=3, marker="ok", dash=None):
        dd = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" marker-end="url(#{marker})"{dd}/>')

    def line(self, x1, y1, x2, y2, color=D, sw=3, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}"{d}/>')

    def save(self, name):
        self.parts.append("</svg>")
        Path(name).write_text("\n".join(self.parts), encoding="utf-8")


# ---------------------------------------------------------------- 1. mimari
def sekil1():
    s = Svg(1600, 1000)
    s.text(800, 44, "EBM SmartClinical – Platform Mimarisi", 30, L, "bold")
    # sag serit
    s.rect(1500, 80, 70, 890, LT, T, 2, 12)
    s.text(1535, 525, "Hastane içi kurulum – veri kurum dışına çıkmaz", 22, T, "bold", rotate=-90)
    X0, Wt = 40, 1130  # ana sutun genisligi
    # roller
    s.rect(X0, 80, Wt, 90, LB, L, 1.5, 10)
    s.text(X0 + 14, 108, "Kullanıcı rolleri", 20, L, "bold", "start")
    roller = ["Araştırmacı", "Koordinatör", "CRA", "Proje Yöneticisi", "Sponsor", "Veri Yöneticisi", "Farmakovijilans", "Denetçi"]
    bw = (Wt - 28 - 7 * 10) / 8
    for i, r in enumerate(roller):
        x = X0 + 14 + i * (bw + 10)
        s.rect(x, 118, bw, 42, W, L, 1.5, 8)
        s.text(x + bw / 2, 146, r, 17 if len(r) > 11 else 19, D)
    s.arrow(X0 + Wt / 2, 172, X0 + Wt / 2, 196)
    # arayuz
    s.rect(X0, 198, Wt, 54, L, L, 1, 10)
    s.text(X0 + Wt / 2, 233, "Web Arayüzü (rol bazlı paneller)   ·   REST API v1 (FHIR uç noktaları dahil)", 22, W, "bold")
    s.arrow(X0 + Wt / 2, 254, X0 + Wt / 2, 278)
    # uygulama modulleri
    s.rect(X0, 280, Wt, 170, W, L, 2, 10)
    s.text(X0 + 14, 308, "Uygulama modülleri", 20, L, "bold", "start")
    mod = [("Çalışma", "Yönetimi"), ("Merkez ve", "Araştırmacı"), ("Etik / TİTCK", "Başvuruları"), ("Hasta", "Eşleştirme"),
           ("eCRF /", "Veri Yönetimi"), ("Güvenlik", "(AE / SAE)"), ("Risk Bazlı", "İzlem"), ("TMF Belge", "Yönetimi")]
    for i, (a, b) in enumerate(mod):
        x = X0 + 14 + i * (bw + 10)
        s.rect(x, 322, bw, 108, LB, L, 1.5, 8)
        s.text(x + bw / 2, 368, a, 19, L, "bold")
        s.text(x + bw / 2, 396, b, 19, L, "bold")
    s.arrow(X0 + Wt / 2, 452, X0 + Wt / 2, 476)
    # yapay zeka katmani
    s.rect(X0, 478, Wt, 170, LT, T, 2, 10)
    s.text(X0 + 14, 506, "Yapay zekâ katmanı", 20, T, "bold", "start")
    yz = [("Türkçe Klinik", "BDM"), ("Kriter", "Yapılandırma"), ("RAG +", "Kanıt Çıkarma"), ("Koruma", "Katmanı"),
          ("Kimliksiz-", "leştirme"), ("Merkez Zekâsı", "Modelleri"), ("KRI / Anomali", "Motoru")]
    bw2 = (Wt - 28 - 6 * 10) / 7
    for i, (a, b) in enumerate(yz):
        x = X0 + 14 + i * (bw2 + 10)
        s.rect(x, 520, bw2, 108, W, T, 1.5, 8)
        s.text(x + bw2 / 2, 566, a, 20, T, "bold")
        s.text(x + bw2 / 2, 594, b, 20, T, "bold")
    s.arrow(X0 + Wt / 2, 650, X0 + Wt / 2, 674)
    # veri ve entegrasyon
    s.rect(X0, 676, Wt, 150, W, L, 2, 10)
    s.text(X0 + 14, 704, "Veri ve entegrasyon", 20, L, "bold", "start")
    ve = [("PostgreSQL", "işlem verisi"), ("Dosya deposu", "TMF belgeleri"), ("HBYS", "FHIR R4 adaptörü"), ("EDC / CTMS", "entegrasyonu"), ("GPU sunucu", "vLLM / llama.cpp")]
    bw3 = (Wt - 28 - 4 * 10) / 5
    for i, (a, b) in enumerate(ve):
        x = X0 + 14 + i * (bw3 + 10)
        s.rect(x, 716, bw3, 92, G, D, 1.5, 8)
        s.text(x + bw3 / 2, 756, a, 21, D, "bold")
        s.text(x + bw3 / 2, 784, b, 19, D)
    # capraz kesen
    s.rect(X0, 850, Wt, 122, Y, "#b7791f", 1.5, 10)
    s.text(X0 + 14, 878, "Çapraz kesen hizmetler (tüm katmanlarda)", 20, "#7a4f0e", "bold", "start")
    ck = [("Denetim izi", "hash zincirli, değiştirilemez"), ("Elektronik imza", "21 CFR Part 11"), ("Rol bazlı erişim", "RBAC, 10 rol"), ("Ortak veri modeli", "FHIR R4 / OMOP CDM")]
    bw4 = (Wt - 28 - 3 * 10) / 4
    for i, (a, b) in enumerate(ck):
        x = X0 + 14 + i * (bw4 + 10)
        s.rect(x, 892, bw4, 66, W, "#b7791f", 1.5, 8)
        s.text(x + bw4 / 2, 919, a, 20, "#7a4f0e", "bold")
        s.text(x + bw4 / 2, 945, b, 17, "#7a4f0e")
    # sag taraf: capraz kesenlerin tum katmanlara dokundugunu gosteren dikey cizgi
    s.line(1205, 198, 1205, 850, "#b7791f", 3, "8,6")
    s.rect(1215, 420, 260, 150, W, "#b7791f", 1.5, 8)
    s.lines(1345, 455, ["Her katmandaki işlem", "kullanıcı, zaman ve", "gerekçe ile denetim", "izine yazılır; kritik", "kayıtlar e-imza ister."], 18, D)
    s.save("sekil_01_mimari.svg")


# ---------------------------------------------------------- 2. yasam dongusu
def sekil2():
    s = Svg(1600, 760)
    s.text(800, 44, "Klinik Araştırma Yaşam Döngüsü ve Platform Desteği", 30, L, "bold")
    s.rect(40, 70, 1520, 44, Y, "#b7791f", 1.5, 8)
    s.text(800, 99, "Denetim izi ve elektronik imza tüm aşamalarda", 20, "#7a4f0e", "bold")
    asama = [("Tasarım", ["Protokol sürümleri", "Kriter yapılandırma", "eCRF tasarımı"]),
             ("Fizibilite", ["Merkez sıralaması", "Kazanım tahmini", "Araştırmacı defteri"]),
             ("Etik / TİTCK", ["EK, TİTCK, KVKK", "Süre analizi", "Değişiklik takibi"]),
             ("Merkez", ["Kilometre taşları", "Gecikme riski", "SIV planlama"]),
             ("Hasta Kaydı", ["BDM ile ön tarama", "Onam takibi", "Randomizasyon"]),
             ("İzlem", ["eCRF ve sorgular", "AE / SAE bildirimi", "KRI erken uyarı"]),
             ("Kapanış", ["Veri tabanı kilidi", "COV ziyaretleri", "TMF tamlık"]),
             ("Analiz", ["SDTM / OMOP", "Rapor verisi", "İstatistik paketi"]),
             ("Arşiv", ["25 yıl saklama", "E-imzalı kayıtlar", "Denetim erişimi"])]
    alt = {"Etik / TİTCK": "Başvurusu", "Merkez": "Aktivasyonu", "Analiz": "ve Raporlama"}
    n = len(asama)
    gap = 14
    bw = (1520 - (n - 1) * gap) / n
    for i, (ad, oz) in enumerate(asama):
        x = 40 + i * (bw + gap)
        fill = L if i in (4, 5) else T
        s.rect(x, 150, bw, 96, fill, fill, 1, 10)
        s.text(x + 16, 174, str(i + 1), 18, W, "bold", "start")
        if ad in alt:
            s.text(x + bw / 2, 206, ad, 21, W, "bold")
            s.text(x + bw / 2, 232, alt[ad], 19, W, "bold")
        else:
            s.text(x + bw / 2, 212, ad, 22, W, "bold")
        if i < n - 1:
            s.arrow(x + bw + 1, 198, x + bw + gap - 1, 198, D, 3)
        # ozellikler
        s.rect(x, 268, bw, 160, LB if i in (4, 5) else W, L, 1.5, 8)
        s.lines(x + bw / 2, 304, oz, 17, D, lh=36)
        # kucuk dikey baglanti
        s.line(x + bw / 2, 246, x + bw / 2, 268, G, 2)
    s.text(800, 470, "Koyu renkli aşamalar, yapay zekâ modüllerinin (Türkçe Klinik BDM, merkez zekâsı, risk bazlı izlem) en yoğun kullanıldığı aşamalardır.", 19, D)
    # alt: dongu / geri besleme serit
    s.rect(40, 500, 1520, 220, LT, T, 1.5, 10)
    s.text(60, 532, "Sürekli öğrenme döngüsü", 21, T, "bold", "start")
    dongu = [("Operasyon verisi", "kazanım, aktivasyon,", "sapma, sorgu kayıtları"), ("Model güncelleme", "Bayesçi öncüller,", "KRI eşikleri, BDM ince ayarı"),
             ("Karar desteği", "merkez seçimi, ön tarama,", "izlem planı"), ("Araştırmacı / CRA kararı", "onay, red, kapanış notu,", "gerekçe")]
    bw2 = 330
    for i, (a, b, c) in enumerate(dongu):
        x = 70 + i * (bw2 + 50)
        s.rect(x, 556, bw2, 120, W, T, 1.5, 8)
        s.text(x + bw2 / 2, 598, a, 20, T, "bold")
        s.text(x + bw2 / 2, 626, b, 18, D)
        s.text(x + bw2 / 2, 652, c, 18, D)
        if i < 3:
            s.arrow(x + bw2 + 2, 616, x + bw2 + 48, 616, T, 3, "okt")
    s.path(f"M {70 + 3 * 380 + 165} 678 L {70 + 3 * 380 + 165} 700 L 235 700 L 235 680", T, 3, "okt", "8,6")
    s.save("sekil_02_yasam_dongusu.svg")


# ------------------------------------------------------ 3. eslestirme akisi
def sekil3():
    s = Svg(1600, 900)
    s.text(800, 44, "Protokol–Hasta Eşleştirme Boru Hattı", 30, L, "bold")
    # ust sira: veri hazirlik
    s.box(40, 100, 230, 110, "HBYS", ["FHIR R4 Bundle", "(Patient, Condition,", "Observation, Document)"], LB, L, 22, 17)
    s.arrow(272, 155, 318, 155)
    s.box(320, 100, 260, 110, "Kimliksizleştirme", ["TCKN, ad, tarih, telefon,", "kurum, adres maskeleme;", "ikinci geçiş doğrulama"], LT, T, 22, 17)
    s.arrow(582, 155, 628, 155)
    s.box(630, 100, 250, 110, "Hasta havuzu", ["kimliksizleştirilmiş", "yapısal veri + metinler", "(takma ad ile)"], LB, L, 22, 17)
    s.arrow(882, 155, 928, 155)
    s.box(930, 100, 220, 110, "ICD-10 ön filtre", ["dahil kriterindeki", "tanı kodlarına göre", "havuz daraltma"], W, L, 22, 17)
    s.arrow(1152, 155, 1198, 155)
    s.box(1200, 100, 360, 110, "Protokol kriterleri", ["dahil / hariç metinleri →", "hesaplanabilir sorgu", "(BDM veya kural ayrıştırıcı)"], LB, L, 22, 17)
    # orta: iki paralel yol
    s.rect(40, 260, 1520, 330, W, L, 2, 12)
    s.text(60, 292, "Kriter değerlendirme (her hasta × her kriter)", 22, L, "bold", "start")
    s.box(70, 320, 400, 110, "(a) Yapısal değerlendirme", ["yaş, cinsiyet, tanı (ICD-10), laboratuvar (LOINC),", "ilaç (ATC), performans (ECOG), zaman penceresi"], LB, L, 21, 17)
    s.box(70, 455, 400, 110, "(b) Metin yolu – RAG", ["cümle/paragraf parçalama,", "BM25 + gömme ile hibrit arama (k=5)"], LT, T, 21, 17)
    s.arrow(472, 510, 518, 510, T, 3, "okt")
    s.box(520, 455, 330, 110, "Türkçe Klinik BDM", ["kriter için kanıt çıkarma:", "sonuç + kaynak cümle + güven"], LT, T, 21, 17)
    s.arrow(852, 510, 898, 510, T, 3, "okt")
    s.box(900, 455, 330, 110, "Koruma katmanı", ["kanıt kaynakta birebir var mı?", "güven ≥ eşik? JSON şema geçerli mi?"], Y, "#b7791f", 21, 17, "#7a4f0e")
    s.arrow(472, 375, 1278, 375)
    s.arrow(1232, 510, 1278, 510, T, 3, "okt")
    s.text(850, 362, "güven ≥ 0,70 ise doğrudan", 17, D)
    s.text(850, 408, "belirsiz veya düşük güven → metin yoluna geçilir", 17, D)
    s.path("M 270 432 L 270 455", D, 3, "ok", "6,5")
    s.box(1280, 320, 250, 245, "Skor ve karar", ["uygun", "olası", "belirsiz", "uygun değil", "", "hariç kriteri sağlandıysa", "doğrudan 'uygun değil'"], W, L, 22, 18)
    # ust siradan kriter degerlendirmeye inis
    s.arrow(1380, 212, 1380, 258)
    s.arrow(755, 212, 755, 258)
    # alt sira: insan kararı
    s.arrow(1405, 592, 1405, 636)
    s.box(1180, 640, 380, 110, "Araştırmacı incelemesi", ["onay / red / beklet + gerekçe", "kriter bazında kanıt cümleleri görüntülenir"], LB, L, 22, 17)
    s.arrow(1178, 695, 1132, 695)
    s.box(760, 640, 370, 110, "Gönüllü ön tarama listesi", ["onam görüşmesi planlanır,", "gönüllü numarası atanır"], W, L, 22, 17)
    s.arrow(758, 695, 712, 695)
    s.box(330, 640, 380, 110, "Gölge mod değerlendirmesi", ["model kararı × araştırmacı kararı →", "duyarlılık, özgüllük, PPV (pilot doğrulama)"], Y, "#b7791f", 22, 17, "#7a4f0e")
    s.rect(40, 640, 260, 110, G, D, 1.5, 8)
    s.text(170, 680, "Denetim izi", 21, L, "bold")
    s.lines(170, 708, ["her tarama, görüntüleme", "ve karar kaydedilir"], 18, D)
    s.line(328, 695, 302, 695, D, 3)
    s.text(800, 820, "Hiçbir hasta araştırmacı onayı olmadan çalışmaya alınmaz; model çıktısı kaynak cümlesiyle birlikte sunulur, kaynakta bulunmayan ifadeler 'belirsiz' olarak işaretlenir.", 19, D)
    s.text(800, 850, "BDM sunucusuna erişilemediğinde sistem kural tabanlı ayrıştırıcı ve kalıp tabanlı metin değerlendirmesine düşer; bu durum denetim izine yazılır.", 19, D)
    s.save("sekil_03_eslestirme_akisi.svg")


# ------------------------------------------------------- 4. bdm gelistirme
def sekil4():
    s = Svg(1600, 760)
    s.text(800, 44, "Türkçe Klinik Büyük Dil Modeli Geliştirme Hattı", 30, L, "bold")
    adim = [("Türkçe tıbbi derlem", ["kimliksizleştirilmiş epikriz,", "patoloji, radyoloji raporları;", "kılavuzlar, protokoller"], LB, L),
            ("Derlem temizleme", ["normalizasyon, hash ile", "tekilleştirme, şablon", "metinlerin ayıklanması"], W, L),
            ("Sürekli ön eğitim", ["açık kaynak 7–8B temel", "model; Türkçe tıbbi alan", "uyarlaması"], LT, T),
            ("Talimat ince ayarı", ["LoRA / QLoRA (4-bit);", "kriter yapılandırma, kanıt", "çıkarma, özet, ICD-10 önerisi"], LT, T)]
    adim2 = [("Değerlendirme", ["altın standart set;", "duyarlılık ≥ %90,", "halüsinasyon ≤ %2"], Y, "#b7791f"),
             ("Nicemleme", ["GGUF Q4_K_M / Q8_0;", "kalite kontrol eşiği", "(kayıp ≤ %1,5)"], W, L),
             ("Hastane içi sunum", ["vLLM / llama.cpp, tek GPU;", "kapalı ağ, dış erişim yok"], L, L)]
    bw, gap, y = 340, 50, 110
    for i, (a, b, f, st) in enumerate(adim):
        x = 40 + i * (bw + gap)
        s.box(x, y, bw, 150, a, b, f, st, 22, 18, W if f == L else (T if st == T else L))
        if i < 3:
            s.arrow(x + bw + 2, y + 75, x + bw + gap - 2, y + 75)
    # ikinci sira
    y2 = 360
    s.path(f"M {40 + 3 * 390 + 170} {y + 152} L {40 + 3 * 390 + 170} {y2 - 40} L 210 {y2 - 40} L 210 {y2 - 2}")
    for i, (a, b, f, st) in enumerate(adim2):
        x = 40 + i * (bw + gap)
        tf = W if f == L else ("#7a4f0e" if st == "#b7791f" else L)
        s.box(x, y2, bw, 150, a, b, f, st, 22, 18, tf, W if f == L else D)
        if i < 2:
            s.arrow(x + bw + 2, y2 + 75, x + bw + gap - 2, y2 + 75)
    # degerlendirme basarisiz -> ince ayara geri
    s.path(f"M 210 {y2 + 152} L 210 {y2 + 190} L {40 + 3 * 390 + 170} {y2 + 190} L {40 + 3 * 390 + 170} {y + 152 + 1}", R, 3, "okr", "8,6")
    s.text(760, y2 + 182, "hedef karşılanmazsa: veri artırımı ve yeniden ince ayar", 18, R)
    # sag alt: platform kullanimi
    s.box(1210, y2, 350, 150, "SmartClinical platformu", ["kriter yapılandırma, hasta eşleştirme,", "protokolden taslak; tüm istekler", "denetim izinde"], LB, L, 22, 18)
    s.arrow(40 + 2 * 390 + bw + 2, y2 + 75, 1208, y2 + 75)
    # klinisyen etiketleme dongusu
    s.rect(40, 620, 1520, 110, LT, T, 1.5, 10)
    s.text(60, 652, "Klinisyen etiketleme döngüsü", 21, T, "bold", "start")
    s.text(60, 684, "Platformdaki araştırmacı kararları (onay / red, gerekçe) ve gölge mod karşılaştırmaları etiketlenmiş örnek olarak altın standart sete eklenir;", 18, D, anchor="start")
    s.text(60, 710, "etiketleyiciler arası uyum (Cohen kappa) izlenir, uyumsuz örnekler ikinci klinisyene yönlendirilir. Döngü her model sürümünde tekrarlanır.", 18, D, anchor="start")
    s.path(f"M 1385 {y2 + 152} L 1385 {y2 + 215} L 1385 618", T, 3, "okt", "8,6")
    s.path("M 100 618 L 100 585 L 100 262", T, 3, "okt", "8,6")
    s.text(130, 300, "yeni etiketli veri", 17, T, anchor="start")
    s.save("sekil_04_bdm_gelistirme.svg")


# -------------------------------------------------------------- 5. kurulum
def sekil5():
    s = Svg(1600, 900)
    s.text(800, 44, "Kurulum Topolojisi – Hastane İçi (On-Premise)", 30, L, "bold")
    # hastane agi
    s.rect(40, 80, 1120, 780, "#f7f9fb", L, 3, 16, "14,8")
    s.text(64, 114, "Hastane ağı (kapalı ağ / DMZ)", 23, L, "bold", "start")
    # kullanicilar
    s.box(80, 160, 240, 120, "Kullanıcılar", ["araştırmacı, koordinatör,", "hastane CRA'sı", "tarayıcı · HTTPS"], LB, L, 22, 17)
    s.arrow(322, 220, 378, 220)
    s.box(380, 160, 220, 120, "Nginx", ["TLS 1.2/1.3, HSTS,", "güvenlik başlıkları,", "50 MB yükleme sınırı"], W, L, 22, 17)
    s.arrow(602, 220, 658, 220)
    s.box(660, 160, 300, 120, "Uygulama sunucusu", ["FastAPI / Uvicorn,", "systemd veya Docker,", "rol bazlı erişim, denetim izi"], L, L, 22, 17, W, W)
    # veri katmani
    s.arrow(810, 282, 810, 358)
    s.box(660, 360, 300, 110, "PostgreSQL 16", ["denetim_kaydi: yalnız INSERT", "(UPDATE/DELETE engelli)"], LB, L, 22, 17)
    s.arrow(962, 415, 1018, 415)
    s.box(1020, 360, 120, 110, "Dosya", ["deposu", "(TMF)"], LB, L, 20, 17)
    s.box(660, 500, 480, 80, "Yedekleme", ["pg_dump + dosya dizini, SHA-256; 7 gün / 30 gün / 7 yıl"], W, D, 21, 17, D)
    s.arrow(810, 472, 810, 498)
    # bdm sunucusu
    s.box(380, 360, 220, 160, "BDM sunucusu", ["GPU (≥ 24 GB VRAM)", "vLLM veya llama.cpp", "GGUF Q4 / Q8 model", "yalnız iç ağdan erişim"], LT, T, 22, 17)
    s.path("M 740 282 L 740 330 L 490 330 L 490 358", T, 3, "okt")
    s.text(615, 322, "HTTP, iç ağ", 17, T)
    # HBYS
    s.box(80, 360, 240, 160, "HBYS", ["FHIR R4 uç noktası", "Patient, Condition,", "Observation, Medication,", "DocumentReference"], W, L, 22, 17)
    s.path("M 200 522 L 200 560 L 630 560 L 630 240 L 658 240", D, 3, "ok")
    s.text(415, 552, "FHIR R4 (salt okunur, zamanlanmış senkron)", 16, D)
    # kimliksizlestirme notu
    s.rect(80, 600, 520, 80, Y, "#b7791f", 1.5, 8)
    s.lines(340, 630, ["HBYS'den alınan her kayıt uygulama içinde kimliksizleştirilir;", "kimlik alanları (ad, adres, TCKN) hiç saklanmaz."], 17, "#7a4f0e", lh=28)
    # cok merkezli not
    s.rect(80, 690, 1040, 140, W, L, 1.5, 10)
    s.text(100, 722, "Çok merkezli çalışmalarda", 21, L, "bold", "start")
    s.text(100, 754, "Her hastaneye bağımsız bir örnek kurulur (hasta havuzu ve BDM yerel kalır). Sponsor ve CRA, EBM merkezinden yalnızca", 18, D, anchor="start")
    s.text(100, 782, "kimliksizleştirilmiş çalışma verisine (eCRF, KRI, uyarılar, TMF) erişir; eşleştirme ekranları yalnız merkez araştırmacısına açıktır.", 18, D, anchor="start")
    s.text(100, 810, "Alternatif: SaaS modeli – uygulama EBM veri merkezinde, BDM ve hasta havuzu hastanede (hibrit).", 18, D, anchor="start")
    # dis: EBM merkezi
    s.rect(1220, 80, 340, 780, W, D, 2, 16)
    s.text(1390, 114, "Kurum dışı", 23, D, "bold")
    s.box(1250, 160, 280, 130, "EBM merkezi", ["proje yöneticisi, CRA,", "veri yöneticisi,", "farmakovijilans"], LB, L, 22, 17)
    s.box(1250, 330, 280, 110, "Sponsor", ["özet panolar,", "KRI ve kazanım raporları"], W, L, 22, 17)
    s.rect(1250, 480, 280, 120, W, L, 1.5, 8)
    s.lines(1390, 516, ["VPN / istemci sertifikası,", "iki faktörlü kimlik doğrulama,", "oturum 30 dk"], 17, D, lh=26)
    s.arrow(1248, 220, 1164, 220, D, 3)
    s.arrow(1248, 385, 1164, 385, D, 3)
    s.text(1206, 198, "HTTPS", 15, D)
    s.text(1206, 363, "HTTPS", 15, D)
    s.rect(1250, 630, 280, 200, "#f9e5e5", R, 2, 10)
    s.lines(1390, 672, ["Hasta verisi", "dış ağa çıkmaz", "", "Dışa aktarım yalnız", "kimliksizleştirilmiş", "OMOP / SDTM"], 19, R, "bold", lh=27)
    s.save("sekil_05_kurulum.svg")


for f in (sekil1, sekil2, sekil3, sekil4, sekil5):
    f()

out = Path("/home/user/EBM-Yaz-l-m/docs/tanitim/sekil")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
    pg = b.new_page(viewport={"width": 1700, "height": 1100}, device_scale_factor=2)
    for svg in sorted(Path(".").glob("sekil_*.svg")):
        pg.set_content("<html><body style='margin:0;background:#fff'>" + svg.read_text(encoding="utf-8") + "</body></html>")
        pg.locator("svg").screenshot(path=str(out / svg.with_suffix(".png").name))
        print(svg.name, "->", out / svg.with_suffix(".png").name)
    b.close()
