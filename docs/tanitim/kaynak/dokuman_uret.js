// EBM SmartClinical - Urun Tanitim Dokumani uretici
const fs = require("fs");
const path = require("path");
const D = require("docx");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, AlignmentType,
  ImageRun, PageBreak, TableOfContents, ShadingType, BorderStyle, LevelFormat, Footer, Header, PageNumber,
  VerticalAlign, TabStopType,
} = D;

// Kullanim: node dokuman_uret.js [cikti.docx]
const KOK = path.resolve(__dirname, "../../..");
const CIKTI = process.argv[2] || path.join(KOK, "docs/tanitim/EBM_SmartClinical_Tanitim_Dokumani.docx");
// Gorsel boyutlari PNG basligindan okunur (ekran/ ve sekil/ klasorleri)
const GORSEL = {};
for (const d of ["docs/tanitim/ekran", "docs/tanitim/sekil"]) {
  for (const ad of fs.readdirSync(path.join(KOK, d)).filter(x => x.endsWith(".png"))) {
    const yol = path.join(KOK, d, ad), b = fs.readFileSync(yol);
    GORSEL[ad] = { yol, w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
  }
}

const LACIVERT = "16325C", TURKUAZ = "0E8A8A", GRI = "595959", ACIK = "EEF2F8", ACIK_TURKUAZ = "E3F3F3", KENAR = "BFC5CF";
const FONT = "Calibri";
const SAYFA_GENISLIK = 11906, KENAR_BOSLUK = 1134; // A4, 2 cm
const ICERIK = SAYFA_GENISLIK - 2 * KENAR_BOSLUK; // 9638 DXA

// ---------------------------------------------------------------- yardimcilar
function run(metin, ops = {}) {
  return new TextRun({ text: metin, font: FONT, size: ops.size || 22, bold: ops.bold, italics: ops.italics, color: ops.color });
}
// **kalin** ve _italik_ isaretlemesini TextRun'lara cevirir
function parcala(metin, ops = {}) {
  const runs = [];
  const re = /(\*\*[^*]+\*\*|_[^_]+_)/g;
  let son = 0, m;
  while ((m = re.exec(metin)) !== null) {
    if (m.index > son) runs.push(run(metin.slice(son, m.index), ops));
    const t = m[0];
    if (t.startsWith("**")) runs.push(run(t.slice(2, -2), { ...ops, bold: true }));
    else runs.push(run(t.slice(1, -1), { ...ops, italics: true }));
    son = m.index + t.length;
  }
  if (son < metin.length) runs.push(run(metin.slice(son), ops));
  return runs;
}
function P(metin, ops = {}) {
  return new Paragraph({
    children: parcala(metin, ops), spacing: { after: ops.after ?? 120, line: 276 },
    alignment: ops.hizala || AlignmentType.JUSTIFIED, keepNext: ops.keepNext,
  });
}
function H1(metin) { return new Paragraph({ text: metin, heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 160 }, pageBreakBefore: true }); }
function H2(metin) { return new Paragraph({ text: metin, heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 120 } }); }
function H3(metin) { return new Paragraph({ text: metin, heading: HeadingLevel.HEADING_3, spacing: { before: 200, after: 80 } }); }
function madde(metin, seviye = 0) {
  return new Paragraph({ children: parcala(metin), numbering: { reference: "madde", level: seviye }, spacing: { after: 60, line: 264 }, alignment: AlignmentType.LEFT });
}
function sira(metin, seviye = 0) {
  return new Paragraph({ children: parcala(metin), numbering: { reference: "sira", level: seviye }, spacing: { after: 60, line: 264 }, alignment: AlignmentType.LEFT });
}
function not(metin) {
  return new Paragraph({
    children: parcala(metin, { size: 19, color: GRI }), spacing: { before: 60, after: 160 },
    indent: { left: 360 }, border: { left: { style: BorderStyle.SINGLE, size: 12, color: TURKUAZ, space: 8 } },
  });
}
function hucre(icerik, ops = {}) {
  const children = Array.isArray(icerik) ? icerik : [new Paragraph({ children: parcala(String(icerik), { size: ops.size || 19, bold: ops.bold, color: ops.color }), spacing: { after: 0, line: 252 }, alignment: ops.hizala || AlignmentType.LEFT })];
  return new TableCell({
    children, width: { size: ops.genislik, type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
    shading: ops.zemin ? { type: ShadingType.CLEAR, fill: ops.zemin, color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 90, right: 90 },
    borders: { top: { style: BorderStyle.SINGLE, size: 4, color: KENAR }, bottom: { style: BorderStyle.SINGLE, size: 4, color: KENAR },
               left: { style: BorderStyle.SINGLE, size: 4, color: KENAR }, right: { style: BorderStyle.SINGLE, size: 4, color: KENAR } },
  });
}
function tablo(baslik, satirlar, oranlar, ops = {}) {
  const toplam = oranlar.reduce((a, b) => a + b, 0);
  const genislikler = oranlar.map(o => Math.round(ICERIK * o / toplam));
  const rows = [new TableRow({
    tableHeader: true,
    children: baslik.map((b, i) => hucre(b, { genislik: genislikler[i], bold: true, zemin: LACIVERT, color: "FFFFFF", size: 19 })),
  })];
  satirlar.forEach((s, r) => rows.push(new TableRow({
    children: s.map((h, i) => hucre(h, { genislik: genislikler[i], zemin: r % 2 ? ACIK : undefined, hizala: ops.sayisal && ops.sayisal.includes(i) ? AlignmentType.RIGHT : AlignmentType.LEFT })),
  })));
  return [new Table({ rows, columnWidths: genislikler, width: { size: ICERIK, type: WidthType.DXA } }), new Paragraph({ spacing: { after: 120 } })];
}
let sekilNo = 0;
function sekil(ad, altyazi, maksGenislikInch = 6.5) {
  const g = GORSEL[ad];
  if (!g) throw new Error("gorsel yok: " + ad);
  const dpi = 96;
  let w = maksGenislikInch * dpi, h = w * g.h / g.w;
  const maksYukseklik = 8.2 * dpi;
  if (h > maksYukseklik) { h = maksYukseklik; w = h * g.w / g.h; }
  sekilNo += 1;
  return [
    new Paragraph({
      children: [new ImageRun({ type: "png", data: fs.readFileSync(g.yol), transformation: { width: Math.round(w), height: Math.round(h) } })],
      alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
    }),
    new Paragraph({ children: [run(`Şekil ${sekilNo}. ${altyazi}`, { size: 18, italics: true, color: GRI })], alignment: AlignmentType.CENTER, spacing: { after: 200 } }),
  ];
}
function bosluk(n = 1) { return Array.from({ length: n }, () => new Paragraph({ spacing: { after: 120 } })); }

// ---------------------------------------------------------------- icerik
const icerik = [];
const ekle = (...x) => x.flat().forEach(e => icerik.push(e));
// Her ana bolumun basinda uzman olmayan okuyucu icin sade bir ozet kutusu
function kisaca(metin) {
  return new Paragraph({
    children: [run("Kısaca: ", { size: 20, bold: true, color: TURKUAZ }), ...parcala(metin, { size: 20, color: "3D4350" })],
    spacing: { before: 40, after: 200, line: 264 },
    shading: { type: ShadingType.CLEAR, fill: ACIK_TURKUAZ, color: "auto" },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: TURKUAZ, space: 8 } },
    indent: { left: 200, right: 200 },
  });
}
let BENCH = null;
try { BENCH = JSON.parse(fs.readFileSync(path.join(__dirname, "bench_ozet.json"), "utf8")); } catch (e) { BENCH = null; }

// Kapak
ekle(...bosluk(6));
ekle(new Paragraph({ children: [run("EBM SmartClinical", { size: 56, bold: true, color: LACIVERT })], alignment: AlignmentType.LEFT, spacing: { after: 120 } }));
ekle(new Paragraph({ children: [run("Klinik Araştırma Yönetimi ve Türkçe Klinik Karar Destek Platformu", { size: 30, color: TURKUAZ })], spacing: { after: 600 } }));
ekle(new Paragraph({ children: [run("Ürün Tanıtım, Teknik Özet ve Yatırım Dokümanı", { size: 26, bold: true })], spacing: { after: 120 } }));
ekle(...bosluk(6));
ekle(new Paragraph({ children: [run("Hazırlayan: EBM Klinik Araştırma Hizmetleri – Yazılım ve Veri Bilimi Ekibi", { size: 20 })], spacing: { after: 60 } }));
ekle(new Paragraph({ children: [run("Yatırımcı ve iş ortağı sunumu için hazırlanmıştır", { size: 20 })], spacing: { after: 60 } }));
ekle(new Paragraph({ children: [run("Gizlilik: Bu doküman EBM'nin ticari ve teknik bilgilerini içerir; yalnızca değerlendirme amacıyla paylaşılmıştır.", { size: 18, italics: true, color: GRI })], spacing: { after: 0 } }));

// Okumadan once
ekle(new Paragraph({ children: [run("Okumadan önce", { size: 24, bold: true, color: LACIVERT })], pageBreakBefore: true, spacing: { after: 160 } }));
ekle(P("Bu dokümandaki ekran görüntüleri ürünün CRO kullanım modundaki demo kurulumundan alınmıştır. Demo kurulumunda kullanılan tüm hasta kayıtları, çalışma ve merkez verileri sentetiktir; merkez adları kurgusaldır ve gerçek bir kurumu temsil etmez. Bölüm 9'daki ölçümler, aksi belirtilmedikçe, ürünle gelen değerlendirme aracının (ml/degerlendirme) aynı demo verisi ve örnek değerlendirme setleri üzerindeki çıktısıdır. Bölüm 12 ve 13'teki fiyat, hacim ve etki rakamları varsayımlara dayalı planlama değerleridir, taahhüt değildir; her birinin varsayımı yanında belirtilmiştir."));
ekle(P("Terimler: **BDM** büyük dil modeli; **HBYS** hastane bilgi yönetim sistemi; **eCRF** elektronik olgu rapor formu; **CRA** klinik araştırma uzmanı (monitör); **KRI/QTL** anahtar risk göstergesi / kalite tolerans limiti; **TMF** çalışma ana dosyası; **SDV** kaynak veri doğrulama; **RAG** erişim destekli üretim; **THS** teknoloji hazırlık seviyesi; **LoRA** düşük sıralı uyarlama (parametre verimli ince ayar)."));

ekle(new Paragraph({ children: [run("İçindekiler", { size: 24, bold: true, color: LACIVERT })], pageBreakBefore: true, spacing: { after: 160 } }));
ekle(new TableOfContents("İçindekiler", { hyperlink: true, headingStyleRange: "1-2" }));

// Bir sayfada
ekle(H1("Bir sayfada EBM SmartClinical"));
ekle(...tablo(["Başlık", "Özet"], [
  ["Ne", "Klinik araştırmanın tasarımdan arşive tüm yaşam döngüsünü yöneten platform + hastane içinde çalışan Türkçe Klinik BDM ile üç karar destek işlevi: hasta ön tarama, merkez seçimi/kazanım tahmini, risk bazlı izlem"],
  ["Kim için", "Sponsorlar (yerli ilaç, biyobenzer, cihaz, IVD), CRO/SMO'lar, araştırma hastaneleri ve üniversiteler, araştırmacılar; dolaylı olarak hastalar ve düzenleyici kurumlar"],
  ["Mevcut durum", "Çekirdek platform geliştirildi ve otomatik testlerle doğrulandı, pilot kullanıma hazır (THS 5–6); yapay zekâ katmanı laboratuvar ortamında sentetik veriyle sınandı (THS 4); validasyon dosyası hazır"],
  ["Ölçülebilir hedefler", "Eşleştirme duyarlılığı ≥ %90 (kural tabanlı taban %77); halüsinasyon ≤ %2 (mevcut %0); MAPE ≤ %25 (mevcut %34); AUC ≥ 0,80 (mevcut 0,79); ön tarama süresinde ≥ %50 azalma"],
  ["Açık bileşen stratejisi", "TR-KlinikBench açık değerlendirme seti; federe model güncelleme protokolü; model ve veri kartları: benimsemeyi hızlandıran ve rakiplerin kopyalayamayacağı veri varlığını büyüten ekosistem yaklaşımı"],
  ["Ticarileşme", "Beş lisans sınıfı; EBM'nin CRO/SMO ağı üzerinden ilk kullanıcılara doğrudan erişim; pilot merkezlerde gölge mod doğrulaması; merkez performans endeksi ile büyüyen veri varlığı"],
  ["Neden şimdi", "ICH E6(R3) risk temelli izlemi zorunlu kılıyor; yerli ürün dalgası klinik doğrulama talebini artırıyor; KVKK yurt dışı bulut çözümlerini dışlıyor; açık kaynak Türkçe temel modeller yeterli olgunluğa ulaştı"],
  ["Yatırımın kullanımı", "18 aylık Ar-Ge programı: Türkçe Klinik BDM eğitimi, üç hastanede prospektif gölge mod doğrulaması, açık değerlendirme setinin oluşturulması, ilk ticari kurulumlar ve THS 7 ürün (bütçe ayrı sunulur)"],
], [1.6, 6.2]));


