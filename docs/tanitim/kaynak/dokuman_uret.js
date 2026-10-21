// EBM SmartClinical - Urun Tanitim Dokumani uretici
const fs = require("fs");
const path = require("path");
const D = require("docx");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, AlignmentType,
  ImageRun, PageBreak, TableOfContents, ShadingType, BorderStyle, LevelFormat, Footer, Header, PageNumber,
  VerticalAlign, TabStopType,
} = D;

const KOK = "/home/user/EBM-Yaz-l-m";
const GORSEL = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const CIKTI = process.argv[3];

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

// Kapak
ekle(...bosluk(6));
ekle(new Paragraph({ children: [run("EBM SmartClinical", { size: 56, bold: true, color: LACIVERT })], alignment: AlignmentType.LEFT, spacing: { after: 120 } }));
ekle(new Paragraph({ children: [run("Klinik Araştırma Yönetimi ve Türkçe Klinik Karar Destek Platformu", { size: 30, color: TURKUAZ })], spacing: { after: 600 } }));
ekle(new Paragraph({ children: [run("Ürün Tanıtım ve Teknik Özet Dokümanı", { size: 26, bold: true })], spacing: { after: 120 } }));
ekle(new Paragraph({ children: [run("Yazılım sürümü 1.4.2  ·  Doküman sürümü 1.1  ·  Ekim 2026", { size: 22, color: GRI })], spacing: { after: 1800 } }));
ekle(new Paragraph({ children: [run("Hazırlayan: EBM Klinik Araştırma Hizmetleri – Yazılım ve Veri Bilimi Ekibi", { size: 20 })], spacing: { after: 60 } }));
ekle(new Paragraph({ children: [run("İlgili program: TÜSEB Türkiye Sağlık Veri Araştırmaları ve Yapay Zekâ Uygulamaları Enstitüsü – \"Ulusal Klinik Türkçe Büyük Dil Modeli ve Karar Destek Altyapısının Geliştirilmesi\" proje alanı", { size: 20 })], spacing: { after: 60 } }));
ekle(new Paragraph({ children: [run("Gizlilik: Bu doküman EBM'nin ticari ve teknik bilgilerini içerir; yalnızca değerlendirme amacıyla paylaşılmıştır.", { size: 18, italics: true, color: GRI })], spacing: { after: 0 } }));

// Belge kontrol
ekle(new Paragraph({ children: [run("Belge kontrolü", { size: 24, bold: true, color: LACIVERT })], pageBreakBefore: true, spacing: { after: 160 } }));
ekle(...tablo(["Sürüm", "Tarih", "Değişiklik", "Hazırlayan / Onaylayan"], [
  ["0.9", "18.06.2026", "İlk taslak; modül tanımları ve mimari", "Yazılım Ekibi / Ürün Yöneticisi"],
  ["1.0", "22.09.2026", "Sürüm 1.4 özellikleri, ekran görüntüleri, uyum bölümü", "Yazılım Ekibi / Kalite Güvence"],
  ["1.1", "21.10.2026", "Ar-Ge göstergeleri, ticarileşme ve yol haritası bölümleri; ölçümler güncellendi", "Yazılım ve Veri Bilimi Ekibi / Genel Müdür"],
], [1, 1.4, 4.2, 2.6]));
ekle(P("Bu dokümandaki ekran görüntüleri sürüm 1.4.2'nin demo kurulumundan alınmıştır. Demo kurulumunda kullanılan tüm hasta kayıtları, çalışma ve merkez verileri sentetiktir; merkez adları kurgusaldır ve gerçek bir kurumu temsil etmez. Bölüm 8'deki ölçümler, aksi belirtilmedikçe, sistemin aynı demo verisi ve altın standart seti üzerinde kendi hesapladığı değerlerdir."));
ekle(P("Terimler: **BDM** büyük dil modeli; **HBYS** hastane bilgi yönetim sistemi; **eCRF** elektronik olgu rapor formu; **CRA** klinik araştırma uzmanı (monitör); **KRI/QTL** anahtar risk göstergesi / kalite tolerans limiti; **TMF** çalışma ana dosyası; **SDV** kaynak veri doğrulama; **RAG** erişim destekli üretim; **THS** teknoloji hazırlık seviyesi."));

ekle(new Paragraph({ children: [run("İçindekiler", { size: 24, bold: true, color: LACIVERT })], pageBreakBefore: true, spacing: { after: 160 } }));
ekle(new TableOfContents("İçindekiler", { hyperlink: true, headingStyleRange: "1-2" }));

// 1 Yonetici ozeti
ekle(H1("1. Yönetici özeti"));
ekle(P("EBM SmartClinical, bir klinik araştırmanın tasarımından arşivine kadar bütün yaşam döngüsünü tek bir platformda yöneten ve bu işletim katmanının üzerine hastane içinde çalışan bir Türkçe Klinik Büyük Dil Modeli ile üç karar destek işlevi ekleyen bir yazılım ürünüdür: protokole uygun hastaların otomatik ön taranması, merkez seçimi ile hasta kazanımının öngörülmesi ve çalışma yürütümündeki risklerin erken tespiti."));
ekle(P("Ürün, EBM'nin sözleşmeli araştırma kuruluşu (CRO) ve merkez yönetim kuruluşu (SMO) olarak yürüttüğü operasyonların ihtiyaçlarından doğmuştur. Çekirdek modüller (çalışma, merkez, gönüllü ve eCRF yönetimi, güvenlik raporlama, TMF, denetim izi ve e-imza) sürüm 1.0'dan bu yana EBM'nin iç operasyonlarında kullanılmaktadır. Yapay zekâ katmanı (Türkçe Klinik BDM, eşleştirme motoru, merkez zekâsı ve risk bazlı izlem modelleri) sürüm 1.3–1.4 ile platforma entegre edilmiş olup laboratuvar ortamında ve sentetik veriyle doğrulanmıştır; gerçek hastane ortamında prospektif doğrulama ise bu dokümanın ilgili olduğu Ar-Ge projesinin konusudur."));
ekle(P("Platformun ayırt edici özellikleri şunlardır:"));
ekle(madde("**Uçtan uca kapsam.** İlaç, biyobenzer, tıbbi cihaz, in vitro tanı, gözlemsel, kayıt (gerçek yaşam verisi) ve araştırmacı başlatımlı çalışmalar aynı veri modeli ve aynı akışla yönetilir; çalışma türü, başvuru şablonlarını ve güvenlik bildirim kurallarını belirler."));
ekle(madde("**Türkçe klinik metni anlayan, hastane içinde çalışan yapay zekâ.** Epikriz, patoloji ve radyoloji raporları kimliksizleştirilir, protokol kriterleri hesaplanabilir sorguya dönüştürülür ve her öneri kaynak cümlesiyle birlikte sunulur. Hasta verisi kurum dışına çıkmaz."));
ekle(madde("**İnsan kararı merkezde.** Hiçbir model çıktısı tek başına işlem yapmaz: eşleştirme önerileri araştırmacı onayı bekler, risk uyarıları CRA tarafından kapatılır, tüm kararlar gerekçesiyle denetim izine yazılır."));
ekle(madde("**Düzenleyici uyum tasarımın parçası.** ICH E6(R3) risk temelli kalite yönetimi, 21 CFR Part 11 / EU Annex 11 elektronik kayıt ve imza gereklilikleri, KVKK ve DIA TMF referans modeli ürünün içinde uygulanır; bilgisayarlı sistem validasyon dosyası (URS, FRS, risk analizi, IQ/OQ/PQ) ürünle birlikte teslim edilir."));
ekle(madde("**Ölçülebilir Ar-Ge.** Platform kendi model performansını (duyarlılık, halüsinasyon oranı, MAPE, AUC, ön tarama süresi) sürekli ölçer ve proje başarı ölçütleriyle yan yana raporlar (Bölüm 8)."));
ekle(P("Bu doküman, ürünün mevcut durumunu, teknik mimarisini, uyum yaklaşımını, Ar-Ge göstergelerini ve ticarileşme planını değerlendirme kurullarına ve potansiyel kullanıcı kurumlara sunmak amacıyla hazırlanmıştır."));

