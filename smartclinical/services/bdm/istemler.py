"""Turkce Klinik BDM istem sablonlari.

Sablonlar ebm-klinik-tr modelinin talimat ince ayarinda kullanilan bicimle ayni;
degistirirken ml/egitim/talimat_sablonlari.py ile tutarli kalmali.
"""

SISTEM = (
    "Sen klinik araştırma uzmanlarına yardımcı olan bir asistansın. Türkçe klinik metinleri "
    "(epikriz, patoloji ve radyoloji raporları) okur, protokol kriterleriyle karşılaştırırsın. "
    "Sadece sana verilen metne dayanarak yanıt ver; metinde olmayan hiçbir bilgiyi varsayma. "
    "Emin değilsen 'belirsiz' yaz. Hasta kimliğine ilişkin hiçbir bilgi üretme. "
    "Yanıtını istenen JSON biçiminde, başka açıklama eklemeden ver."
)

KRITER_YAPILANDIR = """Aşağıdaki klinik araştırma kriterini hesaplanabilir bir sorguya dönüştür.

Kriter tipi: {tip}
Kriter: "{metin}"

Kategoriler: yas, cinsiyet, tani, lab, ilac, performans, gebelik, organ_fonksiyon, zaman, tedavi_gecmisi, serbest
Sorgu biçimi örnekleri:
  {{"alan": "yas", "op": ">=", "deger": 18}}
  {{"alan": "tani", "icd10": ["C50"], "terimler": ["meme kanseri"], "son_ay": null}}
  {{"alan": "lab", "loinc": "718-7", "ad": "hemoglobin", "op": ">=", "deger": 9, "birim": "g/dL"}}
  {{"alan": "performans", "olcek": "ecog", "op": "arasi", "deger": [0, 1]}}
  {{"ve": [ ... ]}}, {{"veya": [ ... ]}}, {{"degil": {{ ... }}}}

Yalnızca şu JSON'u döndür:
{{"kategori": "...", "sorgu": {{...}}, "guven": 0.0-1.0, "notlar": ["..."]}}"""

KANIT_CIKAR = """Hastanın klinik metninden alınan parçalar aşağıda numaralandırılmıştır. Verilen kriterin
bu hasta için sağlanıp sağlanmadığına yalnızca bu parçalara dayanarak karar ver.

Kriter: "{kriter}"

Parçalar:
{parcalar}

Kurallar:
- "kanit_cumlesi" alanına, kararını dayandırdığın cümleyi parçadan BİREBİR kopyala. Kendi cümleni yazma.
- Parçalarda yeterli bilgi yoksa sonuc "belirsiz" olsun ve kanit_cumlesi boş kalsın.
- "guven" 0 ile 1 arasında; emin değilsen düşük ver.

Yalnızca şu JSON'u döndür:
{{"sonuc": "saglandi" | "saglanmadi" | "belirsiz", "kanit_cumlesi": "...", "parca_indeks": 0, "guven": 0.0}}"""

KLINIK_OZET = """Aşağıdaki klinik metni, klinik araştırma ön taraması yapan bir uzman için en fazla 5 maddede özetle.
Tanılar, evre/alt tip, aktif tedaviler, önemli laboratuvar bulguları ve performans durumu öncelikli.
Kimlik bilgisi yazma.

Metin:
{metin}

Yalnızca şu JSON'u döndür:
{{"maddeler": ["...", "..."]}}"""

SORU_CEVAP = """Bağlam metnine dayanarak soruyu yanıtla. Bağlamda cevap yoksa "Verilen metinde bu bilgi yok." yaz.

Bağlam:
{baglam}

Soru: {soru}

Yalnızca şu JSON'u döndür:
{{"cevap": "...", "dayanak": "bağlamdan birebir alıntı veya boş", "guven": 0.0}}"""


def parcalari_bicimle(parcalar: list[str]) -> str:
    return "\n".join(f"[{i}] {p.strip()}" for i, p in enumerate(parcalar))

PROTOKOL_TASLAK = """Aşağıdaki klinik araştırma protokolü metninden çalışma tasarımı taslağı çıkar.
Yalnızca metinde açıkça yazanı kullan; tahmin etme. Her kriteri tek cümle olarak, metindeki ifadeye sadık yaz.

Vizitler için "gun" başlangıç (randomizasyon) gününe göre gün sayısıdır; tarama vizitleri negatif olur.
"pencere" vizit penceresi (± gün). Formlar için yalnızca şu kodları kullan:
DM (demografi), IE (uygunluk), VS (vital bulgular), LB (laboratuvar), EX (araştırma ürünü), CM (eşlik eden ilaçlar),
QS (ECOG / performans), ANKET (anket, ölçek).

Metin:
{metin}

Yalnızca şu JSON'u döndür:
{{"dahil": ["..."], "haric": ["..."], "kollar": ["..."], "vizitler": [{{"ad": "...", "gun": 0, "pencere": 0}}],
  "formlar": ["VS"], "guven": 0.0}}"""