// Uzman olmayanlar icin
ekle(H1("SmartClinical'ı beş dakikada anlamak"));
ekle(P("Bu bölüm, klinik araştırma alanında çalışmayan okuyucular içindir. Teknik ayrıntılar sonraki bölümlerdedir."));
ekle(H2("Klinik araştırma nedir, neden gecikir?"));
ekle(P("Yeni bir ilaç, aşı ya da tıbbi cihaz hastalara sunulmadan önce gerçek hastalar üzerinde güvenli ve etkili olduğunun kanıtlanması gerekir. Buna klinik araştırma denir. Bir araştırma için önce uygun hastaların bulunması, sonra bu hastaların tedavi edilip düzenli kontrollerle izlenmesi ve her adımın kurallara uygun kaydedilmesi gerekir. Araştırmalar genellikle birkaç hastanede birden yürütülür."));
ekle(P("Pratikte araştırmalar çoğunlukla planlanandan geç biter. Üç neden öne çıkar. Birincisi, araştırmaya uygun hastalar hastanenin kayıtlarında vardır ama bu bilgi tablolarda değil, doktorların yazdığı Türkçe raporların içindedir; bir koordinatör her hastanın dosyasını tek tek okumak zorunda kalır. İkincisi, hangi hastanenin kaç hasta kazandıracağı tahminle belirlenir ve tahmin çoğu zaman iyimser çıkar. Üçüncüsü, eksik veri, geciken bildirim gibi sorunlar ancak bir uzman hastaneyi ziyaret ettiğinde, yani haftalar sonra görülür. Her ay gecikme hem büyük bir maliyet hem de hastaların yeni tedaviye geç ulaşması demektir."));
ekle(H2("SmartClinical ne yapar?"));
ekle(P("SmartClinical, araştırmanın bütün adımlarını tek bir yazılımda toplar ve bunun üzerine üç akıllı yardımcı ekler:"));
ekle(madde("**Doğru hastayı bulur.** Hastane kayıtlarındaki Türkçe raporları okur, araştırmanın koşullarına uyan hastaları listeler ve her öneri için \"neden uygun?\" sorusuna raporun kendi cümlesiyle cevap verir. Son kararı her zaman doktor verir."));
ekle(madde("**Doğru hastaneyi seçer.** Geçmiş araştırmalardan öğrenerek hangi hastanenin ne kadar sürede başlayabileceğini ve kaç hasta kazandıracağını tahmin eder; tahminin gerekçesini açıkça yazar."));
ekle(madde("**Sorunu büyümeden gösterir.** Her hastaneyi sürekli izler; geciken bildirimler, eksik veriler veya kurallara uymayan işlemler bir uyarı ve açıklamasıyla ekibin önüne düşer."));
ekle(H2("Yapay zekâya neden güvenebilirsiniz?"));
ekle(P("Dört ilke uygulanır. Hasta verisi hastaneden dışarı çıkmaz; yazılım ve yapay zekâ hastanenin kendi sunucusunda çalışır. Yapay zekâ bir şey söylediğinde kaynağını göstermek zorundadır; kaynak bulamazsa \"belirsiz\" der, uydurmaz. Yapay zekâ önerir, karar insanın elindedir ve her karar gerekçesiyle silinemez biçimde kaydedilir. Yapay zekâ sunucusu çalışmasa bile sistem durmaz; daha basit bir yöntemle devam eder ve bunu kayda geçirir."));
ekle(H2("Bugün ne durumda, Ar-Ge programıyla ne olacak?"));
ekle(P("Yazılımın araştırma yönetimi, hasta formları, yan etki takibi ve belge arşivi gibi temel kısımları geliştirilmiş, otomatik testlerle ve bir demo ortamında doğrulanmıştır; ilk gerçek kullanım EBM'nin yürüteceği çalışmalarda ve pilot hastanelerde olacaktır. Yapay zekâ kısmı laboratuvarda, yapay veriyle sınanmıştır ve hedeflere yakın sonuçlar vermektedir; gerçek hastane verisiyle kanıtlanması Ar-Ge programının işidir. Program sonunda Türkçe tıbbi metinleri anlayan bir yapay zekâ modeli, üç hastanede doğrulanmış bir ürün ve başka kurumların da kullanabileceği açık test setleri ortaya çıkacaktır."));
ekle(H2("Bu dokümanı nasıl okumalı?"));
ekle(P("Karar vericiler için: Bölüm 1 (yönetici özeti), Bölüm 9 (bugünkü durum ve ölçümler), Bölüm 12 (iş modeli) ve Bölüm 13 (etki). Teknik değerlendiriciler için: Bölüm 5–8 ve 10. Her ana bölümün başındaki \"Kısaca\" kutusu, bölümün sade bir özetidir."));

// 1 Yonetici ozeti
ekle(H1("1. Yönetici özeti"));
ekle(kisaca("SmartClinical, klinik araştırmaları baştan sona yöneten ve Türkçe hasta raporlarını okuyabilen bir yapay zekâ ile uygun hastayı bulan, doğru hastaneyi seçen ve sorunları erken gösteren yerli bir yazılımdır. Temel kısmı geliştirilmiş ve test edilmiştir, yapay zekâ kısmı doğrulama aşamasındadır."));
ekle(P("EBM SmartClinical, bir klinik araştırmanın tasarımından arşivine kadar bütün adımlarını tek bir platformda yönetir. Bunun üzerine, hastanenin kendi sunucusunda çalışan ve Türkçe hasta raporlarını anlayan bir yapay zekâ modeliyle üç karar desteği ekler: araştırmaya uygun hastaların otomatik ön taranması, hangi hastanenin ne kadar hasta kazandıracağının öngörülmesi ve yürütme sırasındaki risklerin erken tespiti."));
ekle(P("Ürün, EBM'nin klinik araştırma yürütme ve hastane yönetimi hizmetlerinde yaşadığı gerçek ihtiyaçlardan doğmuştur. Çalışma kurulumu ve tasarımı, kod yazmadan form hazırlama, hasta formları, randomizasyon, yan etki bildirimi, izlem ziyaretleri, belge arşivi, ön analiz, denetim izi ve elektronik imza gibi temel modüller geliştirilmiş, otomatik testlerle ve demo ortamında doğrulanmış olup pilot kullanıma hazırdır. Yapay zekâ katmanı (Türkçe klinik model, hasta eşleştirme, hastane seçimi ve risk izleme modelleri) platforma eklenmiş ve laboratuvar ortamında yapay veriyle sınanmıştır. Gerçek hastane ortamında ileriye dönük doğrulama, yatırımın finanse edeceği 18 aylık Ar-Ge programında yapılacaktır."));
ekle(P("Ürün iki katmanlı bir yapıya sahiptir. **Açık bileşen katmanı**, Türkçe klinik model geliştirme ve değerlendirmesi için herkese açık yapı taşlarını içerir: TR-KlinikBench değerlendirme seti, veri kurum dışına çıkmadan model iyileştirmeyi sağlayan federe LoRA güncelleme protokolü, model ve veri kartları, kimliksizleştirme aracı ve standart veri eşlemeleri. **Ticari ürün katmanı**, bu altyapıyı kullanan klinik araştırma platformudur. Bu ayrım, açık bileşenlerin hastaneler ve araştırmacılar tarafından benimsenerek ürünün etrafında bir ekosistem oluşturmasını, ticari ürünün ise bu bileşenlerin sürdürülmesini finanse etmesini sağlar (Bölüm 3)."));
ekle(P("Platformun ayırt edici özellikleri şunlardır:"));
ekle(madde("**Uçtan uca kapsam.** İlaç, biyobenzer, tıbbi cihaz, in vitro tanı, gözlemsel, kayıt (gerçek yaşam verisi) ve araştırmacı başlatımlı çalışmalar aynı veri modeli ve aynı akışla yönetilir; CRO, üniversite ve tekil araştırmacı için ayrı kullanım modları vardır."));
ekle(madde("**Türkçe klinik metni anlayan, hastane içinde çalışan yapay zekâ.** Epikriz, patoloji ve radyoloji raporları kimliksizleştirilir, protokol kriterleri hesaplanabilir sorguya dönüştürülür ve her öneri kaynak cümlesiyle sunulur. Hasta verisi kurum dışına çıkmaz."));
ekle(madde("**İnsan kararı merkezde.** Hiçbir model çıktısı tek başına işlem yapmaz; her karar gerekçesiyle denetim izine yazılır."));
ekle(madde("**Düzenleyici uyum tasarımın parçası.** ICH E6(R3), 21 CFR Part 11 / EU Annex 11, KVKK ve DIA TMF referans modeli ürünün içinde uygulanır; bilgisayarlı sistem validasyon dosyası ürünle birlikte teslim edilir."));
ekle(madde("**Ölçülebilir Ar-Ge ve ağ etkisi.** Model performansı ürünle gelen değerlendirme aracı ve gölge mod raporuyla tekrarlanabilir biçimde ölçülür; merkez performans endeksi her yeni çalışmayla kuvvetlenen, kurumlar arası anonim bir kıyaslama varlığı oluşturur."));
ekle(P("Bu doküman ürünün mevcut durumunu, stratejik konumlandırmasını, teknik mimarisini, uyum yaklaşımını, olgunluk durumunu ve ölçüm sonuçlarını, iş birliği ve yönetişim yapısını, iş modelini ve etki projeksiyonunu yatırımcılara ve potansiyel iş ortaklarına sunmak amacıyla hazırlanmıştır."));

// 2 Problem ve firsat
ekle(H1("2. Problem tanımı ve fırsat"));
ekle(kisaca("Klinik araştırmalar üç nedenle gecikir: uygun hasta bulunamaz, yanlış hastane seçilir, sorunlar geç fark edilir. Yabancı yazılımlar Türkçe raporları okuyamaz ve hasta verisini yurt dışına taşımak ister; bu yüzden Türkiye'de kullanılamaz. Şimdi doğru zaman, çünkü hem kurallar hem teknoloji değişti."));
ekle(H2("2.1 Üç yapısal darboğaz"));
ekle(sira("**Uygun hastalar görünmez kalıyor.** Protokol kriterlerini karşılayan hastalar HBYS'de yapılandırılmış alanlarda değil, Türkçe serbest metin raporlarda tanımlıdır. Koordinatörler dosyaları elle tarar; bu hem yavaştır hem de kriter anlaşılmasına bağlı tutarsızlık üretir."));
ekle(sira("**Merkez seçimi deneyime dayalı.** Fizibilite anketleri öz beyana dayanır; gerçekleşen kazanım ile beyan arasındaki fark takvimi kaydırır. Etik kurul, TİTCK ve sözleşme gecikmeleri ancak gerçekleştikten sonra fark edilir."));
ekle(sira("**Riskler geç görülüyor.** Veri kalitesi, protokol sapması ve güvenlik bildirim sorunları çoğunlukla yerinde ziyaretlerde, olaydan haftalar sonra saptanır."));
ekle(H2("2.2 Mevcut çözümlerin sınırı"));
ekle(P("Piyasadaki klinik araştırma yönetim ve hasta eşleştirme çözümleri büyük ölçüde yurt dışı kaynaklı, İngilizce odaklı ve bulut tabanlıdır. Türkçe klinik metni işleyemezler, hastane verisinin kurum dışına çıkmasını gerektirirler ve bu nedenle KVKK çerçevesinde Türkiye'deki hastanelerde uygulanamazlar. Lisans maliyetleri yurt içi akademik ve araştırmacı başlatımlı çalışmalar için erişilebilir değildir. Yerel araçlar ise çoğunlukla yalnızca veri toplama (EDC) ile sınırlıdır."));
ekle(H2("2.3 Neden şimdi"));
ekle(...tablo(["Etken", "Sonuç"], [
  ["ICH E6(R3) risk temelli kalite yönetimini ve merkezi izlemi standart haline getirdi", "Sponsorlar ve CRO'lar KRI/QTL tabanlı izlem araçlarına geçmek zorunda; mevcut Türkçe çözüm yok"],
  ["Yerli ilaç, biyobenzer, tıbbi cihaz ve IVD ürün dalgası (kamu teşvikleri ve sanayi yatırımları)", "Klinik doğrulama kapasitesi ürünleşmenin darboğazı; hızlı ve ucuz çalışma yürütme talebi artıyor"],
  ["KVKK ve Kişisel Sağlık Verileri Yönetmeliği uygulaması sıkılaştı", "Bulut tabanlı yabancı çözümler hastane verisine erişemiyor; hastane içi çözüm zorunlu"],
  ["Açık kaynak 7–8B temel modeller Türkçe için yeterli olgunluğa ulaştı; nicemlenmiş modeller tek GPU'da çalışıyor", "Hastane içinde çalışan Türkçe klinik BDM teknik olarak uygulanabilir ve ekonomik hale geldi"],
  ["HL7 FHIR R4 HBYS üreticileri tarafından benimsenmeye başladı (e-Nabız entegrasyonları)", "Standart tabanlı hasta havuzu erişimi mümkün; CSV yolu geçiş dönemini kapatıyor"],
], [3.4, 4.4]));