// 2 Problem
ekle(H1("2. Problem tanımı ve ihtiyaç"));
ekle(P("Yerli ilaç, biyobenzer, tıbbi cihaz ve tanı kitlerinin ürünleşmesi klinik araştırma olmadan mümkün değildir. Buna karşın klinik araştırma operasyonlarında üç yapısal darboğaz sürmektedir:"));
ekle(sira("**Uygun hastalar görünmez kalıyor.** Protokol kriterlerini karşılayan hastalar HBYS'de yapılandırılmış alanlarda değil, Türkçe serbest metin raporlarda tanımlıdır. Merkez koordinatörleri hasta dosyalarını elle tarar; bu hem yavaştır hem de kriter anlaşılmasına bağlı tutarsızlık üretir."));
ekle(sira("**Merkez seçimi deneyime dayalı.** Fizibilite anketleri merkezlerin öz beyanına dayanır; gerçekleşen kazanım ile beyan arasındaki fark çalışma takvimini kaydırır. Etik kurul, TİTCK ve sözleşme süreçlerindeki gecikmeler ancak gerçekleştikten sonra fark edilir."));
ekle(sira("**Riskler geç görülüyor.** Veri kalitesi, protokol sapması ve güvenlik bildirim sorunları çoğunlukla yerinde izlem ziyaretlerinde, yani olaydan haftalar sonra saptanır. ICH E6(R3)'ün öngördüğü risk temelli izlem, merkezler arası karşılaştırmalı göstergeler olmadan uygulanamaz."));
ekle(P("Piyasadaki klinik araştırma yönetim ve hasta eşleştirme çözümleri büyük ölçüde yurt dışı kaynaklı, İngilizce odaklı ve bulut tabanlıdır. Türkçe klinik metni işleyemezler, hastane verisinin kurum dışına çıkmasını gerektirirler ve bu nedenle KVKK çerçevesinde Türkiye'deki hastanelerde uygulanamazlar. Ayrıca lisans maliyetleri yurt içi akademik ve araştırmacı başlatımlı çalışmalar için erişilebilir değildir."));
ekle(P("SmartClinical bu boşluğu, Türkçe klinik metni anlayan, hastane ağı içinde çalışan ve klinik araştırma operasyonunun tamamını kapsayan yerli bir platformla doldurmayı hedefler. Geliştirilen Türkçe klinik model ve kimliksizleştirme altyapısı, klinik araştırma dışındaki ulusal klinik karar destek uygulamaları için de yeniden kullanılabilir bir bileşen olarak tasarlanmıştır (Bölüm 6.4)."));

// 3 Urun genel bakis
ekle(H1("3. Ürüne genel bakış"));
ekle(H2("3.1 Kapsam ve desteklenen çalışma türleri"));
ekle(P("Platform, çalışma türünden bağımsız ortak bir veri modeli üzerine kuruludur. Çalışma oluşturulurken seçilen tür; başvuru kurumlarını ve şablonlarını, varsayılan risk göstergelerini, güvenlik bildirim kurallarını ve eCRF şablon setini belirler."));
ekle(...tablo(["Çalışma türü", "Örnek", "Türe özgü davranış"], [
  ["İlaç (Faz I–IV)", "Onkoloji faz III, biyoeşdeğerlik", "TİTCK klinik araştırma başvurusu, SUSAR hızlandırılmış bildirim, CTCAE derecelendirme, randomizasyon kolları"],
  ["Biyobenzer", "İnsülin glargin karşılaştırma", "Non-inferiorite tasarımı, referans ürün kolu, immünojenisite formları"],
  ["Tıbbi cihaz", "Koroner stent pivotal", "Cihaz olumsuz olay sınıflaması, tek kollu / tarihsel kontrol tasarımı, kullanım hatası kaydı"],
  ["In vitro tanı (IVD)", "HPV genotipleme performansı", "Örnek bazlı kayıt, referans yöntem karşılaştırması, performans faz etiketi"],
  ["Gözlemsel / kayıt (RWE)", "KOAH gerçek yaşam kaydı", "Girişimsel olmayan başvuru yolu, azaltılmış eCRF, yüksek hacimli kayıt"],
  ["Araştırmacı başlatımlı (akademik)", "Üniversite faz IV güvenlik", "Tek merkez akışı, sadeleştirilmiş TMF, düşük maliyet lisans sınıfı"],
  ["İleri tedavi (ATMP)", "Hücre/gen tedavisi", "Uzun dönem takip vizit şablonu, ürün zinciri kayıtları (1.5 sürümü)"],
], [1.6, 1.8, 4.4]));
ekle(H2("3.2 Kullanıcı rolleri"));
ekle(P("Erişim, on rol üzerinden ince taneli izinlerle yönetilir. Araştırmacı ve koordinatör yalnızca kendi merkezinin kayıtlarını görür; sponsor ve denetçi rolleri kimliksizleştirilmiş özet verilere salt okunur erişir."));
ekle(...tablo(["Rol", "Başlıca işlevler"], [
  ["Araştırmacı", "Eşleştirme önerilerini inceleme ve onaylama, onam, randomizasyon, advers olay bildirimi, kriter onayı"],
  ["Çalışma koordinatörü", "Gönüllü kaydı, vizit takvimi, eCRF veri girişi, sorgu cevaplama"],
  ["CRA (monitör)", "Risk bazlı izlem panosu, uyarı yönetimi, SDV, sorgu açma, ziyaret planlama ve raporu"],
  ["Proje yöneticisi", "Çalışma kurulumu, merkez seçimi, başvuru takibi, aşama geçişleri, fizibilite raporu"],
  ["Veri yöneticisi", "eCRF tasarımı, veri kilidi, CDISC ODM / CSV / OMOP dışa aktarım"],
  ["Farmakovijilans", "SAE/SUSAR değerlendirme, TİTCK ve etik kurul bildirim takibi"],
  ["Biyoistatistikçi", "Kilitli veri setlerine erişim, dışa aktarım"],
  ["Sponsor", "Portföy ve çalışma özetleri, kazanım projeksiyonu, risk ısı haritası (salt okunur)"],
  ["Denetçi / gözlemci", "Denetim izi, e-imza kayıtları, TMF (salt okunur)"],
  ["Sistem yöneticisi", "Kullanıcı ve rol yönetimi, sistem durumu, BDM yapılandırması, zincir doğrulama"],
], [1.8, 6]));
ekle(H2("3.3 Klinik araştırma yaşam döngüsü"));
ekle(P("Her çalışma dokuz aşamalı bir yaşam döngüsü üzerinde ilerler. Aşama geçişleri proje yöneticisi tarafından gerekçeyle yapılır; her aşamanın kontrol listesi platform tarafından izlenir ve eksikler uyarı olarak gösterilir. Şekil 2, aşamaları ve her aşamada platformun sağladığı işlevleri özetler."));
ekle(...sekil("sekil_02_yasam_dongusu.png", "Klinik araştırma yaşam döngüsü ve platform işlevleri"));

