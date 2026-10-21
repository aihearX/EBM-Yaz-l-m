"""Kimliksizlestirme icin sozlukler.

Ad/soyad listeleri NVI sik kullanilan isim istatistiklerinden derlendi; tam kapsama iddiasi yok,
unvan ve buyuk harf heuristigiyle birlikte kullaniliyor.
"""

ILLER = [
    "Adana", "Adıyaman", "Afyonkarahisar", "Afyon", "Ağrı", "Amasya", "Ankara", "Antalya", "Artvin", "Aydın",
    "Balıkesir", "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum",
    "Denizli", "Diyarbakır", "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir", "Gaziantep", "Giresun",
    "Gümüşhane", "Hakkari", "Hakkâri", "Hatay", "Isparta", "Mersin", "İstanbul", "İzmir", "Kars", "Kastamonu",
    "Kayseri", "Kırklareli", "Kırşehir", "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa", "Kahramanmaraş",
    "Mardin", "Muğla", "Muş", "Nevşehir", "Niğde", "Ordu", "Rize", "Sakarya", "Samsun", "Siirt", "Sinop",
    "Sivas", "Tekirdağ", "Tokat", "Trabzon", "Tunceli", "Şanlıurfa", "Uşak", "Van", "Yozgat", "Zonguldak",
    "Aksaray", "Bayburt", "Karaman", "Kırıkkale", "Batman", "Şırnak", "Bartın", "Ardahan", "Iğdır", "Yalova",
    "Karabük", "Kilis", "Osmaniye", "Düzce",
]

# Il adlariyla cakisan klinik/genel kelimeler yok sayilir (Ordu, Van, Muş, Kars vb. serbest metinde nadir)
# ama "Van" ingilizce metinde gecebilir; simdilik kabul.

ADLAR = """
Ahmet Mehmet Mustafa Ali Hüseyin Hasan İbrahim İsmail Osman Yusuf Ömer Murat Ramazan Halil Süleyman Abdullah
Mahmut Recep Salih Kemal Kadir Fatih Serkan Emre Burak Erdem Tolga Volkan Onur Barış Cem Can Deniz Kaan Selim
Kerem Mert Yunus Enes Furkan Eren Berk Arda Umut Oğuz Orhan Metin Cengiz Erol Turgut Erkan Levent Bülent Tuncay
Sinan Selçuk Ercan Ersin Uğur Ufuk Zafer Gökhan Hakan Okan Özgür Tamer Taner Tarık Yavuz Yaşar Yılmaz Nihat Nuri
Necati Necmettin Nevzat Nurettin Sabri Sadık Şaban Şükrü Veli Vedat Zeki Ziya Adem Adnan Alpaslan Alper Aydın Aykut
Bahri Baki Bayram Bekir Bilal Birol Cahit Celal Cemal Cemil Cevdet Cüneyt Davut Doğan Dursun Ender Engin Erhan
Ertuğrul Eyüp Fahri Faruk Ferhat Fevzi Fikret Fuat Galip Gürkan Habib Hamdi Hamza Hayati Haydar Hikmet Hilmi Hüsnü
İhsan İlhan İlker İrfan Kazım Kenan Kudret Lütfü Mesut Muammer Muhammed Muharrem Muzaffer Naci Nazım Nejat Nizamettin
Orçun Özkan Rahmi Ramiz Raşit Rıdvan Rıza Rüştü Sadettin Saffet Samet Sedat Semih Serdar Serhat Sezgin Suat Şahin
Şenol Şeref Talat Tayfun Tevfik Tufan Turan Ümit Vahit Yakup Yalçın Yener Zeynel Abdurrahman Alaattin Ayhan Bora
Fatma Ayşe Emine Hatice Zeynep Elif Meryem Şerife Zehra Sultan Hanife Merve Havva Zeliha Esra Fadime Özlem Yasemin
Büşra Kübra Hülya Sevim Gülsüm Derya Dilek Nurcan Nuray Nurten Şükran Sevgi Sevil Serpil Sibel Songül Tuba Tuğba
Türkan Ümmü Yeliz Yeşim Zekiye Zübeyde Aynur Aysel Ayten Aysun Bahar Belgin Berna Betül Beyza Burcu Canan Ceren
Çiğdem Damla Duygu Ebru Ece Eda Elvan Emel Esma Figen Filiz Funda Gamze Gaye Gizem Gonca Gökçe Gül Gülay Gülbahar
Gülçin Gülden Gülhan Güler Gülnur Gülşen Günay Hacer Hale Halime Handan Hande Hilal Huriye İlknur İpek Kadriye
Kamile Kevser Leyla Makbule Melek Melike Melis Meltem Mine Müge Nalan Naime Nazan Nazlı Nebahat Necla Nejla Nermin
Neslihan Nevin Nilgün Nilüfer Nur Nurgül Nurhan Nursel Oya Pelin Perihan Pınar Rabia Rukiye Saadet Sabiha Safiye
Saniye Seda Seher Selda Selma Sema Semra Sena Serap Sevda Sevinç Sezen Şebnem Şenay Şule Tülay Ülkü Vildan Yıldız
Zeynep Ayla Aylin Ayça Aslı Begüm Buse Cansu Dila Ezgi İrem Nisa Selin Simge Sinem Tuğçe Yağmur Nazife Kezban Ayşegül
Mücahit Mücahide Reyhan Rüya Sevtap
""".split()