// 3 Stratejik konumlandirma
ekle(H1("3. Stratejik konumlandırma: açık bileşenler ve ticari ürün"));
ekle(kisaca("Ürünün bazı yapı taşları (test seti, model kartları, hastaneler arası ortak öğrenme protokolü) herkese açık olacak; bu, hastanelerin güvenini ve benimsemeyi hızlandırır. Ürünün kendisi ticaridir ve açık kısmın bakımını finanse eder."));
ekle(P("Ürün, açık bileşenler ile ticari çekirdek arasındaki sınırı baştan tanımlar. Açık bileşenler, hastanelerin ve araştırmacıların güvenini kazanarak benimsemeyi hızlandırır ve Türkçe klinik yapay zekâda referans olma konumu yaratır; ticari çekirdek gelir üretir ve açık bileşenlerin sürdürülmesini finanse eder."));
ekle(...tablo(["Katman", "Bileşen", "Erişim", "Sürdürme"], [
  ["Açık bileşen", "TR-KlinikBench: Türkçe klinik araştırma NLP değerlendirme seti (6 görev, şemalar, skor tablosu, etiketleme kılavuzu)", "Açık (CC BY-NC-SA 4.0 planı); sentetik ve etik onaylı kimliksizleştirilmiş veri", "EBM + konsorsiyum; yıllık sürüm"],
  ["Açık bileşen", "Federe LoRA güncelleme protokolü ve toplayıcı iskeleti", "Açık kaynak (Apache 2.0 planı)", "EBM; akademik katkı"],
  ["Açık bileşen", "Model ve veri kartları, etiketleme şeması, değerlendirme betikleri", "Açık", "Her model sürümüyle güncellenir"],
  ["Lisanslı bileşen", "Türkçe Klinik BDM ağırlıkları (ebm-klinik-tr)", "Hastane ve üniversitelere araştırma lisansı; ticari kullanım lisansla", "EBM; federe turlarla iyileştirme"],
  ["Lisanslı bileşen", "Kimliksizleştirme aracı, FHIR/OMOP eşlemeleri, klinik NLP servis API'si", "Bileşen lisansı; HBYS üreticilerine OEM", "EBM"],
  ["Ticari ürün (kapalı)", "SmartClinical platformu (çalışma yönetimi ve tasarımı, eCRF, RBM, merkez zekâsı, sponsor görünümü, TMF, ön analiz)", "Lisans sınıfları (Bölüm 12)", "EBM ürün ekibi"],
], [1.7, 3.1, 1.8, 1.2]));
ekle(P("Bu yapı üç soruya aynı anda cevap verir: hastaneler için \"verimi dışarı vermeden faydalanabilir miyim?\" (evet, federe protokol ve hastane içi kurulum); yatırımcı için \"savunulabilir bir konum var mı?\" (evet, açık bileşenler referans konumu ve veri varlığını büyütür, ticari çekirdek geliri üretir); EBM için \"bu altyapıyı kim sürdürecek?\" (ticari ürün gelirleri)."));

// 4 Urun genel bakis
ekle(H1("4. Ürüne genel bakış"));
ekle(kisaca("SmartClinical, bir klinik araştırmanın başından sonuna kadar her adımını tek yerde yönetir; her türden araştırma için çalışır ve her kullanıcı yalnızca kendi işine ait ekranları görür."));
ekle(H2("4.1 Kapsam ve desteklenen çalışma türleri"));
ekle(P("Platform, çalışma türünden bağımsız ortak bir veri modeli üzerine kuruludur. Seçilen tür; başvuru kurumlarını ve şablonlarını, varsayılan risk göstergelerini, güvenlik bildirim kurallarını ve eCRF şablon setini belirler."));
ekle(...tablo(["Çalışma türü", "Örnek", "Türe özgü davranış"], [
  ["İlaç (Faz I–IV)", "Onkoloji faz III, biyoeşdeğerlik", "TİTCK klinik araştırma başvurusu, SUSAR hızlandırılmış bildirim, CTCAE derecelendirme, randomizasyon kolları"],
  ["Biyobenzer", "İnsülin glargin karşılaştırma", "Non-inferiorite tasarımı, referans ürün kolu, immünojenisite formları"],
  ["Tıbbi cihaz", "Koroner stent pivotal", "Cihaz olumsuz olay sınıflaması, tek kollu / tarihsel kontrol tasarımı, kullanım hatası kaydı"],
  ["In vitro tanı (IVD)", "HPV genotipleme performansı", "Örnek bazlı kayıt, referans yöntem karşılaştırması"],
  ["Gözlemsel / kayıt (RWE)", "KOAH gerçek yaşam kaydı", "Girişimsel olmayan başvuru yolu, azaltılmış eCRF, yüksek hacimli kayıt"],
  ["Araştırmacı başlatımlı", "Üniversite faz IV güvenlik", "Tek merkez akışı, sadeleştirilmiş TMF, akademik lisans sınıfı"],
  ["İleri tedavi (ATMP)", "Hücre/gen tedavisi", "Uzun dönem takip vizit şablonu; ürün zinciri kayıtları yol haritasında"],
], [1.6, 1.8, 4.4]));
ekle(H2("4.2 Kullanıcı rolleri"));
ekle(P("Erişim on rol üzerinden ince taneli izinlerle yönetilir. Araştırmacı ve koordinatör yalnızca kendi merkezinin kayıtlarını görür; proje ekibindeki roller yalnızca atandıkları çalışmaları görür (çalışma ekibi, Bölüm 6.7); sponsor ve denetçi rolleri kimliksizleştirilmiş özet verilere salt okunur erişir; makine-makine entegrasyonlar API anahtarıyla, anahtar sahibinin rol izinleri dahilinde çalışır. Hangi rolün çalışmayı kurduğu kullanım moduna göre değişir: tekil ve üniversite modunda araştırmacı, CRO modunda proje yöneticisi."));
ekle(...tablo(["Rol", "Başlıca işlevler"], [
  ["Araştırmacı", "Eşleştirme önerilerini inceleme ve onaylama, onam, randomizasyon, advers olay bildirimi, kriter onayı, araştırmacı (PI) imzası; tekil ve üniversite modunda çalışma kurulumu"],
  ["Çalışma koordinatörü", "Gönüllü kaydı, vizit takvimi, eCRF veri girişi, sorgu cevaplama, CSV ile hasta havuzu yükleme"],
  ["CRA (monitör)", "Risk bazlı izlem panosu, uyarı yönetimi, SDV, sorgu açma, ziyaret planlama, ziyaret raporu ve bulgular"],
  ["Proje yöneticisi", "Sihirbazla çalışma kurulumu, tasarım, çalışma ekibi, merkez seçimi, başvuru takibi, aşama geçişleri, ziyaret raporu onayı, fizibilite raporu"],
  ["Veri yöneticisi", "eCRF tasarımı, toplu kilit ve gerekçeli kilit açma, randomizasyon listesi, CDISC ODM / CSV / OMOP dışa aktarım"],
  ["Farmakovijilans", "SAE/SUSAR değerlendirme, TİTCK ve etik kurul bildirim takibi"],
  ["Biyoistatistikçi", "Ön analiz ve Tablo 1, kilitli veri setlerine erişim, analiz veri seti dışa aktarımı"],
  ["Sponsor", "Genel Bakış'ta kendi kurumunun çalışmalarına ait salt okunur özet: ilerleme, takvim riski, uyarılar, fizibilite raporu; anonim merkez endeksi"],
  ["Denetçi / gözlemci", "Denetim izi, e-imza kayıtları, TMF (salt okunur)"],
  ["Sistem yöneticisi", "İlk kurulum ve kullanım modu, kullanıcı ve rol yönetimi, API anahtarları, sistem durumu, BDM yapılandırması, zincir doğrulama"],
], [1.8, 6]));
ekle(H2("4.3 Klinik araştırma yaşam döngüsü"));
ekle(P("Her çalışma dokuz aşamalı bir yaşam döngüsü üzerinde ilerler. Aşama geçişleri proje yöneticisi tarafından gerekçeyle yapılır; her aşamanın kontrol listesi platform tarafından izlenir."));
ekle(...sekil("sekil_02_yasam_dongusu.png", "Klinik araştırma yaşam döngüsü ve platform işlevleri"));

// 5 Mimari
ekle(H1("5. Platform mimarisi"));
ekle(kisaca("Sistem hastanenin kendi sunucusuna kurulur, internet gerektirmez; hasta verisi dışarı çıkmaz. Yapay zekâ ayrı bir sunucuda çalışır, o sunucu yoksa sistem yine çalışır."));
ekle(H2("5.1 Katmanlı yapı"));
ekle(P("SmartClinical, hastane bilgi işlem ekiplerinin işletebileceği sadelikte tasarlanmış modüler bir mimariye sahiptir. Uygulama tek bir sunucu süreci olarak çalışır; yalnızca GPU gerektiren bileşenler (BDM ve gömme sunucusu) ayrı servislerdir."));
ekle(...sekil("sekil_01_mimari.png", "Platform mimarisi"));
ekle(...tablo(["Katman", "Bileşenler", "Teknoloji"], [
  ["Sunum", "Rol bazlı web panelleri, sponsor özet görünümü, yazdırılabilir raporlar, REST API v1 (oturum veya API anahtarı), OpenAPI belgeleri", "Sunucu tarafı render (Jinja2), harici JavaScript kütüphanesi yok (kapalı ağ uyumu)"],
  ["Uygulama", "Çalışma, sihirbaz ve tasarım, merkez, başvuru, eşleştirme, eCRF, randomizasyon, güvenlik, RBM, izlem, TMF, analiz, kıyaslama modülleri", "Python 3.11+, FastAPI, SQLAlchemy 2.0"],
  ["Yapay zekâ", "Türkçe Klinik BDM istemcisi, kriter motoru, RAG, kalıp tabanlı metin değerlendirme, koruma katmanı, kimliksizleştirme, merkez zekâsı, KRI/anomali motoru", "NumPy/SciPy; BDM: vLLM / llama.cpp / Ollama; LoRA eğitim ve federe toplayıcı (ml/)"],
  ["Çapraz kesen", "Zincirli denetim izi, e-imza, RBAC, API anahtarı, ortak veri modeli", "PBKDF2-SHA256 parola, SHA-256 zincir ve anahtar özeti, FHIR R4 / OMOP CDM v5.4"],
  ["Veri ve entegrasyon", "İşlem veritabanı, TMF dosya deposu, HBYS FHIR adaptörü, CSV hasta havuzu yükleme, dışa aktarım", "PostgreSQL 16 (geliştirmede SQLite), CDISC ODM 1.3.2, CSV, OMOP CSV"],
], [1.4, 3.6, 3]));
ekle(H2("5.2 Hastane içi kurulum ve entegrasyon yolları"));
ekle(P("Platform hastane ağı içinde kurulacak şekilde paketlenmiştir: Docker Compose veya systemd ile kurulum, nginx üzerinden TLS, PostgreSQL ve dosya deposu için yedekleme betikleri, denetim izi tablolarında güncelleme ve silmeyi engelleyen veritabanı yetkileri. BDM, hastanedeki GPU sunucusunda nicemlenmiş olarak çalışır; GPU bulunmayan kurulumlarda llama.cpp ile CPU üzerinde daha düşük hızda ya da tamamen kural tabanlı modda çalışabilir."));
ekle(P("Hasta havuzuna erişim için iki yol vardır. **FHIR R4** yolu HBYS'nin FHIR uç noktasından tanı kodlarına göre hasta çeker, kimlik alanlarını hiç okumaz ve metinleri kimliksizleştirir. **CSV** yolu, FHIR uç noktası bulunmayan hastaneler için HBYS'den alınan dökümün yüklenmesini sağlar; kimlik alanı yazılmaz, HBYS kimliği takma ada çevrilir, kimliksizleştirme ikinci geçişinde şüpheli kalıp kalan satırlar reddedilir. Bu ikinci yol, entegrasyon projesi beklemeden pilot başlatmayı mümkün kılar ve satış döngüsünü kısaltır."));
ekle(...sekil("sekil_05_kurulum.png", "Hastane içi kurulum topolojisi", 6.2));