// 4 Mimari
ekle(H1("4. Platform mimarisi"));
ekle(H2("4.1 Katmanlı yapı"));
ekle(P("SmartClinical, hastane bilgi işlem ekiplerinin işletebileceği sadelikte tasarlanmış modüler bir mimariye sahiptir. Uygulama tek bir sunucu süreci olarak çalışır; yalnızca GPU gerektiren bileşenler (BDM ve gömme sunucusu) ayrı servislerdir. Şekil 1 katmanları ve çapraz kesen hizmetleri gösterir."));
ekle(...sekil("sekil_01_mimari.png", "Platform mimarisi"));
ekle(...tablo(["Katman", "Bileşenler", "Teknoloji"], [
  ["Sunum", "Rol bazlı web panelleri, yazdırılabilir raporlar, REST API v1, OpenAPI belgeleri", "Sunucu tarafı render (Jinja2), harici JavaScript kütüphanesi yok (kapalı ağ uyumu)"],
  ["Uygulama", "Çalışma, merkez, başvuru, eşleştirme, eCRF, güvenlik, RBM, TMF modülleri", "Python 3.11+, FastAPI, SQLAlchemy 2.0"],
  ["Yapay zekâ", "Türkçe Klinik BDM istemcisi, kriter motoru, RAG, koruma katmanı, kimliksizleştirme, merkez zekâsı, KRI/anomali motoru", "NumPy/SciPy; BDM: vLLM / llama.cpp / Ollama sağlayıcıları; LoRA eğitim hattı (ml/)"],
  ["Çapraz kesen", "Hash zincirli denetim izi, e-imza, RBAC, ortak veri modeli", "PBKDF2-SHA256 parola, SHA-256 zincir, FHIR R4 / OMOP CDM v5.4 eşlemeleri"],
  ["Veri ve entegrasyon", "İşlem veritabanı, TMF dosya deposu, HBYS FHIR adaptörü, dışa aktarım", "PostgreSQL 16 (geliştirmede SQLite), CDISC ODM 1.3.2, CSV, OMOP CSV"],
], [1.4, 3.6, 3]));
ekle(H2("4.2 Hastane içi kurulum"));
ekle(P("Platform, hastane ağı içinde (on-premise) kurulacak şekilde paketlenmiştir: Docker Compose veya systemd ile kurulum, nginx üzerinden TLS, PostgreSQL ve dosya deposu için yedekleme betikleri, uygulama veritabanı kullanıcısı için denetim izi tablolarında güncelleme ve silmeyi engelleyen yetki tanımları. BDM, hastanedeki GPU sunucusunda nicemlenmiş (GGUF Q4/Q8) olarak çalışır; GPU bulunmayan kurulumlarda llama.cpp ile CPU üzerinde daha düşük hızda ya da tamamen kural tabanlı modda çalışabilir. Şekil 5 kurulum topolojisini gösterir."));
ekle(...sekil("sekil_05_kurulum.png", "Hastane içi kurulum topolojisi", 6.2));
ekle(P("Sponsor ve CRA erişimi, hastane tarafından tanımlanan VPN veya ters vekil üzerinden, yalnızca kimliksizleştirilmiş özet verilere ve çalışma operasyon verilerine sınırlıdır. Çok merkezli çalışmalarda her hastanenin kendi kurulumu kendi hasta havuzunu tarar; sponsor görünümü kurulumlar arasında yalnızca operasyonel özetleri toplar (1.5 sürümünde merkezi toplayıcı servis)."));