SOYADLAR = """
Yılmaz Kaya Demir Şahin Çelik Yıldız Yıldırım Öztürk Aydın Özdemir Arslan Doğan Kılıç Aslan Çetin Kara Koç Kurt
Özkan Şimşek Polat Korkmaz Çakır Erdoğan Özcan Taş Aksoy Avcı Güneş Acar Bulut Keskin Turan Yavuz Tekin Kaplan
Işık Ateş Ünal Bozkurt Güler Kurtuluş Karaca Sönmez Can Şen Ergün Sarı Yücel Aktaş Ercan Öz Kalkan Duman Toprak
Gül Demirci Kocaman Tunç Ünsal Uysal Eren Çiftçi Aygün Yalçın Gündüz Erdem Kahraman Altun Karataş Bayram Durmuş
Özer Ayhan Çoban Yiğit Demirel Alkan Ekinci Karaman Sezer Sağlam Çolak Başaran Uçar Akgün Dinç Erkan Soylu Yurt
Taşkın Bilgin Özbek Güngör Mutlu Göksu Akın Kara Yaman Aktürk Tanrıverdi Bal Çevik Demirtaş Akbulut Kutlu Türk
Köse Özdemir Tosun Kurtoğlu Büyükkaya Bozdağ Oktay Ergin Varol Gürses Pekmez Yurdakul Karakaş Durak Balcı Akyol
Şeker Aral Güzel Kıran Ulusoy Karahan Vural Ersoy Bekar Örnek Eroğlu Ozan Çiçek Alp Toker Yener Ün Aksu Baran
Kocabaş Önal Tuncer Çalışkan Küçük Ayaz Batmaz Korkut Özgür Savaş Sevinç Şentürk Erbaş Ulu Gürbüz Özen Daş
""".split()

UNVANLAR = [
    "Prof. Dr.", "Doç. Dr.", "Dr. Öğr. Üyesi", "Op. Dr.", "Uzm. Dr.", "Dr.", "Prof.", "Doç.", "Uzm.", "Hemş.",
    "Sn.", "Sayın", "Asist. Dr.", "Arş. Gör.", "Ecz.", "Dyt.", "Fzt.", "Psk.",
]

AYLAR = [
    "ocak", "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz", "ağustos", "eylül", "ekim", "kasım", "aralık",
]