// 6 Moduller
ekle(H1("6. Modüller"));
ekle(kisaca("Bu bölüm her ekranın ne işe yaradığını anlatır: kurulum ve çalışma tasarımı, hasta bulma, hasta kaydı ve formlar, yan etki bildirimi, hastane seçimi, risk izleme, ziyaretler, belge arşivi, ilk analizler ve her şeyin kayıt altında tutulması."));
ekle(P("Bu bölümde her modülün işlevi ve ekran görüntüleri verilmektedir. Ekranlar CRO kullanım modundaki demo kurulumundan alınmıştır; veriler sentetiktir."));
ekle(H2("6.1 Kullanım modları ve ilk kurulum"));
ekle(P("Aynı yazılım üç farklı kurum tipine göre çalışır: **CRO / sponsor** (çok merkezli, sponsorlu çalışmalar; tam menü), **üniversite / hastane** (bölümler ve araştırmacılar tek kurum çatısı altında; kurum izni ve etik kurul takibi) ve **tekil araştırmacı** (tek merkezde kendi çalışmasını yürüten araştırmacı; en sade menü). Mod, ilk açılışta kurulum ekranında kurum adı ve yönetici hesabıyla birlikte seçilir ve sonradan Ayarlar sayfasından değiştirilebilir. Mod yalnızca menüyü, sihirbaz varsayılanlarını ve yeni kayıtları etkiler; yetkiler her modda rol bazlıdır."));
ekle(...sekil("32_kurulum.png", "İlk kurulum: kullanım modu, kurum ve yönetici hesabı", 5.6));
ekle(H2("6.2 Genel bakış ve çalışma yönetimi"));
ekle(P("Genel bakış ekranı, kullanıcının rolüne göre düzenlenmiş bir iş listesi (yaklaşan vizitler, inceleme bekleyen aday hastalar, açık sorgular, bildirim bekleyen ciddi advers olaylar, planlı ziyaretler, açık risk uyarıları) ile portföydeki çalışmaların kayıt ilerlemesini bir arada gösterir."));
ekle(...sekil("02_pano.png", "Genel bakış ekranı (sistem yöneticisi görünümü)"));
ekle(P("Çalışma kaydı; protokol sürümleri ve değişiklik notları, aşama kontrol listesi, planlanan–gerçekleşen kayıt eğrisi ve çalışmaya ait denetim izini içerir. Sekmeler kurulum, yürütme, izlem ve kapanış başlıkları altında gruplanır."));
ekle(...sekil("04_calisma_ozet.png", "Çalışma özeti: yaşam döngüsü, kayıt eğrisi ve aşama kontrol listesi"));
ekle(H2("6.3 Dört adımlı çalışma sihirbazı"));
ekle(P("Yeni bir çalışma dört adımda kurulur: temel bilgiler (protokol kodu önerisi, tür, faz, sponsor, hedef gönüllü sayısı), tasarım (kollar, vizit şablonu, dahil etme ve hariç tutma kriterleri), merkez ve ekip, eCRF formları ve başvurular. Yarım kalan kurulum taslak olarak saklanır ve kaldığı yerden sürdürülür; çalışmayı kuran kişi ekibe kendiliğinden eklenir. Protokol metni olan kullanıcı, çalışma oluşur oluşmaz protokolden taslak sayfasına yönlendirilir."));
ekle(...sekil("33_sihirbaz_1.png", "Sihirbaz, 1. adım: temel bilgiler", 6.0));
ekle(...sekil("34_sihirbaz_2.png", "Sihirbaz, 2. adım: kollar, vizit şablonu ve kriterler", 6.0));
ekle(H2("6.4 Çalışma tasarımı ve kodsuz eCRF tasarımcısı"));
ekle(P("Tasarım sayfası bir çalışmanın iskeletini tek yerde toplar: kollar ve randomizasyon oranları, gün ve pencere bilgisiyle vizit şeması, eCRF formları ve hangi formun hangi vizitte doldurulacağını gösteren vizit × form matrisi. Gönüllü randomize edildiğinde vizitleri bu şemadan üretilir."));
ekle(...sekil("19_tasarim.png", "Çalışma tasarımı: kollar, vizit şeması ve eCRF formları"));
ekle(P("eCRF tasarımcısı formların kod yazmadan hazırlanmasını sağlar: alan ekleme, tip ve birim seçimi, alt–üst sınırlar, zorunlu alan, koşullu alanlar, bölüm başlıkları, çoklu seçim ve tekrarlayan formlar. Sağdaki canlı önizleme veri giriş ekranının nasıl görüneceğini gösterir. Veri kaydı olan bir formda alan silinemez, tipi değiştirilemez; diğer değişiklikler form sürümünü artırır ve denetim izine yazılır. CDASH standart formları ve telifsiz ölçekler (PHQ-9, GAD-7, VAS) tek tıkla eklenebilir."));
ekle(...sekil("35_ecrf_tasarimci.png", "Kodsuz eCRF tasarımcısı: alanlar, vizit seçimi ve canlı önizleme"));
ekle(H2("6.5 Protokolden taslak"));
ekle(P("Protokol metni yapıştırıldığında ya da PDF/DOCX olarak yüklendiğinde sistem dahil etme ve hariç tutma kriterlerini, çalışma kollarını, vizit takvimini ve gereken standart formları ayıklayıp öneri olarak listeler. Ayrıştırma kural tabanlıdır; Türkçe Klinik BDM bağlıysa öneriler onunla zenginleştirilir. Hiçbir öneri kendiliğinden uygulanmaz: kullanıcı işaretlediklerini onaylar, tanınamayan satırlar ayrıca gösterilir ve uygulanan her öğe denetim izine yazılır. Metinde kimlik verisi bulunursa metin modele gönderilmez."));
ekle(...sekil("36_protokol_taslak.png", "Protokolden çıkarılan öneriler: kriterler, kollar, vizitler ve formlar"));
ekle(H2("6.6 Protokol ve kriter yapılandırma"));
ekle(P("Dahil etme ve hariç tutma kriterlerinin her biri, Türkçe Klinik BDM (ya da BDM sunucusu olmayan kurulumlarda kural tabanlı ayrıştırıcı) tarafından hesaplanabilir bir sorguya dönüştürülür: yaş, cinsiyet, tanı (ICD-10), laboratuvar (LOINC, birim normalizasyonu), ilaç (ATC), performans ölçeği (ECOG, Karnofsky, NYHA), gebelik, tedavi geçmişi, zaman penceresi ve bileşik koşullar desteklenir. Düşük güvenli dönüşümler araştırmacı onayı bekler."));
ekle(...sekil("05_protokol_kriterler.png", "Kriterlerin hesaplanabilir sorguya dönüştürülmesi ve araştırmacı onayı"));
ekle(H2("6.7 Çalışma ekibi"));
ekle(P("Her çalışmanın ekibi ayrı tanımlanır. Proje yöneticisi, CRA, veri yöneticisi, istatistikçi ve farmakovijilans kullanıcıları yalnızca atandıkları çalışmaları görür; araştırmacı ve koordinatörler merkezleri üzerinden erişir. Rol kişiye bir kez verilir, hangi çalışmada çalışacağı ekip sayfasından belirlenir; her ekleme ve çıkarma denetim izine yazılır."));
ekle(...sekil("37_ekip.png", "Çalışma ekibi: atanan kullanıcılar ve merkez üzerinden erişenler"));
ekle(H2("6.8 Merkez yönetimi, performans endeksi ve başvurular"));
ekle(P("Merkez kayıt defteri; kurum türü, HBYS türü, FHIR uç noktası, terapötik alanlar, araştırmacı listesi (GCP eğitim yenileme uyarısıyla) ve geçmiş çalışmalardaki performansı tutar. **Merkez performans endeksi**, her merkezin aktivasyon süresi, kazanım hızı, tarama başarısızlığı ve veri kalitesi göstergelerini tüm havuza ve aynı kurum tipine göre yüzdelik dilimlerle kıyaslar. Sponsor görünümünde merkez adları gizlenir; merkezler kendi konumlarını görür. Kıyaslama havuzu platformdaki çalışma sayısıyla büyüdüğü için endeks, zamanla kuvvetlenen ve rakiplerce kolay kopyalanamayan bir veri varlığıdır."));
ekle(...sekil("29_merkez_endeksi.png", "Merkez performans endeksi (EBM görünümü; sponsor görünümünde adlar gizlenir)"));
ekle(P("Etik kurul, TİTCK, kurum izni ve KVKK başvuruları tip, referans numarası, gönderim ve karar tarihleriyle kaydedilir; karar süreleri merkez ve kurum bazında öğrenilir ve aktivasyon gecikme modelini besler."));
ekle(...sekil("06_merkezler.png", "Çalışma merkezleri: durum, kilometre taşları, tahmin ve risk puanı"));
ekle(H2("6.9 Protokol–hasta eşleştirme"));
ekle(P("Eşleştirme modülü, aktif merkezlerin kimliksizleştirilmiş hasta kayıtlarını protokol kriterleriyle karşılaştırır. Dahil etme kriterlerinde tanı kodu varsa havuz önce ICD-10 ön filtresiyle daraltılır; her hasta için her kriter önce yapısal veri üzerinde, yeterli kanıt yoksa serbest metin üzerinde değerlendirilir. Metin yolunda hasta metinleri cümle tabanlı parçalanır, hibrit aramayla ilgili parçalar bulunur ve BDM'den yalnızca kaynak metinde birebir geçen bir kanıt cümlesiyle karar vermesi istenir. BDM bulunmadığında kalıp tabanlı değerlendirme (laboratuvar değeri, ECOG/NYHA, TNM evre, reseptör durumu, zaman penceresi, tedavi geçmişi) devreye girer."));
ekle(...sekil("sekil_03_eslestirme_akisi.png", "Protokol–hasta eşleştirme boru hattı"));
ekle(P("Sonuçlar uygun, olası, belirsiz ve uygun değil sınıflarında özetlenir. Araştırmacı kriter bazında sonuç, kaynak cümle, güven ve yöntemi görür; kararını gerekçesiyle kaydeder. Onaylanan hasta gönüllü ön tarama listesine düşer. Gölge mod, model önerisi ile araştırmacı kararını karşılaştırarak duyarlılık, özgüllük ve öngörü değerlerini çalışma bazında raporlar."));
ekle(...sekil("08_eslestirme.png", "Aday hasta listesi: model kararı ve araştırmacı kararı"));
ekle(...sekil("09_eslestirme_detay.png", "Aday hasta detayı: kriter bazında kanıt cümleleri ve araştırmacı kararı"));
ekle(H2("6.10 Gönüllü yönetimi, randomizasyon ve eCRF"));
ekle(P("Gönüllü kaydı; onam tarihi ve sürümü, tarama, randomizasyon (onam olmadan randomizasyon engellenir), kol ataması, vizit takvimi, erken ayrılma ve tarama başarısızlığı nedenlerini içerir. Tamamlanmış formdaki değişiklik için gerekçe zorunludur; açık sorgusu olan form kilitlenemez."));
ekle(...sekil("13_gonullu_detay.png", "Gönüllü kaydı: vizit × form matrisi, advers olaylar ve sorgular"));
ekle(P("**Randomizasyon** platformun içinde yapılır: blok boyutu ve isteğe bağlı merkeze göre strata ile bir liste üretilir ve e-imza ile mühürlenir. Gönüllü çalışmaya alındığında kol sıradaki kayıttan otomatik atanır; kol dizilimi ve sıradaki tahsis hiçbir ekranda gösterilmez, yalnızca kullanılan ve kalan kayıt sayıları görünür. Tahsis yapılmış bir liste yeniden üretilemez."));
ekle(...sekil("38_randomizasyon.png", "Randomizasyon listesi: merkeze göre strata, kullanılan ve kalan kayıtlar"));
ekle(P("eCRF alanları CDASH değişken adlarıyla eşlenir; sayısal aralık, zorunlu alan ve tarih kontrolleri otomatik sorgu açar. CRA kaynak veri doğrulamasını (SDV) işaretler. Kapanış aşamasında **araştırmacı (PI) imzası** ve **toplu kilit** kullanılır: veri yöneticisi ön kontrol raporunu görür, seçilen formları tek e-imza ile kilitler; kilit açma gerekçe ister. Veri CDISC ODM 1.3.2 veya CSV paketi olarak dışa aktarılır."));
ekle(...sekil("14_ecrf_form.png", "eCRF veri giriş formu (CDASH eşlemeli alanlar, otomatik edit-check)"));
ekle(H2("6.11 Güvenlik raporlama"));
ekle(P("Advers olaylar MedDRA terimi, CTCAE derecesi, nedensellik, beklenirlik ve ciddiyet ölçütü ile kaydedilir. Ciddi olaylarda TİTCK bildirim süresi (7/15 gün) farkındalık tarihinden geri sayılır; beklenmeyen ve ilişkili ciddi olaylar SUSAR olarak işaretlenir."));
ekle(...sekil("16_guvenlik.png", "Güvenlik modülü: AE listesi, SAE/SUSAR işaretleri ve bildirim takibi"));
ekle(H2("6.12 Merkez zekâsı ve sponsor fizibilite raporu"));
ekle(P("Kazanım tahmini, merkezin kendi geçmişi ile benzer terapötik alandaki merkez havuzunu birleştiren Gamma–Poisson hiyerarşik Bayes modelidir; az verili merkezlerde tahmin havuza doğru büzülür. Aktivasyon gecikme riski, seçimden aktivasyona geçen sürenin sansürlü Weibull hızlandırılmış başarısızlık zamanı modeliyle kestirilir. Monte Carlo simülasyonu ile hedefe ulaşma tarihi ve zamanında bitirme olasılığı hesaplanır; sıralama katmanı her merkez için Türkçe gerekçe üretir. Sponsor fizibilite raporu bu analizleri yazdırılabilir tek sayfada derler."));
ekle(...sekil("10_merkez_zekasi.png", "Merkez zekâsı: tahminler, Monte Carlo projeksiyonu ve açıklanabilir sıralama"));
ekle(...sekil("26_fizibilite_raporu.png", "Sponsor fizibilite ve kazanım raporu", 6.0));
ekle(H2("6.13 Sponsor görünümü"));
ekle(P("Sponsor rolündeki kullanıcı, herkesin kullandığı Genel Bakış ekranına girer; bu ekran ona yalnızca kendi kurumunun çalışmalarını salt okunur bir özet olarak gösterir: aktif çalışma ve randomize gönüllü sayısı, mevcut hızla hedefe kalan süre ve plana göre takvim riski, açık ve aksiyon seviyesindeki uyarılar, SAE sayısı, en riskli merkez ve fizibilite raporu bağlantısı. Sponsor hiçbir kaydı değiştiremez; hasta kimlik verisi, eşleştirme çıktıları ve kaynak belgeler yalnızca araştırma merkezi tarafından görülür. Merkez performans endeksi sponsora anonim olarak açılır."));
ekle(...sekil("27_sponsor_gorunumu.png", "Sponsor görünümü: Genel Bakış'ta kurumun salt okunur özeti"));
ekle(H2("6.14 Risk bazlı izlem"));
ekle(P("Modül ICH E6(R3) risk temelli kalite yönetimini uygular. On beş varsayılan anahtar risk göstergesi çalışma bazında eşiklerle özelleştirilir; uyarılar hem sabit eşiklerden hem de merkezler arası dayanıklı z-skoru ile anomali tespitinden üretilir ve her uyarının \"neden tetiklendi\" açıklaması vardır. Bileşik risk puanı izlem önerisini belirler; kalite tolerans limitleri çalışma düzeyinde izlenir."));
ekle(...sekil("11_rbm.png", "Risk bazlı izlem: merkez × KRI ısı haritası ve uyarılar"));
ekle(H2("6.15 İzlem ziyaretleri, ziyaret raporu ve sapma kapatma"));
ekle(P("Ziyaretler (başlatma, ara izlem, kapanış, uzaktan ve tetiklenmiş) merkez bazında planlanır; aksiyon seviyesindeki bir risk uyarısından tek tıkla tetiklenmiş ziyaret açılabilir. **Ziyaret raporu** gerçekleşen tarihi, SDV oranını, kontrol listesini ve bulguları içerir; proje yöneticisi raporu e-imza ile onaylar, onaydan sonra rapor değiştirilemez. Kapanmamış bulgular sonraki ziyarete taşınır."));
ekle(...sekil("39_ziyaret_raporu.png", "Ziyaret raporu: kayıt, kontrol listesi, bulgular ve e-imzalı onay"));
ekle(P("Protokol sapmaları kategori ve önemle kaydedilir. **Sapma kapatma** için kök neden ve düzeltici-önleyici faaliyet girilir; majör sapmalarda etik kurul bildirim tarihi girilmeden sapma kapatılamaz. Tüm değişiklikler eski ve yeni değerleriyle denetim izine yazılır."));
ekle(...sekil("40_sapma_kapatma.png", "Majör protokol sapması: kök neden, düzeltici faaliyet ve zorunlu etik bildirim tarihi"));
ekle(H2("6.16 TMF, denetim izi ve elektronik imza"));
ekle(P("TMF modülü DIA referans modeli bölgelerine göre düzenlenmiştir ve merkez dosyası (ISF) görünümü sunar. Her belgenin SHA-256 özeti alınır; belge sürümleri zincir halinde tutulur, onay e-imza ile yapılır. Belge indirilirken özet yeniden doğrulanır, böylece arşivdeki dosyanın değişmediği her indirmede kontrol edilmiş olur. Tüm işlemler zincirli denetim izine yazılır; e-imzada parola yeniden istenir; art arda hatalı girişte hesap süreli olarak kilitlenir."));
ekle(...sekil("18_tmf.png", "TMF: DIA referans modeli bölgeleri, özet değerleri ve e-imza ile onay", 6.0));
ekle(...sekil("21_denetim_izi.png", "Denetim izi: zincirli kayıtlar ve elektronik imzalar"));
ekle(H2("6.17 Ön analiz ve Tablo 1"));
ekle(P("Analiz sekmesi, veri girildikçe çalışmanın ilk sonuçlarını gösterir: kollara göre gönüllü akışı, değişken bazında betimleyici özet ve verinin dağılımına göre kural tabanlı test seçimi (Welch t, Mann-Whitney, ANOVA, Kruskal-Wallis, ki-kare, Fisher), vizitler arası değişim ve kol × sistem organ sınıfı advers olay özeti. **Tablo 1** (başlangıç özeti) seçilen vizitte tüm sayısal ve seçim alanlarını kol bazında tek tıkla hazırlar ve CSV olarak indirilir. Analiz veri seti de indirilebilir; her indirme denetim izine yazılır. Bu sayfa ön analiz içindir; nihai analiz istatistiksel analiz planına göre yapılır."));
ekle(...sekil("25_analiz.png", "Ön analiz: kayıt özeti ve kollara göre gönüllü akışı"));
ekle(...sekil("41_tablo1.png", "Başlangıç özeti (Tablo 1): kol bazında değişken özetleri"));
ekle(H2("6.18 Kimliksizleştirme ve hasta havuzu yükleme"));
ekle(P("HBYS'den gelen serbest metinler sisteme yazılmadan önce kimliksizleştirme modülünden geçer: TC kimlik numarası (algoritma doğrulamalı), telefon, e-posta, IBAN, plaka, tarihler, dosya ve protokol numaraları, kişi adları, kurum adları, il/ilçe ve adres ifadeleri, 89 yaş üstü. Klinik terimler beyaz liste ile korunur; maskeleme, tutarlı takma ad ve tarih kaydırma modları vardır. İkinci geçiş doğrulaması şüpheli kalıp kalan kayıtları reddeder. CSV yükleme sayfası aynı akışı HBYS dökümleri için uygular."));
ekle(...sekil("20_kimliksizlestirme.png", "Kimliksizleştirme aracı: girdi, çıktı ve ikinci geçiş uyarıları"));
ekle(...sekil("31_csv_yukleme.png", "CSV ile hasta havuzu yükleme (FHIR bağlantısı olmayan kurulumlar için)"));
ekle(H2("6.19 REST API ve HBYS entegrasyonu"));
ekle(P("REST API, platform işlevlerini (çalışma, kriter, eşleştirme, risk uyarıları) ve klinik metin uçlarını (kimliksizleştirme, kriter yapılandırma, ICD-10 kodlama önerisi, klinik özet) oturum veya API anahtarıyla diğer kurumsal uygulamalara açar. API anahtarları geçerlilik süreli ve iptal edilebilirdir; anahtar, sahibinin rol izinleri dahilinde çalışır. HBYS entegrasyonu FHIR R4 Bundle alımı, ResearchStudy / ResearchSubject kaynakları ve merkez bazlı senkronizasyon uçlarıyla yapılır. API belgeleri yalnızca oturum açmış kullanıcılara açılır."));
ekle(...sekil("30_api_anahtarlari.png", "API anahtarı yönetimi (makine-makine entegrasyon)"));