// 5 Moduller
ekle(H1("5. Modüller"));
ekle(P("Bu bölümde her modülün işlevi, ürün içindeki yeri ve ekran görüntüleri verilmektedir. Ekranlar demo kurulumundan alınmıştır; veriler sentetiktir."));
ekle(H2("5.1 Genel bakış ve çalışma yönetimi"));
ekle(P("Genel bakış ekranı, kullanıcının rolüne göre düzenlenmiş bir iş listesi (yaklaşan vizitler, inceleme bekleyen aday hastalar, açık sorgular, bildirim bekleyen ciddi advers olaylar, planlı ziyaretler, açık risk uyarıları) ile portföydeki çalışmaların kayıt ilerlemesini bir arada gösterir."));
ekle(...sekil("02_pano.png", "Genel bakış ekranı (sistem yöneticisi görünümü)"));
ekle(P("Çalışma kaydı; protokol sürümleri ve değişiklik notları, randomizasyon kolları, aşama kontrol listesi, planlanan–gerçekleşen kayıt eğrisi ve çalışmaya ait denetim izini içerir. Aşama geçişleri gerekçe ile yapılır ve denetim izine yazılır."));
ekle(...sekil("04_calisma_ozet.png", "Çalışma özeti: yaşam döngüsü, kayıt eğrisi ve aşama kontrol listesi"));
ekle(H2("5.2 Protokol ve kriter yapılandırma"));
ekle(P("Dahil etme ve hariç tutma kriterleri protokolden satır satır yapıştırılır. Her kriter, Türkçe Klinik BDM (ya da BDM sunucusu olmayan kurulumlarda kural tabanlı ayrıştırıcı) tarafından hesaplanabilir bir sorguya dönüştürülür: yaş, cinsiyet, tanı (ICD-10), laboratuvar (LOINC, birim normalizasyonu), ilaç (ATC), performans ölçeği (ECOG, Karnofsky, NYHA), gebelik, tedavi geçmişi, zaman penceresi ve bileşik (ve/veya/değil) koşullar desteklenir. Model, her dönüşüme bir güven değeri atar; düşük güvenli dönüşümler araştırmacı onayı bekler ve onaylanmadan yapılan eşleştirmeler \"ön tarama\" olarak etiketlenir."));
ekle(...sekil("05_protokol_kriterler.png", "Kriterlerin hesaplanabilir sorguya dönüştürülmesi ve araştırmacı onayı"));
ekle(H2("5.3 Merkez ve araştırmacı yönetimi, etik kurul ve TİTCK başvuruları"));
ekle(P("Merkez kayıt defteri; kurum türü, yatak sayısı, HBYS türü, FHIR uç noktası, terapötik alanlar, araştırmacı listesi (GCP eğitim tarihi yenileme uyarısıyla) ve geçmiş çalışmalardaki kazanım ve aktivasyon performansını tutar. Bu geçmiş, merkez zekâsı modelinin öğrenme verisidir. Çalışma düzeyinde her merkezin seçim, etik, sözleşme, başlatma ziyareti ve ilk hasta kilometre taşları planlanan–gerçekleşen tarihlerle izlenir."));
ekle(P("Etik kurul, TİTCK, kurum izni ve KVKK başvuruları; tip (ilk başvuru, önemli değişiklik, yıllık bildirim, güvenlik ve sapma bildirimi, sonlandırma), referans numarası, gönderim ve karar tarihleriyle kaydedilir. Karar süreleri merkez ve kurum bazında öğrenilir; altmış günü aşan beklemeler işaretlenir ve aktivasyon gecikme modelini besler."));
ekle(...sekil("06_merkezler.png", "Çalışma merkezleri: durum, kilometre taşları, tahmin ve risk puanı"));
ekle(H2("5.4 Protokol–hasta eşleştirme"));
ekle(P("Eşleştirme modülü, aktif merkezlerin HBYS'den FHIR R4 ile alınmış ve kimliksizleştirilmiş hasta kayıtlarını protokol kriterleriyle karşılaştırır. Akış Şekil 3'te verilmiştir. Dahil etme kriterlerinde tanı kodu varsa havuz önce ICD-10 ön filtresiyle daraltılır; ardından her hasta için her kriter önce yapısal veri üzerinde, yeterli kanıt yoksa serbest metin üzerinde değerlendirilir. Metin yolunda hasta metinleri cümle tabanlı parçalanır, BM25 ve gömme tabanlı hibrit aramayla ilgili parçalar bulunur ve BDM'den yalnızca kaynak metinde birebir geçen bir kanıt cümlesiyle karar vermesi istenir."));
ekle(...sekil("sekil_03_eslestirme_akisi.png", "Protokol–hasta eşleştirme boru hattı"));
ekle(P("Sonuçlar dört sınıfta özetlenir: uygun (tüm kriterler kanıtlı), olası (bazı kriterler belirsiz), belirsiz ve uygun değil (bir hariç tutma kriteri sağlandı veya bir dahil etme kriteri sağlanmadı). Araştırmacı, aday listesinden hastayı açtığında kriter bazında sonuç, kaynak cümle, güven ve kullanılan yöntemi (yapısal / BDM / kural) görür; kararını (onam görüşmesine çağır, ek bilgi gerekli, uygun değil) gerekçesiyle kaydeder. Onaylanan hasta otomatik olarak gönüllü ön tarama listesine düşer."));
ekle(...sekil("08_eslestirme.png", "Aday hasta listesi: model kararı ve araştırmacı kararı"));
ekle(...sekil("09_eslestirme_detay.png", "Aday hasta detayı: kriter bazında kanıt cümleleri ve araştırmacı kararı"));
ekle(P("Gölge mod, pilot doğrulamanın aracıdır: model önerisi araştırmacıya gösterilmeden kaydedilir, manuel ön tarama sonucuyla karşılaştırılır ve duyarlılık, özgüllük, pozitif ve negatif öngörü değerleri çalışma bazında raporlanır."));
ekle(H2("5.5 Gönüllü yönetimi ve eCRF"));
ekle(P("Gönüllü kaydı; onam tarihi ve sürümü, tarama, randomizasyon (onam olmadan randomizasyon engellenir), kol ataması, vizit takvimi (protokol penceresi ve pencere dışı uyarısı), erken ayrılma ve tarama başarısızlığı nedenlerini içerir. eCRF tanımları CDASH değişken adlarıyla eşlenmiş alanlardan oluşur; sayısal aralık, zorunlu alan ve tarih kontrolleri otomatik sorgu açar, kaydı engellemez. Tamamlanmış bir formdaki değişiklik için gerekçe zorunludur; CRA kaynak belge doğrulaması (SDV) işaretler, veri yöneticisi elektronik imza ile kilitler. Açık sorgusu olan form kilitlenemez."));
ekle(...sekil("13_gonullu_detay.png", "Gönüllü kaydı: vizit × form matrisi, advers olaylar ve sorgular"));
ekle(...sekil("14_ecrf_form.png", "eCRF veri giriş formu (CDASH eşlemeli alanlar, otomatik edit-check)"));
ekle(H2("5.6 Güvenlik raporlama"));
ekle(P("Advers olaylar MedDRA tercih edilen terim ve sistem-organ sınıfı, CTCAE derecesi, nedensellik, beklenirlik ve ciddiyet ölçütü ile kaydedilir. Ciddi olaylarda sponsor farkındalık tarihinden itibaren TİTCK bildirim süresi (ölüm veya yaşamı tehdit eden olaylarda 7, diğer ciddi olaylarda 15 gün) geri sayılır; beklenmeyen ve ilişkili ciddi olaylar SUSAR olarak işaretlenir. Bildirim gecikmeleri risk bazlı izlem modülünde SAE_GEC_BILDIRIM göstergesine yansır."));
ekle(...sekil("16_guvenlik.png", "Güvenlik modülü: AE listesi, SAE/SUSAR işaretleri ve bildirim takibi"));
ekle(H2("5.7 Merkez zekâsı"));
ekle(P("Merkez zekâsı iki model ve bir sıralama katmanından oluşur. Kazanım tahmini, merkezin kendi geçmişi ile benzer terapötik alandaki merkez havuzunu birleştiren Gamma–Poisson hiyerarşik Bayes modelidir; az verili merkezlerde tahmin havuza doğru büzülür ve aralık genişliği bu belirsizliği yansıtır. Aktivasyon gecikme riski, seçimden aktivasyona geçen sürenin sansürlü Weibull hızlandırılmış başarısızlık zamanı modeliyle kestirilir; kurum türü, önceki iş birliği ve sözleşme şablonu varlığı kovaryattır. Monte Carlo simülasyonu (2.000 yineleme) ile çalışmanın hedefe ulaşma tarihi ve zamanında bitirme olasılığı hesaplanır. Sıralama katmanı, kazanım, gecikme riski, kalite geçmişi, deneyim, rekabet ve coğrafya bileşenlerinden bileşik puan üretir ve her merkez için iki-üç cümlelik Türkçe gerekçe yazar."));
ekle(...sekil("10_merkez_zekasi.png", "Merkez zekâsı: tahminler, Monte Carlo projeksiyonu ve açıklanabilir sıralama"));
ekle(P("Sponsor fizibilite raporu, bu analizleri yazdırılabilir tek sayfalık bir rapor olarak derler (taranan, tarama başarısız, randomize, gözlenen ve tahmini hız, gecikme riski, sıralama gerekçeleri, yöntem ve sınırlar)."));
ekle(...sekil("26_fizibilite_raporu.png", "Sponsor fizibilite ve kazanım raporu", 6.0));
ekle(H2("5.8 Risk bazlı izlem"));
ekle(P("Modül, ICH E6(R3) risk temelli kalite yönetimi yaklaşımını uygular. On beş varsayılan anahtar risk göstergesi (form başına sorgu, sorgu kapanış süresi, sapma ve majör sapma, gönüllü başına advers olay, SAE geç bildirim, pencere dışı ve kaçırılan vizit, tarama başarısızlığı, erken ayrılma, veri giriş gecikmesi, SDV ve form tamamlama oranı, onam sapması, kazanım hedef gerisi) çalışma bazında eşiklerle özelleştirilir. Uyarılar hem sabit eşiklerden hem de merkezler arası dayanıklı z-skoru (medyan/MAD) ile anomali tespitinden üretilir; her uyarının \"neden tetiklendi\" açıklaması vardır. Bileşik risk puanı, merkez için izlem önerisini (uzaktan izlem, tetiklenmiş ziyaret, SDV oranı) belirler. Kalite tolerans limitleri çalışma düzeyinde izlenir."));
ekle(...sekil("11_rbm.png", "Risk bazlı izlem: merkez × KRI ısı haritası ve uyarılar"));
ekle(H2("5.9 İzlem ziyaretleri, protokol sapmaları ve TMF"));
ekle(P("Başlatma, ara izlem, kapanış, uzaktan ve tetiklenmiş ziyaretler CRA tarafından planlanır; bulgular önem derecesi ve kapanış durumuyla izlenir. Protokol sapmaları kategori (onam, uygunluk, vizit penceresi, araştırma ürünü, prosedür, güvenlik bildirimi, kaynak belge), önem derecesi, kök neden ve düzeltici faaliyetle kaydedilir. TMF modülü DIA TMF referans modeli bölgelerine göre düzenlenmiştir; her belgenin SHA-256 özeti yükleme anında alınır, onay elektronik imza ile yapılır, bölge bazında tamlık kontrolü yapılır."));
ekle(...sekil("18_tmf.png", "TMF: DIA referans modeli bölgeleri, özet değerleri ve e-imza ile onay", 6.0));
ekle(H2("5.10 Denetim izi, elektronik imza ve erişim denetimi"));
ekle(P("Her oluşturma, güncelleme, silme, görüntüleme (hasta kaydı için), giriş/çıkış, dışa aktarım ve model çalıştırma işlemi; kullanıcı, zaman, eski ve yeni değer, gerekçe ve IP adresiyle denetim izine yazılır. Kayıtlar hash zinciriyle birbirine bağlıdır; veritabanına doğrudan müdahale zincir doğrulamasında tespit edilir. Elektronik imza işlemlerinde (belge onayı, veri kilidi) parola yeniden istenir ve imzanın anlamı, zamanı ve imzalanan içeriğin özeti saklanır. Parolalar PBKDF2-SHA256 ile saklanır, beş hatalı girişte hesap kilitlenir, oturum süresi varsayılan 30 dakikadır."));
ekle(...sekil("21_denetim_izi.png", "Denetim izi: hash zincirli kayıtlar ve elektronik imzalar"));
ekle(H2("5.11 Kimliksizleştirme"));
ekle(P("HBYS'den gelen serbest metinler sisteme yazılmadan önce kimliksizleştirme modülünden geçer. Modül; TC kimlik numarası (algoritma doğrulamalı), telefon, e-posta, IBAN, plaka, tarih biçimleri, dosya ve protokol numaraları, kişi adları (unvan tetikleyicileri ve ad-soyad sözlüğü), kurum adları, il/ilçe ve adres ifadeleri ile 89 yaş üstü yaşları tespit eder. Klinik terimler beyaz liste ile korunur. Üç mod desteklenir: maskeleme, tutarlı takma ad (aynı kişi aynı metinde aynı takma adı alır) ve tarih kaydırma. İkinci geçiş doğrulaması, kalmış olabilecek şüpheli kalıpları raporlar; şüpheli kalıp içeren kayıtlar API üzerinden reddedilir."));
ekle(...sekil("20_kimliksizlestirme.png", "Kimliksizleştirme aracı: girdi, çıktı ve ikinci geçiş uyarıları"));
ekle(H2("5.12 Türkçe Klinik BDM konsolu, Ar-Ge göstergeleri ve API"));
ekle(P("BDM konsolu; kriter yapılandırma, kanıt çıkarma, çalışma odaklı klinik özet ve bağlam üzerinden soru-cevap görevlerini, koruma katmanının kararlarıyla birlikte gösterir. Ar-Ge göstergeleri sayfası model performansını proje hedefleriyle karşılaştırır (Bölüm 8). REST API, platform işlevlerini ve genel amaçlı klinik NLP uçlarını (kimliksizleştirme, ICD-10 kodlama önerisi, özet, soru-cevap, kriter yapılandırma) diğer kurumsal uygulamalara açar; HBYS entegrasyonu FHIR R4 Bundle alımı ve merkez bazlı senkronizasyon uçlarıyla yapılır."));
ekle(...sekil("19_bdm_konsol.png", "Türkçe Klinik BDM konsolu"));