# Buyuk harfle basladigi icin isim sanilabilecek klinik/genel terimler. Kucuk harfe cevrilerek bakilir.
KLINIK_BEYAZ_LISTE = {
    "ca", "metastaz", "tümör", "tumor", "karsinom", "adenokarsinom", "lenfoma", "lösemi", "sarkom", "melanom",
    "hipertansiyon", "diyabet", "diabetes", "mellitus", "koah", "astım", "kalp", "yetmezliği", "yetmezlik",
    "anemi", "sepsis", "pnömoni", "pnomoni", "enfeksiyon", "fraktür", "kırık", "ödem", "bulantı", "kusma",
    "hasta", "hastanın", "hastaya", "hastada", "tanı", "tanısı", "tedavi", "tedavisi", "operasyon", "ameliyat",
    "epikriz", "patoloji", "radyoloji", "laboratuvar", "biyopsi", "sitoloji", "histoloji", "evre", "grade",
    "derece", "sol", "sağ", "bilateral", "üst", "alt", "lob", "meme", "akciğer", "karaciğer", "böbrek", "mide",
    "kolon", "rektum", "prostat", "mesane", "over", "uterus", "serviks", "tiroid", "pankreas", "beyin",
    "kemik", "lenf", "nodu", "nodülü", "nodül", "kitle", "lezyon", "nekroz", "fibrozis", "inflamasyon",
    "bt", "mr", "mrg", "pet", "usg", "ekg", "eko", "ekokardiyografi", "ct", "mri", "rt", "kt", "kemoterapi",
    "radyoterapi", "immünoterapi", "hormonoterapi", "cerrahi", "mastektomi", "lobektomi", "gastrektomi",
    "kolektomi", "nefrektomi", "prostatektomi", "histerektomi", "tiroidektomi", "sistektomi", "rezeksiyon",
    "her2", "er", "pr", "ki67", "egfr", "alk", "kras", "braf", "pdl1", "msi", "brca", "tnm", "ecog", "nyha",
    "karnofsky", "ctcae", "recist", "glukoz", "kreatinin", "üre", "hemoglobin", "hemogram", "lökosit",
    "trombosit", "nötrofil", "lenfosit", "ast", "alt", "ggt", "ldh", "crp", "sedimantasyon", "hba1c", "ldl",
    "hdl", "trigliserid", "kolesterol", "inr", "aptt", "pt", "troponin", "bnp", "tsh", "ft4", "ft3",
    "sodyum", "potasyum", "kalsiyum", "magnezyum", "fosfor", "albümin", "bilirubin", "amilaz", "lipaz",
    "metformin", "insülin", "glargin", "aspirin", "klopidogrel", "atorvastatin", "rosuvastatin", "ramipril",
    "enalapril", "losartan", "valsartan", "amlodipin", "metoprolol", "bisoprolol", "karvedilol", "furosemid",
    "spironolakton", "varfarin", "apiksaban", "rivaroksaban", "enoksaparin", "heparin", "pantoprazol",
    "omeprazol", "lansoprazol", "levotiroksin", "prednizolon", "metilprednizolon", "deksametazon",
    "parasetamol", "ibuprofen", "diklofenak", "tramadol", "morfin", "fentanil", "ondansetron",
    "metoklopramid", "siklofosfamid", "doksorubisin", "paklitaksel", "dosetaksel", "karboplatin",
    "sisplatin", "oksaliplatin", "kapesitabin", "fluorourasil", "gemsitabin", "trastuzumab", "pertuzumab",
    "bevacizumab", "rituksimab", "pembrolizumab", "nivolumab", "atezolizumab", "tamoksifen", "letrozol",
    "anastrozol", "goserelin", "amoksisilin", "seftriakson", "siprofloksasin", "levofloksasin", "meropenem",
    "vankomisin", "salbutamol", "tiotropium", "budesonid", "formoterol", "mg", "ml", "gr", "cc", "mcg",
    "iu", "tablet", "tb", "amp", "ampul", "flakon", "kapsül", "günde", "gün", "hafta", "ay", "yıl",
    "tarih", "no", "sayı", "sonuç", "normal", "patolojik", "pozitif", "negatif", "yok", "var", "mevcut",
    "öyküsü", "öykü", "anamnez", "şikayet", "şikayeti", "fizik", "muayene", "muayenesi", "bulgu", "bulgular",
    "plan", "öneri", "öneriler", "kontrol", "kontrole", "poliklinik", "servis", "yoğun", "bakım", "acil",
    "yatış", "taburcu", "taburculuk", "konsültasyon", "ileri", "tetkik", "tetkikler", "takip", "takibi",
    "klinik", "çalışma", "protokol", "randomize", "plasebo", "doz", "dozu", "siklus", "kür", "evreleme",
    "yaş", "yaşında", "erkek", "kadın", "bayan", "bay", "cinsiyet", "kilo", "boy", "vki", "bmi",
    "nabız", "tansiyon", "ateş", "solunum", "spo2", "saturasyon", "sistolik", "diyastolik", "mmhg",
    "ekim", "kasım", "aralık", "ocak", "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz", "ağustos", "eylül",
    "türkiye", "sağlık", "bakanlığı", "hastanesi", "hastane", "üniversitesi", "üniversite", "tıp", "fakültesi",
    "eğitim", "araştırma", "merkezi", "bölümü", "anabilim", "dalı", "kliniği", "polikliniği", "servisi",
    "onkoloji", "kardiyoloji", "nöroloji", "nefroloji", "endokrinoloji", "gastroenteroloji", "hematoloji",
    "romatoloji", "göğüs", "hastalıkları", "dahiliye", "cerrahisi", "genel", "ortopedi", "üroloji",
    "jinekoloji", "kadın", "doğum", "pediatri", "çocuk", "psikiyatri", "dermatoloji", "göz", "kbb",
    "anestezi", "reanimasyon", "fizik", "tedavi", "rehabilitasyon", "nükleer", "enfeksiyon", "immünoloji",
    "alerji", "tıbbi", "medikal", "cerrahi", "hemodiyaliz", "diyaliz", "transplantasyon", "nakil",
}

# Sahte isim uretiminde kullanilacak havuz (gercek sozlukten ayri tutuyoruz ki takma ad gercek kisiyle carpismasin)
TAKMA_ADLAR = ["Hasta A", "Hasta B", "Hasta C", "Hasta D", "Hasta E", "Hasta F", "Hasta G", "Hasta H"]