// 7 BDM altyapisi
ekle(H1("7. Türkçe Klinik Büyük Dil Modeli altyapısı"));
ekle(kisaca("Türkçe hasta raporlarını anlayan yapay zekâ modeli, açık bir temel modelin Türkçe tıp metinleriyle eğitilmesiyle elde edilir; model uydurmasın diye her cevabını kaynağıyla vermek zorundadır ve hastaneler verilerini paylaşmadan modeli birlikte geliştirebilir."));
ekle(H2("7.1 Model geliştirme hattı"));
ekle(P("Model, açık kaynak 7–8 milyar parametreli bir temel modelin Türkçe tıbbi derlemle sürekli ön eğitimi ve klinik araştırma görevleri için talimat ince ayarı (LoRA/QLoRA) ile geliştirilmektedir. Derlem; kimliksizleştirilmiş epikriz, patoloji ve radyoloji raporları, klinik kılavuzlar, protokol metinleri ve klinisyen etiketli görev örneklerinden oluşur. Eğitim yapılandırmaları, veri hazırlama, değerlendirme ve nicemleme betikleri ürünün ml/ dizininde sürümlenir."));
ekle(...sekil("sekil_04_bdm_gelistirme.png", "Türkçe Klinik BDM geliştirme ve dağıtım hattı"));
ekle(H2("7.2 Görevler, istem tasarımı ve koruma katmanı"));
ekle(P("Model dört göreve özelleştirilir: kriteri hesaplanabilir sorguya dönüştürme, kriter için hasta metninden kanıt çıkarma, çalışma odaklı klinik özet ve ICD-10 kodlama önerisi. Protokolden taslak çıkarma da aynı yapılandırma yeteneğini kullanır. Koruma katmanı; kaynak metinde birebir bulunmayan kanıtı reddeder (halüsinasyon kontrolü), güven eşiğinin altındaki sonuçları araştırmacıya bırakır, JSON şema doğrulaması yapar, BDM erişilemezse kural tabanlı yola düşer ve istemde kimlik verisi kalıbı tespit ederse isteği engeller."));
ekle(H2("7.3 TR-KlinikBench: açık değerlendirme seti"));
ekle(P("Ar-Ge programı, Türkçe klinik araştırma NLP görevleri için bir açık değerlendirme seti tanımlar. Altı görev (kriter–hasta eşleştirme, kanıt çıkarma, kriter yapılandırma, kimliksizleştirme, ICD-10 kodlama, çalışma odaklı özet) için JSON şemaları, metrikler, iki etiketleyici + hakem kuralı ve skor tablosu politikası belirlenmiştir. Set yalnızca sentetik ve etik onaylı kimliksizleştirilmiş veri içerir; demo kurulumundaki örnekler sentetiktir. Hedef, pilot hastanelerde 2.000 etiketli çifte ulaşmak ve seti program sonunda yayımlamaktır. Kural tabanlı taban çizgisinin mevcut skorları Bölüm 9'da verilmiştir."));
ekle(H2("7.4 Federe model güncelleme"));
ekle(P("Hasta verisinin kurum dışına çıkmaması ilkesi model iyileştirmeyi de kapsar. Federe protokolde her hastane LoRA adaptörünü kendi kimliksizleştirilmiş verisiyle yerelde eğitir; yalnızca adaptör ağırlıkları (hasta verisi değil) EBM toplayıcısına gönderilir ve ağırlıklı ortalama (FedAvg) ile birleştirilir. Diferansiyel gizlilik gürültüsü ve güvenli toplama seçenekleri, ağırlıklardan üyelik çıkarımı riskini azaltır. Her tur TR-KlinikBench ile değerlendirilir; hedef karşılanmazsa tur yinelenir. Toplayıcı ve istemci iskeleti üründe mevcuttur; GPU'lu pilot hastanelerle ilk tur Ar-Ge programının 2. fazındadır."));
ekle(H2("7.5 Model ve veri kartları"));
ekle(P("Her model sürümü, amaçlanan kullanım ve kullanım dışı durumları, eğitim verisi özetini, değerlendirme sonuçlarını, alt grup (bölge, kurum tipi, cinsiyet) analizlerini, sınırlılıkları ve güvenlik önlemlerini içeren bir model kartıyla; eğitim verisi ise kaynakları, kimliksizleştirme ve etik onay durumunu, saklama ve erişim kurallarını içeren bir veri kartıyla yayımlanır. Bu belgeler sorumlu yapay zekâ ilkelerinin denetlenebilir karşılığıdır."));

// 8 Uyum
ekle(H1("8. Düzenleyici uyum, veri koruma ve güvenlik"));
ekle(kisaca("Sistem, kişisel veri kanununa, iyi klinik uygulama kurallarına ve uluslararası elektronik kayıt standartlarına uygun tasarlanmıştır; denetim için gereken belgeler ürünle birlikte verilir."));
ekle(...tablo(["Çerçeve", "Platformdaki karşılığı"], [
  ["KVKK (6698 s. Kanun) ve Kişisel Sağlık Verileri Yönetmeliği", "Hastane içi işleme; zorunlu kimliksizleştirme akışı; takma ad anahtarının merkezde kalması; hasta kaydı görüntülemelerinin denetim izine yazılması; federe öğrenmede verinin kurum dışına çıkmaması; veri envanteri ve etki değerlendirmesi"],
  ["İyi Klinik Uygulamaları – ICH E6(R3)", "Risk temelli kalite yönetimi: KRI, QTL, merkezler arası anomali, izlem önerisi; onam olmadan randomizasyon engeli; protokol sapma yönetimi; TMF"],
  ["21 CFR Part 11 / EU GMP Annex 11", "Hash zincirli değiştirilemez denetim izi; parola ile yeniden doğrulanan e-imza; değişiklik gerekçesi zorunluluğu; hesap kilitleme ve oturum süresi; uyum değerlendirme belgesi"],
  ["TİTCK Klinik Araştırmalar Hakkında Yönetmelik", "Başvuru tiplerinin takibi; SAE için 7/15 gün bildirim sayacı; SUSAR tespiti; yıllık bildirim ve sonlandırma kayıtları"],
  ["CDISC (CDASH, ODM, SDTM)", "CDASH eşlemeli eCRF alanları; ODM 1.3.2 dışa aktarım; SDTM eşlemesi veri yöneticisi işlemi"],
  ["HL7 FHIR R4 / OMOP CDM v5.4", "HBYS adaptörü; ResearchStudy / ResearchSubject kaynakları; OMOP CSV dışa aktarımı"],
  ["IEC 62304 / ISO 27001 yaklaşımı", "Yaşam döngüsü kayıtları, sürümleme, değişiklik günlüğü, FMEA; TLS, güvenlik başlıkları, en az yetki, API anahtarı geçerlilik süresi, yedekleme politikası; sızma testi Faz 4"],
  ["Bilgisayarlı sistem validasyonu (GAMP 5)", "Validasyon planı, URS (78 gereksinim), FRS, risk analizi, IQ/OQ (38 senaryo)/PQ, izlenebilirlik matrisi ürünle birlikte teslim edilir"],
  ["Sorumlu yapay zekâ", "Model ve veri kartları; karar desteği sınırı; insan onayı; gölge mod ile sürekli ölçüm; alt grup analizleri; halüsinasyon koruması"],
], [2.4, 5.4]));