// 6 BDM
ekle(H1("6. Türkçe Klinik Büyük Dil Modeli altyapısı"));
ekle(H2("6.1 Model geliştirme hattı"));
ekle(P("Model, açık kaynak 7–8 milyar parametreli bir temel modelin Türkçe tıbbi derlemle sürekli ön eğitimi ve klinik araştırma görevleri için talimat ince ayarı (LoRA/QLoRA) ile geliştirilmektedir. Derlem; kimliksizleştirilmiş epikriz, patoloji ve radyoloji raporları, klinik kılavuzlar, protokol metinleri ve klinisyen etiketli görev örneklerinden oluşur. Eğitim yapılandırmaları, veri hazırlama (temizleme, tekilleştirme, kimliksizleştirme, talimat seti üretimi), değerlendirme ve nicemleme betikleri ürünün `ml/` dizininde sürümlenir. Şekil 4 hattı özetler."));
ekle(...sekil("sekil_04_bdm_gelistirme.png", "Türkçe Klinik BDM geliştirme ve dağıtım hattı"));
ekle(H2("6.2 Görevler ve istem tasarımı"));
ekle(P("Model dört göreve özelleştirilir: (1) kriteri hesaplanabilir sorguya dönüştürme (JSON şema zorlamalı), (2) kriter için hasta metninden kanıt çıkarma (sonuç + kaynak cümle + güven), (3) çalışma odaklı klinik özet, (4) bağlam üzerinden soru-cevap. Sistem istemi modeli yalnızca verilen metne dayanmaya, bilmediğinde \"belirsiz\" demeye ve kimlik verisi üretmemeye yönlendirir."));
ekle(H2("6.3 Koruma katmanı"));
ekle(madde("**Halüsinasyon kontrolü:** modelin verdiği kanıt cümlesi kaynak parçada (normalize edilmiş biçimde) birebir bulunmuyorsa sonuç reddedilir ve \"belirsiz\"e düşürülür."));
ekle(madde("**Belirsizlik katmanı:** güven değeri eşiğin altındaki sonuçlar araştırmacı değerlendirmesine bırakılır; isteğe bağlı olarak sıcaklık > 0 ile üç örnekleme ve çoğunluk oyu uygulanır."));
ekle(madde("**Şema doğrulama ve geri düşme:** JSON çıktısı şemaya uymazsa veya BDM sunucusuna erişilemezse sistem kural tabanlı ayrıştırıcıya ve kalıp tabanlı metin değerlendirmesine düşer; bu durum denetim izine yazılır."));
ekle(madde("**Kimlik sızıntısı kontrolü:** istemde TC kimlik numarası, telefon veya e-posta kalıbı tespit edilirse istek engellenir. Servis API'sinden gelen metinler modele ulaşmadan önce kimliksizleştirilir."));
ekle(H2("6.4 Ulusal altyapı olarak yeniden kullanım"));
ekle(P("Türkçe klinik model ve etrafındaki bileşenler, klinik araştırma dışındaki kullanımlar için de erişilebilir olacak şekilde tasarlanmıştır:"));
ekle(madde("**Servis API'si:** kimliksizleştirme, ICD-10 kodlama önerisi, klinik özet, soru-cevap ve kriter yapılandırma uçları; hastane içi diğer uygulamalar (HBYS modülleri, araştırma veri ambarı, etik kurul yazılımı) tarafından çağrılabilir."));
ekle(madde("**Altın standart değerlendirme seti ve etiketleme kılavuzu:** klinisyen etiketli hasta metni–kriter çiftleri, kanıt aralıkları, etiketleyiciler arası uyum. Proje sonunda kimliksizleştirilmiş ve sentetik bileşenleri açık değerlendirme seti olarak yayımlanması planlanmaktadır."));
ekle(madde("**Kimliksizleştirme aracı:** HBYS verisinin araştırma amaçlı ikincil kullanımı için bağımsız bileşen olarak lisanslanabilir."));
ekle(madde("**Ortak veri modeli:** FHIR R4 ve OMOP CDM eşlemeleri, çok merkezli gerçek yaşam verisi çalışmalarında yeniden kullanılabilir."));

// 7 Uyum
ekle(H1("7. Düzenleyici uyum, veri koruma ve güvenlik"));
ekle(...tablo(["Çerçeve", "Platformdaki karşılığı"], [
  ["KVKK (6698 s. Kanun) ve Kişisel Sağlık Verileri Yönetmeliği", "Hastane içi işleme; kimliksizleştirme zorunlu akış; takma ad anahtarının merkezde kalması; hasta kaydı görüntülemelerinin denetim izine yazılması; veri envanteri ve etki değerlendirmesi (docs/validasyon/KVKK_etki_degerlendirmesi.md)"],
  ["İyi Klinik Uygulamaları – ICH E6(R3)", "Risk temelli kalite yönetimi: KRI, QTL, merkezler arası anomali, izlem önerisi; onam olmadan randomizasyon engeli; protokol sapma yönetimi; TMF"],
  ["21 CFR Part 11 / EU GMP Annex 11", "Değiştirilemez, hash zincirli denetim izi; parola ile yeniden doğrulanan e-imza; imza anlamı ve içerik özeti; değişiklik gerekçesi zorunluluğu; hesap kilitleme ve oturum süresi; uyum değerlendirme belgesi"],
  ["TİTCK Klinik Araştırmalar Hakkında Yönetmelik", "Başvuru tiplerinin takibi; SAE için 7/15 gün bildirim sayacı; SUSAR tespiti; yıllık bildirim ve sonlandırma kayıtları"],
  ["CDISC (CDASH, ODM, SDTM)", "CDASH eşlemeli eCRF alanları; ODM 1.3.2 dışa aktarım; SDTM eşlemesi veri yöneticisi işlemi"],
  ["HL7 FHIR R4 / OMOP CDM v5.4", "HBYS adaptörü; ResearchStudy / ResearchSubject kaynakları; OMOP CSV dışa aktarımı"],
  ["IEC 62304 / ISO 27001 yaklaşımı", "Yazılım yaşam döngüsü kayıtları, sürümleme, değişiklik günlüğü, risk analizi (FMEA); TLS, güvenlik başlıkları, en az yetki ilkesi, yedekleme ve saklama politikası; sızma testi proje iş paketi İP4"],
  ["Bilgisayarlı sistem validasyonu (GAMP 5)", "Validasyon planı, URS (78 gereksinim), FRS, risk analizi, IQ/OQ (38 senaryo)/PQ, izlenebilirlik matrisi ürünle birlikte teslim edilir"],
], [2.4, 5.4]));
ekle(P("Yapay zekâ bileşenleri için ayrıca şu ilke uygulanır: model çıktıları tıbbi karar değil, karar desteğidir; nihai uygunluk kararı araştırmacıya, merkez seçimi proje yöneticisine, uyarı kapanışı CRA'ya aittir. Risk analizinde yanlış pozitif ve yanlış negatif eşleştirme, halüsinasyon, eksik kimliksizleştirme ve model sunucusu erişilemezliği ayrı başarısızlık modları olarak ele alınmış; her biri için insan-döngüde kontrol, koruma katmanı veya geri düşme mekanizması tanımlanmıştır."));