// 9 Olgunluk ve Ar-Ge
ekle(H1("9. Olgunluk durumu ve ölçüm sonuçları"));
ekle(kisaca("Ürünün temel kısmı geliştirilmiş ve test edilmiş durumda; yapay zekâ kısmı ise doğrulama aşamasında. Yapay zekâ bileşenlerinin başarısı ürünle gelen değerlendirme aracıyla ölçülür ve hedeflerle karşılaştırılır; sayılar bu bölümde olduğu gibi verilmiştir."));
ekle(H2("9.1 Modül olgunluk tablosu"));
ekle(...tablo(["Modül", "Durum", "Açıklama"], [
  ["Çalışma, merkez, başvuru yönetimi; kullanım modları, sihirbaz, çalışma ekibi", "Hazır", "Otomatik testler ve demo ortamında doğrulandı"],
  ["Çalışma tasarımı, kodsuz eCRF tasarımcısı, form sürümleme", "Hazır", "Kayıtlı formda alan silme ve tip değiştirme engelli; değişiklikler sürümlenir"],
  ["Gönüllü, vizit, eCRF, sorgu, SDV, randomizasyon, PI imzası, toplu kilit, ODM dışa aktarım", "Hazır", "CDASH eşlemeli formlar; e-imzalı blok randomizasyon listesi"],
  ["Güvenlik raporlama (AE/SAE/SUSAR)", "Hazır", "MedDRA kodlama elle; otomatik kodlama önerisi yol haritasında"],
  ["İzlem ziyaretleri, ziyaret raporu, sapma kapatma", "Hazır", "E-imzalı rapor onayı; majör sapmada etik bildirim zorunlu"],
  ["Ön analiz ve Tablo 1", "Hazır", "Ön analiz amaçlı; nihai analiz istatistiksel analiz planına göre yapılır"],
  ["TMF (özet doğrulamalı indirme), denetim izi, e-imza, RBAC, API anahtarı", "Hazır", "21 CFR 11 / Annex 11 uyum değerlendirmesi mevcut"],
  ["Merkez performans endeksi; sponsor görünümü", "Hazır", "Havuz büyüdükçe güvenilirliği artar; sponsora anonim ve salt okunur"],
  ["Protokolden taslak", "Pilot", "Kural tabanlı ayrıştırma; BDM ile zenginleştirme laboratuvarda; öneriler insan onayıyla uygulanır"],
  ["Kimliksizleştirme", "Pilot", "Kural tabanlı; sentetik sette F1 0,95; gerçek rapor seti üzerinde değerlendirme Faz 1"],
  ["FHIR R4 HBYS adaptörü, CSV yükleme, OMOP", "Pilot", "Mock ve standart FHIR sunucusuyla test edildi; HBYS üreticileriyle saha testi Faz 4"],
  ["Risk bazlı izlem (KRI/QTL/anomali)", "Pilot", "Eşikler EBM geçmiş verisine göre; prospektif yanlış alarm oranı ölçülecek"],
  ["Merkez zekâsı", "Pilot / Ar-Ge", "Örnek içi MAPE ve AUC hedefe yakın; çalışma türü kovaryatı yol haritasında"],
  ["Kriter yapılandırma ve eşleştirme motoru", "Pilot / Ar-Ge", "Yapısal ve kalıp tabanlı yol üretimde; BDM yolu laboratuvarda"],
  ["Türkçe Klinik BDM, federe güncelleme", "Ar-Ge", "Kavram kanıtı ve iskelet; sürekli ön eğitim, ince ayar ve ilk federe tur Faz 2"],
  ["TR-KlinikBench", "Ar-Ge", "Şemalar, metrikler, sentetik örnek set ve çalıştırıcı hazır; klinisyen etiketli set Faz 1"],
], [2.8, 1.1, 3.9]));
ekle(H2("9.2 Ar-Ge başarı ölçütleri ve mevcut ölçümler"));
ekle(P("Eşleştirme, kanıt, kriter yapılandırma ve kimliksizleştirme değerleri, ürünle gelen değerlendirme aracının (ml/degerlendirme) demo kurulumunun örnek değerlendirme setleri üzerindeki komut satırı çıktısıdır; kazanım ve aktivasyon değerleri aynı demo verisi üzerinde merkez zekâsı modellerinin örnek içi hesaplamasıdır. BDM sunucusu bağlı olmadığı için eşleştirme ölçümleri **kural tabanlı taban çizgisini** gösterir; Ar-Ge programında geliştirilecek Türkçe Klinik BDM'nin bu taban çizgisini aşması beklenir."));
ekle(...tablo(["Ölçüt", "Hedef (program)", "Mevcut", "Ölçüm kaynağı ve not"], [
  ["Hasta–kriter eşleştirmede duyarlılık", "≥ %90", "%76,9", "Altın standart set (28 sentetik örnek), kural tabanlı; özgüllük %93,3; belirsiz oranı %32"],
  ["Halüsinasyon oranı (kanıt kaynakta yok)", "≤ %2", "%0", "Koruma katmanı kaynakta bulunmayan kanıtı reddeder"],
  ["Kriter yapılandırmada tam eşleşme", "≥ %85", "%35,7", "Alan bazlı eşleşme %60; BDM yapılandırması Faz 2'nin ana hedefi"],
  ["Kimliksizleştirme duyarlılığı", "≥ %98", "%90,9", "Sentetik set, 22 varlık; kesinlik %100, F1 %95"],
  ["Kazanım tahmininde MAPE", "≤ %25", "%33,5", "3 aktif çalışma, çalışma düzeyinde, örnek içi; kayıt çalışmasında sapma yüksek"],
  ["Aktivasyon gecikme riskinde AUC", "≥ 0,80", "0,79", "37 merkez, örnek içi; prospektif doğrulama Faz 5"],
  ["Ön tarama süresinde azalma", "≥ %50", "%84 (tahmini)", "Motor ~50 ms/hasta + 4 dk inceleme; manuel 25 dk varsayımı pilotta ölçülecek"],
], [2.4, 1.1, 1.1, 3.2]));
if (BENCH && BENCH.satirlar && BENCH.satirlar.length) {
  ekle(H3("TR-KlinikBench kural tabanlı taban çizgisi"));
  ekle(P("Altı görevli değerlendirme setinin kural tabanlı sağlayıcıyla çalıştırılmasından elde edilen skorlar aşağıdadır. Set sentetik örneklerden oluşur; sayılar BDM'nin aşması gereken taban çizgisini belirler."));
  ekle(...tablo(["Görev", "Ana metrik", "Taban (kural)", "Hedef (BDM)"], BENCH.satirlar, [2.8, 2.2, 1.4, 1.4]));
}
ekle(not("Ölçümler aynı komutla yeniden üretilebilir: **python -m ml.degerlendirme.degerlendir --altin ml/degerlendirme/ornek_altin_standart.jsonl** (kural tabanlı sağlayıcı; BDM bağlıysa --saglayici ve --model ile). Sonuç ml/ciktilar altına JSON olarak yazılır."));
ekle(P("Bu ölçümler ürünün mevcut durumuna ilişkin dürüst bir resim sunmayı amaçlar. Kural tabanlı yol halüsinasyon üretmez ancak serbest metin kriterlerinde sık \"belirsiz\" der; Ar-Ge programının kapatacağı boşluk budur."));
ekle(H2("9.3 Teknoloji hazırlık seviyesi ve Ar-Ge programı fazları"));
ekle(P("Platform çekirdeği ilgili ortamda doğrulanmış prototip düzeyindedir (THS 5–6: geliştirildi, otomatik testlerle ve demo ortamında sınandı, validasyon dosyası hazır), yapay zekâ katmanı laboratuvar ortamında doğrulanmıştır (THS 4). 18 aylık Ar-Ge programı, yapay zekâ katmanını gerçek klinik araştırma ortamında doğrulayarak bütünleşik ürünü THS 7'ye taşımayı hedefler. Program beş fazdan oluşur:"));
ekle(...tablo(["Faz", "Platformdaki mevcut temel", "Programla eklenecek"], [
  ["Faz 1 (ay 1–4) Veri altyapısı ve referans veri seti", "Ortak veri modeli, FHIR/OMOP eşlemeleri, CSV yolu, kimliksizleştirme aracı, TR-KlinikBench şemaları ve etiketleme kılavuzu", "Pilot hastane veri envanteri, etik/KVKK onayları, 2.000 çiftlik altın standart set, gerçek rapor seti üzerinde kimliksizleştirme değerlendirmesi"],
  ["Faz 2 (ay 3–10) Türkçe Klinik BDM ve eşleştirme motoru", "Eşleştirme boru hattı, koruma katmanı, RAG, kalıp tabanlı değerlendirme, eğitim/değerlendirme betikleri, federe toplayıcı iskeleti", "Sürekli ön eğitim, talimat ince ayarı, nicemlenmiş hastane içi model, ilk federe tur, duyarlılık ≥ %90"],
  ["Faz 3 (ay 5–12) Merkez zekâsı ve RBM modelleri", "Gamma–Poisson, Weibull AFT, sıralama, performans endeksi, 15 KRI, anomali motoru", "Çalışma türü ve etik kurul süresi kovaryatları, transfer öğrenme, prospektif MAPE/AUC, yanlış alarm oranı"],
  ["Faz 4 (ay 9–15) Platform entegrasyonu, güvenlik, validasyon", "Sağlayıcı soyutlaması, FHIR adaptörü, API anahtarı, CSV dosyası, Part 11 uyumu", "HBYS üreticileriyle saha entegrasyonu, sızma testi, IEC 62304 / ISO 27001 uyum tamamlanması"],
  ["Faz 5 (ay 13–18) Pilot doğrulama ve ürünleştirme", "Gölge mod, değerlendirme aracı, sponsor görünümü, fizibilite raporu, ön analiz, kurulum paketi", "Üç hastanede prospektif gölge mod doğrulaması, kullanıcı kabul testleri, regülasyon sınıflandırması, ilk ticari kurulumlar, yazılım tescili ve patent başvurusu, TR-KlinikBench yayımı"],
], [1.8, 3, 3]));

// 10 Dogrulama
ekle(H1("10. Doğrulama planı"));
ekle(kisaca("Yapay zekânın gerçekten işe yaradığını kanıtlamak için üç hastanede sistem, doktorların mevcut çalışma biçiminin yanında 'gölge' olarak çalışacak ve sonuçlar karşılaştırılacak."));
ekle(P("Doğrulama iki düzeyde yürütülür. **Teknik doğrulama** TR-KlinikBench ve altın standart set üzerinde otomatik değerlendirme ile yapılır; her model sürümü için metrikler raporlanır ve sürümlenir. **Klinik ortam doğrulaması** gölge mod ile yapılır: en az biri onkoloji merkezi olmak üzere üç pilot hastanede, EBM'nin yürüttüğü aktif çalışmalarda motor önerileri araştırmacıya gösterilmeden kaydedilir ve manuel ön tarama sonuçlarıyla karşılaştırılır."));
ekle(...tablo(["Doğrulama konusu", "Yöntem", "Kabul ölçütü"], [
  ["Eşleştirme doğruluğu", "Gölge mod; araştırmacı kararı referans; çalışma ve merkez bazında", "Duyarlılık ≥ %90; PPV raporlanır; kaynak cümle doğruluğu klinisyen tarafından örneklemle denetlenir"],
  ["Ön tarama süresi", "Zaman-hareket ölçümü, manuel ve platform destekli kollar", "≥ %50 azalma"],
  ["Kazanım ve gecikme tahmini", "Prospektif: tahminler kilitlenir, 6 ay sonra gerçekleşenle karşılaştırılır", "MAPE ≤ %25; AUC ≥ 0,80"],
  ["Risk bazlı izlem", "Uyarıların CRA tarafından sınıflanması; ziyaret bulgularıyla eşleme", "Yanlış alarm oranı raporlanır; majör bulguların uyarı ile öncelenme oranı"],
  ["Kimliksizleştirme", "Gerçek rapor örneklemi üzerinde çift etiketleme", "Duyarlılık ≥ %98 (kimlik verisi), klinik terim kaybı ≤ %1"],
  ["Federe güncelleme", "İki hastaneyle bir tur; merkezi eğitimle karşılaştırma", "TR-KlinikBench'te merkezi eğitimin %95'i içinde performans; ağırlıklardan veri sızıntısı testi"],
  ["Kullanılabilirlik ve kabul", "Kullanıcı kabul testleri (OQ/PQ senaryoları), SUS anketi", "Kritik senaryolarda %100 geçiş; SUS ≥ 70"],
], [1.8, 3.2, 2.8]));

// 11 Konsorsiyum
ekle(H1("11. İş birlikleri, yönetişim ve ekosistem"));
ekle(kisaca("Ar-Ge programı EBM, üç pilot hastane, bir üniversite ve bir hastane yazılımı üreticisiyle birlikte yürütülecek; veriyle ilgili her karar ortak bir kurulun onayından geçecek; seçilmiş sonuçlar yayın ve açık bileşen olarak paylaşılacak."));
ekle(H2("11.1 Paydaş yapısı"));
ekle(...tablo(["Paydaş", "Rol", "Katkı ve kazanım"], [
  ["EBM Klinik Araştırma Hizmetleri (yürütücü)", "Ürün geliştirme, operasyon, pilot koordinasyonu, ticarileşme", "Aktif çalışma portföyü, CRO/SMO ağı, geliştirilmiş platform; ürün ve altyapının sürdürülmesi"],
  ["Pilot hastaneler (3; en az biri onkoloji merkezi; anlaşmalar görüşme aşamasında)", "Veri sağlayıcı, klinisyen etiketleme, gölge mod doğrulama, federe tur katılımcısı", "Hastane içi kurulum, araştırma kapasitesinde artış, çalışma gelirleri; ticari koşullar pilot sözleşmesinde belirlenir"],
  ["Üniversite doğal dil işleme / biyoistatistik grubu", "Model eğitimi ve değerlendirme yöntemi, yayın, TR-KlinikBench hakemliği", "Ortak yayın, veri seti erişimi, lisansüstü tez konuları"],
  ["HBYS üreticisi (en az bir)", "FHIR R4 entegrasyonunun saha testi, OEM kimliksizleştirme bileşeni", "Araştırma modülü teklif edebilme, FHIR uyumluluğunun doğrulanması"],
  ["Danışma kurulu (TİTCK, etik kurul temsilcileri, hasta derneği)", "Regülasyon uyumu, etik çerçeve, hasta bakış açısı", "Karar destek sınırlarının doğru çizilmesi"],
], [2.2, 2.6, 3]));
ekle(H2("11.2 Veri yönetişimi"));
ekle(P("Ar-Ge programı bir Veri Yönetişim Kurulu kurar: her pilot hastanenin veri sorumlusu temsilcisi, EBM kalite güvence ve veri koruma sorumlusu, üniversite etik temsilcisi. Kurul; veri envanterini, kimliksizleştirme kurallarının değişikliklerini, TR-KlinikBench'e girecek örneklerin uygunluğunu, federe tur katılımını ve açık yayımlanacak bileşenleri onaylar. Hasta verisi hiçbir aşamada kurum dışına çıkmaz; açık sete yalnızca sentetik veya etik onaylı kimliksizleştirilmiş örnekler girer; her örnek iki etiketleyici ve bir hakem tarafından onaylanır."));
ekle(H2("11.3 Klinisyen etiketleme ağı"));
ekle(P("Altın standart setin oluşturulması klinisyen emeği gerektirir. Platform, etiketleme işini araştırmacının rutin iş akışına gömer: gölge modda her araştırmacı kararı (onay/red/gerekçe) etiket adayıdır; kriter onayları yapılandırma etiketidir; kaynak cümle doğrulamaları kanıt etiketidir. Böylece etiketleme ayrı bir proje değil, pilot operasyonun yan ürünüdür. Etiketleyiciler arası uyum (Cohen κ) sürekli raporlanır; düşük uyumlu kriter tipleri kılavuza geri beslenir."));
ekle(H2("11.4 Yayın, standart ve eğitim katkısı"));
ekle(madde("TR-KlinikBench tanımı ve taban sonuçları için hakemli yayın (Türkçe klinik NLP alanında referans set)."));
ekle(madde("Kanıta bağlı eşleştirme ve koruma katmanı için yöntem yayını; gölge mod pilot sonuçları için klinik araştırma metodolojisi yayını."));
ekle(madde("HL7 Türkiye FHIR profilleri ve TİTCK e-başvuru biçimleri için öneri; OMOP Türkçe sözlük eşlemelerine katkı."));
ekle(madde("Araştırma hastaneleri için risk bazlı izlem ve yapay zekâ destekli ön tarama eğitimleri; pilot hastanelerde koordinatör sertifikasyonu."));

// 12 Is modeli
ekle(H1("12. İş modeli ve ticarileşme"));
ekle(kisaca("Ürün hastanelere, ilaç ve cihaz firmalarına ve araştırma şirketlerine farklı paketlerle satılır; ilk adım pilot hastanelerde ölçülebilir doğrulama. Rakamlar planlama hedefidir, taahhüt değildir; varsayımları yanında yazılıdır."));
ekle(H2("12.1 Hedef kullanıcılar ve değer önerisi"));
ekle(...tablo(["Segment", "Temel sorun", "SmartClinical'ın değeri", "Ödeme gerekçesi"], [
  ["Sponsorlar (yerli ilaç, biyobenzer, cihaz, IVD üreticileri)", "Kayıt gecikmesi, merkez seçim hatası, görünürlük eksikliği", "Hızlı kazanım, kanıta dayalı merkez seçimi, sponsor görünümünde güncel takvim ve risk özeti, fizibilite raporu", "Çalışma süresindeki her ayın sabit maliyeti ve pazara giriş gecikmesi"],
  ["CRO ve SMO'lar", "Manuel ön tarama ve izlem iş yükü, çok sistemli operasyon", "Tek platform, yapay zekâ destekli ön tarama, risk bazlı izlem ile ziyaret maliyeti düşüşü", "Personel verimliliği, proje başına marj"],
  ["Araştırma hastaneleri ve üniversiteler", "Uygun hastanın bulunamaması, KVKK nedeniyle dış sistem kullanılamaması, akademik çalışmalarda yazılım maliyeti", "Hastane içi Türkçe eşleştirme, performans endeksinde görünürlük, akademik lisans sınıfı", "Çalışma gelirleri, araştırma kapasitesi, akreditasyon"],
  ["HBYS üreticileri ve veri ambarı projeleri", "Araştırma amaçlı ikincil kullanım için kimliksizleştirme ve NLP eksikliği", "OEM kimliksizleştirme ve klinik NLP servis API'si", "Ürünlerine eklenecek araştırma modülü"],
], [1.9, 2, 2.4, 1.5]));
ekle(H2("12.2 İlk kurulum ve doğrulama programı"));
ekle(P("Pazara giriş, satış sürecinden önce kanıt üretme süreci olarak tasarlanmıştır. İlk kurulumlar, Ar-Ge programı kapsamında anlaşma yapılacak pilot hastanelerde ve EBM'nin yürüttüğü çalışmalarda yapılır; sistem mevcut iş akışının yanında gölge modda çalışır ve etkisi ölçülür. İlk kurulumların ticari koşulları (kurulum, lisans, veri ve etiketleme katkısı, referans olma izni) her kurumla ayrı sözleşmede belirlenir; bu doküman bir fiyat taahhüdü içermez."));
ekle(...tablo(["Başlık", "Yaklaşım"], [
  ["Süre ve kapsam", "Hastane başına yaklaşık 6 ay; 1–2 aktif çalışma; FHIR veya CSV yoluyla hasta havuzu; gölge modda eşleştirme, risk izleme ve merkez zekâsı"],
  ["Hastaneden beklenen", "Etik kurul başvurusu, klinisyen etiketleme (iş akışı içinde), gölge mod karşılaştırması için manuel ön tarama kayıtları, pilot raporunun referans olarak kullanılmasına izin"],
  ["Hastaneye sağlanan", "Hastane içi kurulum ve eğitim, kendi merkezlerinin performans endeksi ve pilot raporu, kurumsal lisansa geçişte pilot sözleşmesinde tanımlanan koşullar"],
  ["EBM ve yatırımcı için çıktı", "Prospektif doğrulama verisi, etiketli veri seti, referans müşteri, satış materyali için anonim pilot bulguları"],
], [1.8, 6]));
ekle(H2("12.3 Gelir modeli ve indikatif fiyatlandırma"));
ekle(P("Fiyatlar indikatif aralıklardır, taahhüt değildir; pilot sonrası fiyat duyarlılığı ölçümleriyle kesinleştirilecektir. Amaç, yurt dışı çözümlerin yıllık lisans düzeyinin belirgin altında kalırken akademik segmenti dışlamamaktır."));
ekle(...tablo(["Lisans sınıfı", "Hedef", "Kapsam", "Model ve indikatif fiyat"], [
  ["Kurumsal (on-premise)", "Araştırma hastaneleri, üniversiteler", "Tüm modüller, BDM hastane GPU'sunda, sınırsız çalışma, HBYS entegrasyonu", "Yıllık lisans 1,5–4 milyon TL (yatak ve çalışma hacmine göre) + kurulum/entegrasyon + %18 bakım"],
  ["Çalışma bazlı", "Sponsorlar, CRO'lar", "Belirli çalışma için merkez zekâsı, RBM, eCRF, TMF, sponsor görünümü", "Çalışma başına 300 bin – 1,5 milyon TL (süre ve merkez sayısına göre)"],
  ["SaaS (operasyon katmanı)", "Küçük CRO'lar, SMO'lar", "Hasta verisi içermeyen operasyon modülleri bulutta; eşleştirme hastane kurulumunda", "Kullanıcı başına aylık 2.500–4.000 TL"],
  ["Akademik", "Araştırmacı başlatımlı çalışmalar", "Tek merkez, temel modüller", "Yıllık 50–100 bin TL; eğitim ve destek dahil"],
  ["Bileşen / OEM", "HBYS üreticileri, veri ambarı projeleri", "Kimliksizleştirme aracı, klinik NLP servis API'si", "OEM lisansı veya API çağrısı başına; üretici başına yıllık asgari"],
], [1.5, 1.5, 2.6, 2.2]));
ekle(H2("12.4 Birim ekonomisi ve üç yıllık hedefler"));
ekle(P("Aşağıdaki değerler planlama hedefidir, tahmin değildir; varsayımlar tabloda açıkça belirtilmiştir ve pilot sonuçlarıyla güncellenecektir."));
ekle(...tablo(["Başlık", "Yıl 1 (pilot + ilk lisanslar)", "Yıl 2", "Yıl 3", "Varsayım"], [
  ["Kurumsal lisans (hastane)", "3 (pilot dönüşümü)", "8", "15", "Pilot dönüşüm oranı ≥ %60 varsayımı; yılda 5–7 yeni kurum"],
  ["Çalışma bazlı lisans", "6", "15", "30", "EBM portföyünün %50'si + dış sponsorlar"],
  ["Akademik lisans", "5", "15", "30", "Üniversite hastanelerinde araştırmacı başlatımlı çalışmalar"],
  ["Bileşen / OEM anlaşması", "1", "2", "4", "HBYS üreticileriyle Faz 4 saha testi sonrası"],
  ["Brüt marj hedefi", "%45", "%60", "%70", "Kurulum/entegrasyon hizmeti düşük marjlı; lisans ve SaaS yüksek marjlı"],
  ["Ar-Ge'ye ayrılan pay", "Yatırım bütçesi", "Gelirin %35'i", "Gelirin %30'u", "Model ve altyapı sürdürme maliyeti"],
], [2, 1.6, 1.1, 1.1, 2.6]));
ekle(H2("12.5 Satış kanalları ve referans müşteri planı"));
ekle(P("İlk kanal EBM'nin kendi operasyonudur: EBM'nin yürüteceği çalışmalarda sponsor görünümü sponsora açılır ve merkez kurulumları pilot sözleşmeleriyle yapılır; böylece ürün, dış satış görüşmelerinden önce gerçek çalışmalarda kanıt üretir. İkinci kanal pilot hastanelerin referansıyla diğer araştırma hastaneleri ve üniversitelerdir; yerli ürün geliştiricilerinin klinik doğrulamasında kullanım ayrıca referans oluşturur. Üçüncü kanal HBYS üreticileriyle OEM ortaklığıdır: üreticinin kurulu tabanı üzerinden araştırma modülü olarak sunum. Dördüncü aşamada Türkçe konuşan ülkeler ve MENA bölgesi için dil uyarlaması planlanır; mimari dil bağımlı bileşenleri değiştirilebilir tutar."));
ekle(H2("12.6 Savunulabilirlik"));
ekle(...tablo(["Savunulabilirlik kaynağı", "Açıklama"], [
  ["Türkçe klinik model ve değerlendirme seti", "Türkçe klinik metin için eğitilmiş model ve klinisyen etiketli set oluşturmak yıllar süren klinik erişim gerektirir; yurt dışı oyuncular için giriş engeli"],
  ["Merkez performans endeksi (ağ etkisi)", "Her yeni çalışma ve merkez kıyaslama havuzunu büyütür; tahminler ve endeks zamanla kuvvetlenir; sonradan girenler aynı veri derinliğine sahip olamaz"],
  ["Uyum paketi", "Validasyon dosyası, Part 11/Annex 11 uyumu ve KVKK etki değerlendirmesi ürünle teslim edilir; hastane ve sponsor için denetim riski düşer, geçiş maliyeti artar"],
  ["Operasyon bilgisi", "Ürün EBM'nin CRO/SMO operasyonundaki ihtiyaçlardan doğmuştur; iş akışları gerçek kullanıcı ihtiyacıyla şekillenmiş ve EBM'nin operasyon ekibiyle birlikte tasarlanmıştır"],
  ["Fikri mülkiyet", "Yazılım tescili; kimliksizleştirme ile kanıta bağlı eşleştirme yöntemi için patent başvurusu (Faz 5)"],
], [2.4, 5.4]));
ekle(H2("12.7 Mevcut çözümlerle karşılaştırma"));
ekle(...tablo(["Özellik", "Yurt dışı CTMS / eşleştirme çözümleri", "Yerel EDC ve dokümantasyon araçları", "EBM SmartClinical"], [
  ["Türkçe klinik serbest metin işleme", "Yok veya sınırlı", "Yok", "Var (Türkçe Klinik BDM, kural tabanlı geri düşme)"],
  ["Hasta verisinin kurum içinde kalması", "Bulut; veri aktarımı gerekir", "Çoğunlukla kurum içi", "Hastane içi kurulum; BDM ve federe güncelleme dahil"],
  ["Uçtan uca yaşam döngüsü", "Parçalı ürün ailesi", "Yalnızca veri toplama", "Tek platform"],
  ["Merkez zekâsı ve kıyaslama", "Üst segment ürünlerde, kapalı veri", "Yok", "Var, açıklanabilir, performans endeksi"],
  ["Risk bazlı izlem (ICH E6 R3)", "Var", "Yok", "Var, anomali tespitiyle"],
  ["Sponsor için salt okunur özet", "Var", "Kısmen", "Var"],
  ["Part 11 / Annex 11 uyumu ve CSV dosyası", "Var", "Değişken", "Var, ürünle teslim"],
  ["Akademik çalışmalar için erişilebilir lisans", "Hayır", "Kısmen", "Evet"],
  ["Açık değerlendirme seti ve model kartı", "Hayır", "Hayır", "Evet (TR-KlinikBench)"],
], [2.2, 2.1, 1.9, 2.2]));

// 13 Etki modeli
ekle(H1("13. Etki modeli"));
ekle(kisaca("Bir araştırma birkaç ay erken biterse milyonlarca lira tasarruf edilir ve hastalar tedaviye daha erken ulaşır; bu bölüm bu etkiyi açık varsayımlarla hesaplar."));
ekle(P("Etki, varsayımları açık bir parametrik modelle hesaplanmıştır; her değer platformdaki etki hesaplayıcısıyla sponsorun kendi verileriyle yeniden üretilebilir."));
ekle(H2("13.1 Çalışma düzeyinde etki"));
ekle(P("120 gönüllü hedefli, altı merkezli bir faz III çalışmasında toplam kazanım hızının ayda 5 hastadan ön tarama ile %20 artarak 6 hastaya çıkması, hedefe ulaşma süresini 24 aydan 20 aya indirir. Aylık sabit maliyetin 400.000 TL olduğu varsayımıyla dört aylık kısalma yaklaşık 1,6 milyon TL sabit maliyet tasarrufu anlamına gelir; pazara dört ay erken giriş geliri bu hesaba dahil değildir. Risk bazlı izlemin düşük riskli merkezlerde yerinde ziyaret sıklığını azaltması CRA seyahat ve zaman maliyetini ayrıca düşürür; bu etki pilotta ölçülecektir."));
ekle(H2("13.2 Pazar ölçeğinde etki"));
ekle(...tablo(["Parametre", "Varsayım", "Not"], [
  ["Yıllık yerli sponsorlu çok merkezli çalışma sayısı (hedef kitle)", "60", "TİTCK yıllık onay istatistiklerinden yerli sponsor payı ile doğrulanacak; planlama değeri"],
  ["Platform penetrasyonu (yıl 3)", "%25 (15 çalışma)", "Bölüm 12.4 hedefleriyle tutarlı"],
  ["Çalışma başına ortalama süre kısalması", "3 ay", "Pilotta ölçülecek; %15–25 kazanım artışına karşılık gelir"],
  ["Çalışma başına aylık sabit maliyet", "300–500 bin TL", "Çalışma büyüklüğüne göre; sponsor beyanlarıyla güncellenecek"],
  ["Yıl 3'te sabit maliyet tasarrufu", "13–22 milyon TL/yıl", "15 çalışma × 3 ay × 300–500 bin TL"],
  ["Erken pazara giriş etkisi", "Hesaba dahil değil", "Ürün başına değişir; yerli ürünlerde ithal ikamesi etkisi ayrıca değerlendirilir"],
  ["Uluslararası sponsorlu çalışmalarda Türkiye'nin payı", "Dolaylı", "Hızlı aktivasyon ve kazanım, merkez seçiminde Türkiye'yi öne çıkarır; döviz girdisi"],
  ["Hasta erişimi", "Yıl 3'te yaklaşık 1.500 ek gönüllü/yıl", "15 çalışma × ortalama 100 gönüllü; onkolojide yenilikçi tedaviye erişim"],
], [2.6, 1.8, 3.4]));
ekle(P("Modelin en duyarlı olduğu parametre kazanım artışıdır; bu nedenle gölge mod pilotunun birincil çıktısı, ön tarama süresi ile birlikte, kazanım hızındaki gerçekleşen değişimdir."));