// 8 Olgunluk ve Ar-Ge
ekle(H1("8. Olgunluk durumu ve Ar-Ge göstergeleri"));
ekle(H2("8.1 Modül olgunluk tablosu"));
ekle(P("Aşağıdaki tablo her modülün mevcut olgunluğunu üç düzeyde özetler: **Üretim** (iç operasyonda kullanılan, validasyon dosyası bulunan), **Pilot** (işlevsel olarak tamam, gerçek ortam doğrulaması bekleyen) ve **Ar-Ge** (prototip düzeyinde, aktif geliştirme)."));
ekle(...tablo(["Modül", "Durum", "Açıklama"], [
  ["Çalışma, merkez, başvuru yönetimi", "Üretim", "Sürüm 1.0'dan itibaren iç kullanımda"],
  ["Gönüllü, vizit, eCRF, sorgu, SDV, kilit", "Üretim", "CDASH eşlemesi 1.1; ODM dışa aktarım 1.4.2"],
  ["Güvenlik raporlama (AE/SAE/SUSAR)", "Üretim", "MedDRA kodlama elle; otomatik kodlama önerisi 1.5"],
  ["TMF, denetim izi, e-imza, RBAC", "Üretim", "21 CFR 11 / Annex 11 uyum değerlendirmesi mevcut"],
  ["Kimliksizleştirme", "Pilot", "Kural tabanlı; sentetik sette F1 0,95; gerçek rapor seti üzerinde değerlendirme İP1"],
  ["FHIR R4 HBYS adaptörü, OMOP", "Pilot", "Mock ve standart FHIR sunucusuyla test edildi; HBYS üreticileriyle saha testi İP4"],
  ["Risk bazlı izlem (KRI/QTL/anomali)", "Pilot", "Eşikler EBM geçmiş verisine göre; prospektif yanlış alarm oranı ölçülecek"],
  ["Merkez zekâsı (kazanım, gecikme, sıralama)", "Pilot / Ar-Ge", "Modeller çalışıyor; örnek içi MAPE ve AUC hedefe yakın, çalışma türü kovaryatı ekleniyor"],
  ["Kriter yapılandırma ve eşleştirme motoru", "Pilot / Ar-Ge", "Yapısal ve kalıp tabanlı yol üretimde; BDM yolu laboratuvarda"],
  ["Türkçe Klinik BDM", "Ar-Ge", "Kavram kanıtı; sürekli ön eğitim ve talimat ince ayarı İP2; nicemlenmiş hastane içi sürüm hedef"],
], [2.6, 1.2, 4]));
ekle(H2("8.2 Proje başarı ölçütleri ve mevcut ölçümler"));
ekle(P("Platform, yapay zekâ bileşenlerinin performansını sürekli ölçer ve Ar-Ge göstergeleri sayfasında proje başarı ölçütleriyle karşılaştırır. Aşağıdaki değerler, bu dokümanın hazırlandığı tarihte demo kurulumunda sistemin kendi hesapladığı değerlerdir. BDM sunucusu bağlı olmadığı için eşleştirme ölçümleri **kural tabanlı taban çizgisini** gösterir; projede geliştirilecek Türkçe Klinik BDM'nin bu taban çizgisini aşması beklenir."));
ekle(...tablo(["Ölçüt", "Hedef (proje)", "Mevcut", "Ölçüm kaynağı ve not"], [
  ["Hasta–kriter eşleştirmede duyarlılık", "≥ %90", "%76,9", "Altın standart set (28 sentetik örnek), kural tabanlı; özgüllük %93,3; belirsiz oranı %32"],
  ["Halüsinasyon oranı (kanıt kaynakta yok)", "≤ %2", "%0", "Koruma katmanı kaynakta bulunmayan kanıtı reddeder"],
  ["Kriter yapılandırmada tam eşleşme", "≥ %85", "%35,7", "Alan bazlı eşleşme %60; BDM yapılandırması İP2'nin ana hedefi"],
  ["Kimliksizleştirme duyarlılığı", "≥ %98", "%90,9", "Sentetik set, 22 varlık; kesinlik %100, F1 %95"],
  ["Kazanım tahmininde MAPE", "≤ %25", "%33,5", "3 aktif çalışma, çalışma düzeyinde, örnek içi; kayıt çalışmasında sapma yüksek"],
  ["Aktivasyon gecikme riskinde AUC", "≥ 0,80", "0,79", "37 merkez, örnek içi; prospektif doğrulama İP5"],
  ["Ön tarama süresinde azalma", "≥ %50", "%84 (tahmini)", "Motor ~50 ms/hasta + 4 dk inceleme; manuel 25 dk varsayımı pilotta ölçülecek"],
], [2.4, 1.1, 1.1, 3.2]));
ekle(...sekil("25_arge_gostergeleri.png", "Ar-Ge göstergeleri sayfası (demo kurulumu, kural tabanlı mod)"));
ekle(P("Bu ölçümler, ürünün mevcut durumuna ilişkin dürüst bir resim sunmayı amaçlar. Kural tabanlı yol halüsinasyon üretmez ancak serbest metin kriterlerinde sık \"belirsiz\" der; bu, projenin gerekçesini oluşturan boşluktur. Altın standart setin pilot hastanelerde klinisyen etiketlemesiyle 2.000 çifte genişletilmesi ve BDM'nin bu set üzerinde değerlendirilmesi İP1–İP2'nin çıktısıdır."));
ekle(H2("8.3 Teknoloji hazırlık seviyesi ve proje iş paketleriyle ilişki"));
ekle(P("Platform çekirdeği operasyonel ortamda kullanılmakta (THS 7–8), yapay zekâ katmanı ise laboratuvar ortamında sentetik ve geçmiş operasyon verisiyle doğrulanmış durumdadır (THS 4). Proje, yapay zekâ katmanını gerçek klinik araştırma ortamında doğrulayarak bütünleşik ürünü THS 7'ye taşımayı hedefler."));
ekle(...tablo(["İş paketi", "Platformdaki mevcut temel", "Proje ile eklenecek"], [
  ["İP1 Veri altyapısı ve referans veri seti", "Ortak veri modeli, FHIR/OMOP eşlemeleri, kimliksizleştirme aracı, etiketleme şeması ve kılavuzu", "Pilot hastane veri envanteri, etik/KVKK onayları, 2.000 çiftlik altın standart set, gerçek rapor seti üzerinde kimliksizleştirme değerlendirmesi"],
  ["İP2 Türkçe Klinik BDM ve eşleştirme motoru", "Eşleştirme boru hattı, koruma katmanı, RAG, kural tabanlı taban çizgisi, eğitim ve değerlendirme betikleri", "Sürekli ön eğitim, talimat ince ayarı, nicemlenmiş hastane içi model, duyarlılık ≥ %90"],
  ["İP3 Merkez zekâsı ve RBM modelleri", "Gamma–Poisson, Weibull AFT, sıralama, 15 KRI, anomali motoru", "Çalışma türü ve etik kurul süresi kovaryatları, transfer öğrenme, prospektif MAPE/AUC doğrulaması, yanlış alarm oranı"],
  ["İP4 Platform entegrasyonu, güvenlik, validasyon", "Mikroservis hazır sağlayıcı soyutlaması, FHIR adaptörü, CSV dosyası, Part 11 uyumu", "HBYS üreticileriyle saha entegrasyonu, sızma testi, IEC 62304 / ISO 27001 uyum tamamlanması"],
  ["İP5 Pilot doğrulama ve ürünleştirme", "Gölge mod, Ar-Ge göstergeleri, fizibilite raporu, kurulum paketi", "Üç hastanede prospektif gölge mod doğrulaması, kullanıcı kabul testleri, regülasyon sınıflandırması, lisans/SaaS modeli, yazılım tescili ve patent başvurusu"],
], [1.8, 3, 3]));

// 9 Dogrulama
ekle(H1("9. Doğrulama planı"));
ekle(P("Doğrulama iki düzeyde yürütülür. **Teknik doğrulama** altın standart set üzerinde otomatik değerlendirme ile yapılır: her model sürümü için duyarlılık, özgüllük, F1, halüsinasyon oranı, kanıt aralığı örtüşmesi, yapılandırma doğruluğu ve güven kalibrasyonu raporlanır; sonuçlar `ml/ciktilar` altında sürümlenir ve Ar-Ge göstergeleri sayfasında görünür. **Klinik ortam doğrulaması** gölge mod ile yapılır: en az biri onkoloji merkezi olmak üzere üç pilot hastanede, EBM'nin yürüttüğü aktif çalışmalarda motor önerileri araştırmacıya gösterilmeden kaydedilir ve manuel ön tarama sonuçlarıyla karşılaştırılır. Ön tarama süresi, klinisyen başına hasta dosyası inceleme süresi olarak eşzamanlı ölçülür."));
ekle(...tablo(["Doğrulama konusu", "Yöntem", "Kabul ölçütü"], [
  ["Eşleştirme doğruluğu", "Gölge mod; araştırmacı kararı referans; çalışma ve merkez bazında", "Duyarlılık ≥ %90; PPV raporlanır; kaynak cümle doğruluğu klinisyen tarafından örneklemle denetlenir"],
  ["Ön tarama süresi", "Zaman-hareket ölçümü, manuel ve platform destekli kollar", "≥ %50 azalma"],
  ["Kazanım ve gecikme tahmini", "Prospektif: tahminler kilitlenir, 6 ay sonra gerçekleşenle karşılaştırılır", "MAPE ≤ %25; AUC ≥ 0,80"],
  ["Risk bazlı izlem", "Uyarıların CRA tarafından sınıflanması (gerçek / yanlış alarm); ziyaret bulgularıyla eşleme", "Yanlış alarm oranı raporlanır; majör bulguların uyarı ile öncelenme oranı"],
  ["Kimliksizleştirme", "Gerçek rapor örneklemi üzerinde çift etiketleme", "Duyarlılık ≥ %98 (kimlik verisi), klinik terim kaybı ≤ %1"],
  ["Kullanılabilirlik ve kabul", "Kullanıcı kabul testleri (OQ/PQ senaryoları), SUS anketi", "Kritik senaryolarda %100 geçiş; SUS ≥ 70"],
], [1.8, 3.2, 2.8]));

// 10 Etki ve ticarilesme
ekle(H1("10. Etki, iş modeli ve ticarileşme"));
ekle(H2("10.1 Hedef kullanıcılar ve değer önerisi"));
ekle(...tablo(["Segment", "Temel sorun", "SmartClinical'ın değeri", "Ödeme gerekçesi"], [
  ["Sponsorlar (yerli ilaç, biyobenzer, cihaz, IVD üreticileri)", "Kayıt gecikmesi, merkez seçim hatası, görünürlük eksikliği", "Hızlı kazanım, kanıta dayalı merkez seçimi, gerçek zamanlı risk görünümü, fizibilite raporu", "Çalışma süresindeki her ayın sabit maliyeti ve pazara giriş gecikmesi"],
  ["CRO ve SMO'lar", "Manuel ön tarama ve izlem iş yükü, çok sistemli operasyon", "Tek platform, yapay zekâ destekli ön tarama, risk bazlı izlem ile ziyaret maliyeti düşüşü", "Personel verimliliği, proje başına marj"],
  ["Araştırma hastaneleri ve üniversiteler", "Uygun hastanın bulunamaması, KVKK nedeniyle dış sistem kullanılamaması, akademik çalışmalarda yazılım maliyeti", "Hastane içi çalışan Türkçe eşleştirme, araştırmacı başlatımlı çalışmalar için uygun lisans sınıfı", "Çalışma gelirleri, araştırma kapasitesi, akreditasyon"],
  ["Araştırmacılar ve koordinatörler", "Dosya tarama ve idari yük", "Kaynak cümleli öneri listesi, otomatik vizit ve sorgu takibi", "Kurum lisansı üzerinden; doğrudan ödeme beklenmez"],
], [1.9, 2, 2.4, 1.5]));
ekle(H2("10.2 Etki örneği"));
ekle(P("120 gönüllü hedefli, altı merkezli bir faz III çalışmasında toplam kazanım hızının ayda 5 hastadan ön tarama ile %20 artarak 6 hastaya çıkması, hedefe ulaşma süresini 24 aydan 20 aya indirir. Çalışmanın aylık sabit maliyetinin 400.000 TL olduğu varsayımıyla bu dört aylık kısalma yaklaşık 1,6 milyon TL sabit maliyet tasarrufu anlamına gelir; pazara dört ay erken giriş geliri bu hesaba dahil değildir. Platformdaki etki hesaplayıcı, bu hesabı sponsorun kendi varsayımlarıyla yapmasına imkân verir. Benzer şekilde risk bazlı izlem, yerinde ziyaret sıklığını düşük riskli merkezlerde azaltarak CRA seyahat ve zaman maliyetini düşürür; bu etki pilotta ölçülecektir."));
ekle(H2("10.3 Gelir modeli"));
ekle(...tablo(["Lisans sınıfı", "Hedef", "Kapsam", "Model"], [
  ["Kurumsal (on-premise)", "Araştırma hastaneleri, üniversiteler", "Tüm modüller, BDM hastane GPU'sunda, sınırsız çalışma, HBYS entegrasyonu", "Yıllık lisans + kurulum ve entegrasyon hizmeti + bakım"],
  ["Çalışma bazlı", "Sponsorlar, CRO'lar", "Belirli çalışma için merkez zekâsı, RBM, eCRF, TMF; merkezlerdeki kurulumlarla bağlantı", "Çalışma başına ücret (süre ve merkez sayısına göre)"],
  ["SaaS (operasyon katmanı)", "Küçük CRO'lar, SMO'lar", "Hasta verisi içermeyen operasyon modülleri (çalışma, merkez, başvuru, RBM, TMF) bulutta; eşleştirme hastane kurulumunda", "Aylık abonelik, kullanıcı sayısına göre"],
  ["Akademik", "Araştırmacı başlatımlı çalışmalar", "Tek merkez, temel modüller", "Sembolik yıllık ücret; eğitim ve destek dahil"],
  ["Bileşen lisansı", "HBYS üreticileri, veri ambarı projeleri", "Kimliksizleştirme aracı, klinik NLP servis API'si", "OEM / API çağrısı başına"],
], [1.6, 1.6, 2.8, 1.8]));
ekle(H2("10.4 Pazara giriş"));
ekle(P("Ürün ilk günden EBM'nin kendi CRO/SMO operasyonlarında kullanıldığı için pazara giriş, mevcut sponsor ve merkez ağı üzerinden başlar: EBM'nin yürüttüğü çalışmalarda sponsorlara çalışma bazlı erişim sunulur ve pilot hastanelerde kurumsal kurulum yapılır. İkinci aşamada yurt içi CRO'lar, yerli ilaç ve tıbbi cihaz üreticileri ile araştırma hastaneleri hedeflenir; TÜSEB destekli ürünlerin klinik doğrulamasında kullanım, referans oluşturur. Üçüncü aşamada Türkçe konuşan ülkeler ve MENA bölgesi için dil uyarlaması planlanır; mimari, dil bağımlı bileşenleri (sözlükler, kimliksizleştirme kuralları, BDM) değiştirilebilir tutar."));
ekle(H2("10.5 Mevcut çözümlerle karşılaştırma"));
ekle(...tablo(["Özellik", "Yurt dışı CTMS / eşleştirme çözümleri", "Yerel EDC ve dokümantasyon araçları", "EBM SmartClinical"], [
  ["Türkçe klinik serbest metin işleme", "Yok veya sınırlı", "Yok", "Var (Türkçe Klinik BDM, kural tabanlı geri düşme)"],
  ["Hasta verisinin kurum içinde kalması", "Bulut; veri aktarımı gerekir", "Çoğunlukla kurum içi", "Hastane içi kurulum; BDM dahil"],
  ["Uçtan uca yaşam döngüsü (tasarım–arşiv)", "Parçalı ürün ailesi", "Yalnızca veri toplama", "Tek platform"],
  ["Merkez zekâsı ve kazanım projeksiyonu", "Üst segment ürünlerde", "Yok", "Var, açıklanabilir"],
  ["Risk bazlı izlem (ICH E6 R3)", "Var", "Yok", "Var, anomali tespitiyle"],
  ["Part 11 / Annex 11 uyumu ve CSV dosyası", "Var", "Değişken", "Var, ürünle teslim"],
  ["Akademik çalışmalar için erişilebilir lisans", "Hayır", "Kısmen", "Evet"],
  ["Yerli geliştirme ve destek", "Hayır", "Evet", "Evet"],
], [2.2, 2.1, 1.9, 2.2]));
ekle(H2("10.6 Fikri mülkiyet ve sürdürülebilirlik"));
ekle(P("Yazılım tescili ve kimliksizleştirme ile kanıta dayalı eşleştirme yöntemi için patent başvurusu proje iş paketi İP5 kapsamındadır. Ürün, EBM'nin kendi operasyonlarında kullanıldığı için proje sonrasında da bakım ve geliştirme sürekliliği iç ihtiyaçla güvence altındadır; yurt içi müşteri lisansları Ar-Ge'nin sürdürülmesini finanse edecek şekilde planlanmıştır."));