// 14 Yol haritasi ve riskler
ekle(H1("14. Yol haritası ve riskler"));
ekle(kisaca("Ar-Ge programı boyunca planlanan geliştirmeler ve en önemli riskler (veri azlığı, hastanelerde donanım eksikliği, yanlış eşleştirme) ve her risk için alınan önlem."));
ekle(H2("14.1 Yol haritası"));
ekle(...tablo(["Aşama", "Zamanlama", "Başlıca içerik"], [
  ["Kısa vade", "Programın ilk altı ayı", "MedDRA ve ATC otomatik kodlama önerisi; merkez zekâsında çalışma türü ve etik kurul süresi kovaryatları; veritabanı migrasyon altyapısı; LDAP/SSO"],
  ["Orta vade", "Programın ikinci yarısı", "HBYS üreticileriyle sertifikalı FHIR entegrasyonu; çok merkezli kurulumlar için merkezi sponsor toplayıcı; SDTM dışa aktarım; e-onam entegrasyonu; ilk federe tur"],
  ["Program sonu", "18. ay", "Nicemlenmiş Türkçe Klinik BDM'nin hastane içi dağıtımı; gölge mod pilotuyla doğrulanmış eşleştirme; TR-KlinikBench'in ilk yayımı; validasyon dosyasının tamamlanması; THS 7 ürün"],
  ["Program sonrası", "Ticari yaygınlaşma", "Çok dilli uyarlama (MENA); federe güncellemenin düzenli turları; gerçek yaşam verisi çalışmaları için OMOP tabanlı analiz katmanı"],
], [1.3, 1.7, 5]));
ekle(H2("14.2 Riskler ve azaltım"));
ekle(...tablo(["Risk", "Etki", "Azaltım"], [
  ["Türkçe tıbbi derlemin yeterli hacimde toplanamaması", "BDM performansı hedefin altında kalır", "Çok merkezli veri paylaşım protokolleri; federe eğitim (veri taşınmadan); sentetik örnek üretimi; kural tabanlı ve kalıp tabanlı yolun üründe kalması"],
  ["Hastanelerde GPU altyapısının bulunmaması", "BDM kullanılamaz", "Nicemlenmiş CPU sürümü; kural tabanlı mod; EBM barındırmalı BDM (yalnızca kimliksizleştirilmiş veri ile)"],
  ["HBYS entegrasyonunda üretici bağımlılığı", "Hasta havuzu alınamaz", "FHIR R4 standardı; CSV yükleme yolu; üreticilerle Faz 4 saha testi ve OEM ortaklığı"],
  ["Yanlış pozitif / negatif eşleştirme", "Uygun olmayan hasta aday listesine girer veya uygun hasta kaçar", "Araştırmacı onayı zorunlu; kaynak cümle gösterimi; gölge mod ile sürekli ölçüm; belirsizde güvenli taraf"],
  ["Regülasyon sınıflandırması (tıbbi yazılım)", "Pazara sunum gecikmesi", "Karar destek sınırlarının açık tanımı; Faz 5'te sınıflandırma analizi; IEC 62304 uyumlu yaşam döngüsü"],
  ["Pilot dönüşümünün düşük kalması", "Gelir hedefleri sarkar", "Pilot tasarımı ödeme kararını verecek paydaşa (sponsor, hastane yönetimi) görünür değer üretir: sponsor görünümü, performans endeksi, pilot raporu"],
  ["Kullanıcı kabulü (araştırmacı iş yükü algısı)", "Düşük kullanım", "Rol bazlı sade arayüz; etiketlemenin iş akışına gömülmesi; pilotta SUS ölçümü"],
], [2.2, 1.8, 3.8]));

// 15 Teknik ozellikler
ekle(H1("15. Teknik özellikler özeti"));
ekle(kisaca("Bilgi işlem ekipleri için kurulum gereksinimleri, entegrasyon yolları ve yedekleme özeti."));
ekle(...tablo(["Başlık", "Özellik"], [
  ["Sunucu gereksinimi (uygulama)", "4 çekirdek, 8 GB bellek, 100 GB disk (TMF hariç); Linux; Docker veya systemd"],
  ["Sunucu gereksinimi (BDM)", "Nicemlenmiş 7–8B model için 16 GB VRAM'li GPU önerilir; CPU modunda 32 GB bellek"],
  ["Veritabanı", "PostgreSQL 16; geliştirme ve küçük kurulumlarda SQLite"],
  ["İstemci", "Güncel tarayıcı; ek yazılım gerekmez; kapalı ağda çalışır"],
  ["Kimlik doğrulama", "Yerel hesaplar, PBKDF2-SHA256, hesap kilitleme; API anahtarı (geçerlilik süreli, iptal edilebilir); LDAP/AD ve SSO yol haritasında"],
  ["Entegrasyon", "REST API v1 (OpenAPI), FHIR R4 (okuma ve ResearchStudy/ResearchSubject), CSV hasta havuzu yükleme, CDISC ODM 1.3.2, CSV, OMOP CDM v5.4, klinik NLP servis uçları"],
  ["Yedekleme", "Günlük veritabanı ve dosya yedeği; 7 günlük, 30 günlük ve uzun dönem saklama; SHA-256 bütünlük"],
  ["Loglama ve izleme", "Uygulama logları hasta verisi içermez; sağlık uç noktası; denetim izi zinciri doğrulama betiği"],
  ["Test ve kalite", "390 otomatik test (servis, model, web, denetim, değerlendirme seti); statik analiz; değişiklik günlüğü"],
  ["Diller", "Arayüz Türkçe; kriter ayrıştırıcı Türkçe ve İngilizce protokol metinlerini destekler"],
], [2.2, 5.6]));

// Ek A: sade sozluk
ekle(H1("Ek A. Sade sözlük"));
ekle(P("Dokümanda geçen terimlerin uzman olmayan okuyucu için kısa açıklamaları."));
ekle(...tablo(["Terim", "Ne demek?"], [
  ["Klinik araştırma", "Yeni bir ilaç, aşı veya cihazın gerçek hastalar üzerinde güvenli ve etkili olduğunu kanıtlamak için yürütülen, sıkı kurallara bağlı çalışma"],
  ["Protokol", "Araştırmanın kuralları: kimler katılabilir, hangi tedavi verilir, hangi kontroller ne zaman yapılır"],
  ["Dahil etme / hariç tutma kriterleri", "Bir hastanın araştırmaya katılabilmesi için taşıması gereken ve taşımaması gereken özellikler"],
  ["Sponsor", "Araştırmayı finanse eden ve sorumluluğunu taşıyan kuruluş (genellikle ilaç veya cihaz firması)"],
  ["CRO / SMO", "Sponsor adına araştırmayı yürüten şirket (CRO) ve hastanelerde araştırma ekibini yöneten şirket (SMO)"],
  ["Merkez", "Araştırmanın yürütüldüğü hastane"],
  ["Araştırmacı", "Araştırmayı hastanede yürüten doktor"],
  ["Koordinatör", "Hastanede hasta kayıtlarını, randevuları ve formları yöneten araştırma hemşiresi veya uzmanı"],
  ["CRA (monitör)", "Hastaneleri ziyaret edip kayıtların doğru ve kurallara uygun olduğunu kontrol eden uzman"],
  ["Etik kurul ve TİTCK", "Araştırmanın başlaması için onay veren bağımsız kurul ve Türkiye İlaç ve Tıbbi Cihaz Kurumu"],
  ["HBYS", "Hastane bilgi yönetim sistemi; hastanenin tüm hasta kayıtlarını tutan yazılım"],
  ["Kimliksizleştirme", "Bir kayıttan kişiyi tanımlayan bilgilerin (isim, kimlik numarası, telefon, tarih gibi) silinmesi veya maskelenmesi"],
  ["Büyük dil modeli (BDM)", "Metni okuyup anlayabilen ve metin üretebilen yapay zekâ modeli; SmartClinical'da Türkçe tıbbi metinler için özelleştirilmiştir"],
  ["Halüsinasyon", "Yapay zekânın kaynağı olmayan, uydurma bir bilgi üretmesi; SmartClinical kaynak gösteremeyen cevapları reddeder"],
  ["Gölge mod", "Yapay zekânın önerilerinin kullanıcılara gösterilmeden kaydedilip mevcut yöntemin sonuçlarıyla karşılaştırılması; sistemin gerçekten işe yarayıp yaramadığını ölçme yöntemi"],
  ["Duyarlılık", "Gerçekten uygun olan hastaların yüzde kaçını sistemin yakaladığı"],
  ["eCRF", "Elektronik hasta formu; araştırmada her hasta için toplanan verilerin girildiği dijital form"],
  ["Randomizasyon", "Gönüllülerin tedavi kollarına kura ile, kimsenin önceden bilemeyeceği biçimde dağıtılması"],
  ["Tablo 1", "Araştırma yayınlarındaki ilk tablo: gönüllülerin başlangıç özelliklerinin kollara göre özeti"],
  ["Protokol sapması", "Araştırmanın kurallarından herhangi bir sapma; kök nedeni ve düzeltici adımıyla kapatılır"],
  ["Advers olay / SAE", "Araştırma sırasında hastada görülen istenmeyen etki; ciddi olanlar (hastaneye yatış gibi) belirli sürede bildirilmek zorundadır"],
  ["Risk bazlı izlem (KRI / QTL)", "Her hastaneyi aynı sıklıkla ziyaret etmek yerine ölçülen risk göstergelerine göre dikkatin sorunlu hastanelere yönlendirilmesi"],
  ["TMF", "Araştırmanın tüm resmi belgelerinin tutulduğu arşiv (çalışma ana dosyası)"],
  ["Denetim izi", "Sistemde kimin, ne zaman, neyi değiştirdiğinin silinemez kaydı"],
  ["Elektronik imza", "Kullanıcının bir işlemi parolasını yeniden girerek onaylaması; ıslak imzanın dijital karşılığı"],
  ["FHIR / OMOP / CDISC", "Sağlık verilerinin farklı sistemler arasında aynı biçimde paylaşılmasını sağlayan uluslararası standartlar"],
  ["Federe öğrenme", "Hastanelerin verilerini paylaşmadan, yalnızca modelin öğrendiklerini paylaşarak ortak bir yapay zekâ modeli geliştirmesi"],
  ["THS (teknoloji hazırlık seviyesi)", "Bir teknolojinin fikirden (1) kanıtlanmış ürüne (9) kadar olgunluğunu gösteren ölçek"],
  ["MAPE / AUC", "Tahmin modellerinin başarısını ölçen iki istatistik: ortalama yüzde hata (düşük iyi) ve ayırt etme gücü (1'e yakın iyi)"],
], [2.2, 5.6]));

ekle(...bosluk(1));
ekle(P("Bu doküman ürünün bugünkü durumunu tanımlar; işlevler ve ölçümler ürün geliştikçe güncellenir. Teknik sorular için yazılım ekibi, ticari sorular için EBM iş geliştirme birimi ile iletişime geçilebilir.", { italics: true, color: GRI, size: 20 }));

// ---------------------------------------------------------------- belge
const doc = new Document({
  creator: "EBM Klinik Araştırma Hizmetleri",
  title: "EBM SmartClinical – Ürün Tanıtım ve Teknik Özet Dokümanı",
  description: "Ürün tanıtım, teknik özet ve yatırım dokümanı",
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 32, bold: true, color: LACIVERT, font: FONT }, paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 26, bold: true, color: TURKUAZ, font: FONT }, paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 23, bold: true, color: LACIVERT, font: FONT }, paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: "madde", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 300 } } } },
                                      { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1000, hanging: 300 } } } }] },
      { reference: "sira", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 340 } } } }] },
    ],
  },
  features: { updateFields: true },
  sections: [{
    properties: { page: { size: { width: SAYFA_GENISLIK, height: 16838 }, margin: { top: 1134, right: KENAR_BOSLUK, bottom: 1134, left: KENAR_BOSLUK } } },
    headers: { default: new Header({ children: [new Paragraph({ children: [run("EBM SmartClinical · Ürün Tanıtım, Teknik Özet ve Yatırım Dokümanı", { size: 16, color: GRI })], alignment: AlignmentType.RIGHT, border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: KENAR, space: 4 } } })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ children: [run("Gizli – EBM Klinik Araştırma Hizmetleri   |   Sayfa ", { size: 16, color: GRI }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: GRI })], alignment: AlignmentType.CENTER })] }) },
    children: icerik,
  }],
});

Packer.toBuffer(doc).then(buf => { fs.writeFileSync(CIKTI, buf); console.log("yazildi", CIKTI, buf.length); });