// 11 Yol haritasi ve riskler
ekle(H1("11. Yol haritası ve riskler"));
ekle(H2("11.1 Yol haritası"));
ekle(...tablo(["Sürüm", "Planlanan", "Başlıca içerik"], [
  ["1.5", "2027 Ç1", "Çalışma bazlı kullanıcı atama; protokol bazlı vizit tasarımcısı; MedDRA ve ATC otomatik kodlama önerisi; merkez zekâsında çalışma türü ve etik kurul süresi kovaryatları; Alembic migrasyonları; API anahtarı ile makine-makine erişim"],
  ["1.6", "2027 Ç2", "HBYS üreticileriyle sertifikalı FHIR entegrasyonu; çok merkezli kurulumlar için merkezi sponsor toplayıcı; SDTM dışa aktarım; e-onam entegrasyonu"],
  ["2.0", "2027 Ç4 (proje sonu)", "Nicemlenmiş Türkçe Klinik BDM'nin hastane içi dağıtımı; gölge mod pilotuyla doğrulanmış eşleştirme; validasyon dosyasının tamamlanması; THS 7 ürün"],
  ["2.x", "2028", "Çok dilli uyarlama (MENA); federe model güncelleme; gerçek yaşam verisi çalışmaları için OMOP tabanlı analiz katmanı"],
], [0.9, 1.5, 5.6]));
ekle(H2("11.2 Riskler ve azaltım"));
ekle(...tablo(["Risk", "Etki", "Azaltım"], [
  ["Türkçe tıbbi derlemin yeterli hacimde toplanamaması", "BDM performansı hedefin altında kalır", "Çok merkezli veri paylaşım protokolleri; sentetik ve yarı sentetik örnek üretimi; kural tabanlı ve kalıp tabanlı yolun ürün içinde kalması"],
  ["Hastanelerde GPU altyapısının bulunmaması", "BDM kullanılamaz", "Nicemlenmiş CPU sürümü; kural tabanlı mod; isteğe bağlı EBM barındırmalı BDM (yalnızca kimliksizleştirilmiş veri ile)"],
  ["HBYS entegrasyonunda üretici bağımlılığı", "Hasta havuzu alınamaz", "FHIR R4 standardı; CSV/toplu yükleme yolu; üreticilerle İP4'te saha testi"],
  ["Yanlış pozitif / negatif eşleştirme", "Uygun olmayan hasta aday listesine girer veya uygun hasta kaçar", "Araştırmacı onayı zorunlu; kaynak cümle gösterimi; gölge mod ile sürekli ölçüm; belirsizde güvenli taraf"],
  ["Regülasyon sınıflandırması (tıbbi yazılım)", "Pazara sunum gecikmesi", "Karar destek sınırlarının açık tanımı; İP5'te sınıflandırma analizi; IEC 62304 uyumlu yaşam döngüsü"],
  ["Kullanıcı kabulü (araştırmacı iş yükü algısı)", "Düşük kullanım", "Rol bazlı sade arayüz; mevcut iş akışına eklenen değil, yerine geçen tasarım; pilotta SUS ölçümü"],
], [2.2, 1.8, 3.8]));

// 12 Teknik ozellikler
ekle(H1("12. Teknik özellikler özeti"));
ekle(...tablo(["Başlık", "Özellik"], [
  ["Sunucu gereksinimi (uygulama)", "4 çekirdek, 8 GB bellek, 100 GB disk (TMF hariç); Linux; Docker veya systemd"],
  ["Sunucu gereksinimi (BDM)", "Nicemlenmiş 7–8B model için 16 GB VRAM'li GPU önerilir; CPU modunda 32 GB bellek"],
  ["Veritabanı", "PostgreSQL 16; geliştirme ve küçük kurulumlarda SQLite"],
  ["İstemci", "Güncel tarayıcı; ek yazılım gerekmez; kapalı ağda çalışır"],
  ["Kimlik doğrulama", "Yerel hesaplar, PBKDF2-SHA256, hesap kilitleme; LDAP/AD ve SSO 1.5 sürümünde"],
  ["Entegrasyon", "REST API v1 (OpenAPI), FHIR R4 (okuma ve ResearchStudy/ResearchSubject), CDISC ODM 1.3.2, CSV, OMOP CDM v5.4"],
  ["Yedekleme", "Günlük veritabanı ve dosya yedeği; 7 günlük, 30 günlük ve uzun dönem saklama politikası; SHA-256 bütünlük"],
  ["Loglama ve izleme", "Uygulama logları hasta verisi içermez; sağlık uç noktası; denetim izi zinciri doğrulama betiği"],
  ["Test ve kalite", "144 otomatik test (servis, model, web, denetim); statik analiz; değişiklik günlüğü; sürümleme"],
  ["Diller", "Arayüz Türkçe; kriter ayrıştırıcı Türkçe ve İngilizce protokol metinlerini destekler"],
], [2.2, 5.6]));
ekle(...bosluk(1));
ekle(P("Bu doküman ürünün mevcut sürümünü tanımlar; işlevler ve ölçümler sürüm notlarıyla güncellenir. Teknik sorular için yazılım ekibi, ticari sorular için EBM iş geliştirme birimi ile iletişime geçilebilir.", { italics: true, color: GRI, size: 20 }));

// ---------------------------------------------------------------- belge
const doc = new Document({
  creator: "EBM Klinik Araştırma Hizmetleri",
  title: "EBM SmartClinical – Ürün Tanıtım ve Teknik Özet Dokümanı",
  description: "Sürüm 1.4.2",
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
    headers: { default: new Header({ children: [new Paragraph({ children: [run("EBM SmartClinical · Ürün Tanıtım ve Teknik Özet Dokümanı · v1.1", { size: 16, color: GRI })], alignment: AlignmentType.RIGHT, border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: KENAR, space: 4 } } })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ children: [run("Gizli – EBM Klinik Araştırma Hizmetleri   |   Sayfa ", { size: 16, color: GRI }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: GRI })], alignment: AlignmentType.CENTER })] }) },
    children: icerik,
  }],
});

Packer.toBuffer(doc).then(buf => { fs.writeFileSync(CIKTI, buf); console.log("yazildi", CIKTI, buf.length); });
