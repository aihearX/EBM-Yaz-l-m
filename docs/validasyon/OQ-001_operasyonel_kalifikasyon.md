# OQ-001 Operasyonel Kalifikasyon Protokolü

| | |
|---|---|
| Belge No | OQ-001 |
| Sistem | EBM SmartClinical |
| Ortam | Validasyon ortamı (üretim imajının kopyası, sentetik veri) |
| Test uygulayıcıları | Klinik Kalite Uzmanı (T1), Veri Yönetimi Uzmanı (T2), CRA (T3) – geliştirme ekibinden bağımsız |
| Gözden geçiren | Validasyon Sorumlusu |
| Onaylayan | Kalite Güvence Yöneticisi |

## 1. Amaç

FRS-001'de tanımlanan fonksiyonların, URS-001 gereksinimlerini belirlenen sınırlar içinde ve
olumsuz koşullarda karşıladığını belgelemek. GK sınıfı gereksinimlerin tamamı en az bir senaryo
ile kapsanır (TM-001). Her senaryo, aynı davranışı sürekli bütünleştirmede doğrulayan otomatik
teste bağlıdır; otomatik testi olmayan adımlar "Kod" sütununda rota/betikle gösterilir.

## 2. Test ortamı ve veri

Validasyon ortamı üretim imajının kopyasıdır; veritabanı `python -m smartclinical.scripts.demo_veri`
ile sentetik veriyle doldurulur. Hiçbir gerçek hasta verisi kullanılmaz. Test kullanıcıları her rol
için ayrı açılır (`oq_yonetici`, `oq_py`, `oq_cra`, `oq_arastirmaci_m01`, `oq_koordinator_m01`,
`oq_sponsor`, `oq_veri`, `oq_denetci`); sonuç sütunu uygulama sırasında doldurulur (G geçti, K kaldı,
G* sapma sonrası tekrar testte geçti).

## 3. Test senaryoları

| No | Senaryo | Adımlar (özet) | Beklenen sonuç | URS | Kod / otomatik test | Sonuç |
|---|---|---|---|---|---|---|
| OQ-01 | Yaşam döngüsü kontrol listesi | Etik onayı olmayan çalışmada aşama sayfasını aç; gerekçesiz aşama değiştirmeyi dene | Kontrol listesinde "Başvuru kararları onay" eksik görünür; gerekçesiz değişim reddedilir; değişim denetim izinde | ÇY-02 | `tests/test_roller.py::test_kontrol_listesi_veriden_hesaplanir`, `tests/test_roller.py::test_asama_degisimi_gerekce_zorunlu` | |
| OQ-02 | Merkez kapsaması ve ekip kısıtı | `oq_arastirmaci_m01` ile Merkez 02 gönüllü ve ziyaret sayfalarına doğrudan URL ile git; CRA'yı bir çalışmaya ata | 403; atama sonrası CRA yalnızca atandığı çalışmayı görür | YT-02, YT-05 | `tests/test_P1.py::test_arastirmaci_baska_merkezin_hastasina_erisemez`, `tests/test_izlem.py::test_merkez_rolu_yalnizca_kendi_merkezini_gorur`, `tests/test_ekip.py::test_ilk_atama_kisiti_baslatir` | |
| OQ-03 | Sponsor görünürlüğü ve sihirbaz yetkisi | `oq_sponsor` ile başka kurumun çalışmasına ve gönüllü sayfasına git; CRO modunda araştırmacı sihirbazı açsın | 403; sponsor yalnızca kendi kurumunu görür; sihirbaz CRO modunda araştırmacıya kapalı | YT-02, ÇY-07 | `tests/test_roller.py::test_sponsor_kurum_filtresi_ve_sekmeler`, `tests/test_sihirbaz.py::test_arastirmaci_tekil_modda_kurar_cro_modda_403` | |
| OQ-04 | Parola politikası ve kilit | 5 hatalı giriş; 11 karakter parola dene; son 5 paroladan birini yeniden kullan; ilk girişte geçici parola | 15 dk süreli kilit; parola reddedilir; tekrar reddedilir; parola değişimi zorunlu | YT-03 | `tests/test_web.py::test_hatali_giris_ve_sureli_kilit`, `tests/test_web.py::test_parola_degistir_ve_gecmis`, `tests/test_web.py::test_ilk_giriste_parola_degisimi_zorunlu` | |
| OQ-05 | Denetim izi – veri değişikliği ve kilit | AE kaydını güncelle; veri yöneticisi toplu kilit uygulasın; kilidi gerekçesiz, sonra gerekçeli aç | Kayıt: kullanıcı, UTC zaman, eski/yeni değer; gerekçesiz açma reddedilir; `kilit_ac` kaydı gerekçeli | EDC-04, EDC-05, Dİ-01 | `tests/test_gonullu.py::test_ae_duzenleme_denetim_izi`, `tests/test_izlem.py::test_arastirmaci_imzasi_ve_toplu_kilit` | |
| OQ-06 | Denetim izi – eşzamanlılık | 20 eşzamanlı istekle kayıt yaz; zinciri doğrula | İki kayıt aynı önceki özeti taşımaz; zincir geçerli | Dİ-01, Dİ-03 | `tests/test_denetim.py::test_eszamanli_kayit_zinciri_bozmaz` | |
| OQ-07 | Denetim izi bütünlüğü | Doğrudan SQL ile UPDATE/DELETE dene; bir kaydı değiştir; `denetim_dogrula` çalıştır; `SC_SECRET_KEY` değiştirip tekrar çalıştır | İşlemler reddedilir; değişiklik ilk bozuk kayıt olarak raporlanır; anahtar değişince ilk kayıtta durur | Dİ-02, Dİ-03 | `smartclinical/scripts/denetim_dogrula.py`, `tests/test_denetim.py::test_zincir_bozulma_tespiti`, `tests/test_denetim.py::test_anahtar_degisince_dogrulama_basarisiz` | |
| OQ-08 | E-imza: ziyaret raporu ve randomizasyon | CRA ziyaret raporunu yazsın; PY yanlış parola, sonra doğru parola ile onaylasın; onay sonrası düzenleme dene; randomizasyon listesini parolasız üret | Yanlış parola reddedilir; imza kaydı ad, zaman, anlam, özet içerir; onaylı rapor değişmez; liste e-imzasız üretilmez | Eİ-01, Eİ-02, RBM-07, EDC-09 | `tests/test_izlem.py::test_ziyaret_raporu_ve_py_onayi`, `tests/test_randomizasyon.py::test_eimza_olmadan_liste_uretilmez` | |
| OQ-09 | E-imza geçersizleşme | Araştırmacı gönüllüyü imzalasın; bir form kaydını değiştir | "İmza yenilenmeli" rozeti; toplu kilit bu gönüllüyü atlar; yeniden imza mümkündür | Eİ-03, EDC-08 | `tests/test_izlem.py::test_imzadan_sonra_degisen_kayit_yenilenmeli` | |
| OQ-10 | eCRF edit check ve sorgu | Sistolik KB alanına aralık dışı değer ve boş zorunlu alan gir; sorguyu cevapla; seçili sorguları toplu kapat | Otomatik sorgu açılır, kayıt engellenmez; sorgu akışı açık → cevaplandı → kapalı | EDC-01, EDC-02, EDC-03 | `tests/test_ecrf.py::test_edit_check_kosul_ve_yeni_tipler`, `tests/test_gonullu.py::test_sorgulu_tamamlamada_formda_kalma`, `tests/test_izlem.py::test_sorgu_toplu_kapatma_ve_csv` | |
| OQ-11 | Vizit penceresi ve kaçırılan vizit | Randomize et; vizitleri şemadan üret; bir viziti pencere dışında gerçekleştir; birini gerekçesiz kaçırıldı işaretle | Vizitler tanımdan üretilir; pencere dışı işaretlenir; gerekçesiz kaçırma reddedilir | EDC-06 | `tests/test_ecrf.py::test_randomizasyonda_vizitler_tanimdan_uretilir`, `tests/test_gonullu.py::test_kacirilan_vizit_gerekce` | |
| OQ-12 | SAE bildirim süresi | Ciddi AE, ölçüt "hastaneye yatış", farkındalık 20 gün önce; gece işini çalıştır | Panelde süre aşıldı; gece işi özetinde gecikmiş SAE sayısı 1; denetim izinde `zamanlanmis` | GV-01, GV-03 | `tests/test_P3.py::test_gece_isleri_aktif_calismalar` | |
| OQ-13 | SUSAR tespiti | AE: ciddi, beklenmeyen, nedensellik "muhtemel" | SUSAR rozeti; KRI hesabına yansır | GV-02 | `tests/test_rbm.py::test_kri_hesapla_sorunlu_merkez` | |
| OQ-14 | Başvuru ve karar | TİTCK gereken türde çalışma aç; başvuru ekle; kararı onayla | Kontrol listesi TİTCK satırı gösterir; karar sonrası madde tamam | BŞ-01, BŞ-02 | `POST /calismalar/{calisma_id}/basvurular`, `tests/test_roller.py::test_kontrol_listesi_veriden_hesaplanir` | |
| OQ-15 | KRI hesaplama | Sorunlu merkezde sorgu oranı ve geç SAE bildirimi | KRI değerleri eşik üstünde; uyarı seviyesi | RBM-01, GV-04 | `tests/test_rbm.py::test_kri_hesapla_sorunlu_merkez`, `tests/test_rbm.py::test_varsayilan_kri_listesi` | |
| OQ-16 | KRI yetersiz veri | Aday merkez / az gönüllü | Aday merkez hesaba girmez; az merkezde anomali güveni sınırlı | RBM-03 | `tests/test_rbm.py::test_kri_hesapla_aday_merkez_atlanir`, `tests/test_rbm.py::test_anomali_az_merkez_ve_none` | |
| OQ-17 | Uyarı tekilleştirme ve kapanış | Erken uyarıyı iki kez çalıştır; değeri normale döndür; uyarıyı kapat | Tek açık uyarı; otomatik kapanış; kapanış notu | RBM-04, RBM-05 | `tests/test_rbm.py::test_erken_uyari_tekrar_calisma_cogaltmaz`, `tests/test_rbm.py::test_erken_uyari_otomatik_kapanis` | |
| OQ-18 | QTL aşımı | Erken ayrılma oranını limit üstüne çıkar | QTL "aşıldı" | RBM-02 | `tests/test_rbm.py::test_qtl` | |
| OQ-19 | Kriter yapılandırma ve onay | "Hemoglobin ≥ 9 g/dL" kriterini ekle; yapıyı incele; onayla | Yapı lab kategorisinde, güven > 0,7; onay denetim izinde | ES-01, ÇY-04 | `tests/test_web.py::test_kriter_ekle_yapilandirilir`, `tests/test_kriter.py::test_lab_hemoglobin` | |
| OQ-20 | Sapma kapatma | Majör sapmayı etik bildirim tarihi olmadan kapatmayı dene; tarih girip kapat; minör sapmayı kapat | Majörde reddedilir, tarihle kapanır; minör etik tarihsiz kapanır; eski/yeni denetim izinde | RBM-08 | `tests/test_izlem.py::test_sapma_kapatma_majorde_etik_bildirim_zorunlu` | |
| OQ-21 | Hariç kriter ihlali | Hastaya "son 3 ay MI" metni ekle; hariç kriter "son 6 ay MI" | Karar "uygun değil", kanıt cümlesi gösterilir | ES-02, ES-03 | `tests/test_eslestirme.py::test_haric_kriter_ihlali`, `tests/test_eslestirme.py::test_metin_ile_teyit` | |
| OQ-22 | Belirsiz sonuç | Yapısal verisi olmayan hasta | İlgili kriter "belirsiz" | ES-02 | `tests/test_eslestirme.py::test_yapisal_veri_yok_belirsiz` | |
| OQ-23 | İnsan-döngüde kontrol | Eşleştirme çalıştır; "uygun" sonuçta Gonullu tablosunu kontrol et; inceleme kararı ver | Gönüllü kaydı oluşmaz; onay sonrası aday durumunda oluşur | ES-04 | `tests/test_eslestirme.py::test_calisma_icin_tara`, `POST /calismalar/{calisma_id}/eslestirme/{sonuc_id}/incele` | |
| OQ-24 | Halüsinasyon ve güven eşiği | Kaynakta olmayan kanıt döndüren test sağlayıcısı; düşük güven | Sonuç "belirsiz"e düşer | BDM-03, BDM-04 | `tests/test_bdm.py::test_kanit_dogrula_birebir_ve_yakin`, `tests/test_bdm.py::test_belirsizlik_esigi` | |
| OQ-25 | Determinizm ve model sürümü | Aynı hastayı üç kez eşleştir; sonucu incele | Skor ve kriter sonuçları aynı; `model_surumu` dolu | BDM-02, BDM-06 | `tests/test_bdm.py::test_kriter_yapilandir_kural`, `tests/test_eslestirme.py::test_kaydet_ve_guncelle` | |
| OQ-26 | BDM fallback | BDM konteynerini durdur; eşleştir | `yontem=kural`, arayüz rozeti, WARNING log | BDM-05 | `tests/test_bdm.py::test_istemci_ag_hatasinda_kurala_duser` | |
| OQ-27 | İstem PHI kontrolü ve kimliksiz yazım | TCKN içeren metinle istem; kimliksizleştirilmemiş metni API ile yaz | İstem engellenir; API metni kimliksizleştirir | BDM-07, KM-02 | `tests/test_bdm.py::test_phi_kontrol`, `tests/test_web.py::test_csv_hasta_yukleme` | |
| OQ-28 | Kimliksizleştirme kapsamı | TCKN, ad, telefon, adres, tarih, dosya no, kurum, 92 yaş içeren metin seti; ikinci geçiş | Tüm türler maskelenir; şüpheli kalıp raporlanır | KM-01, KM-03 | `tests/test_kimliksizlestirme.py::test_maske_modu_tum_turleri_yakalar`, `tests/test_kimliksizlestirme.py::test_dogrulama_ikinci_gecis` | |
| OQ-29 | Aşırı maskeleme | Klinik terim içeren metinler | Klinik terimler korunur | KM-01 | `tests/test_kimliksizlestirme.py::test_klinik_terimler_korunur` | |
| OQ-30 | FHIR ve CSV – kimlik alanları | Ad, adres, telefon içeren Bundle ve CSV içe aktar; anahtarı değiştirip yeniden anahtarla | Kimlik alanları yok; takma ad HMAC ve merkeze bağlı; yeniden anahtarlama tutarlı | KM-04, ENT-01, ENT-04 | `tests/test_fhir.py::test_kimlik_alanlari_asla_tasinmaz`, `tests/test_web.py::test_takma_ad_hmac_ve_yeniden_anahtarla`, `tests/test_web.py::test_csv_hasta_yukleme` | |
| OQ-31 | Kazanım tahmini açıklanabilirlik | Geçmişi olmayan yeni merkez için tahmin | Havuz öncülü, büzülme açıklaması, geniş aralık | MZ-03 | `tests/test_merkez_zekasi.py::test_kazanim_havuz_yok_oncul` | |
| OQ-32 | Dışa aktarma kayıtları | `oq_denetci` ile tarih filtreli denetim izi CSV; CRA ile sorgu/gönüllü/ziyaret/sapma CSV; sponsor ile deneme | Dosyalar BOM + noktalı virgül; her dışa aktarma denetim izinde; sponsor 403 | Dİ-04, ENT-06 | `tests/test_P1.py::test_denetim_izi_filtre_ve_csv`, `tests/test_izlem.py::test_sorgu_toplu_kapatma_ve_csv` | |
| OQ-33 | TMF: sürüm zinciri, indirme ve bütünlük | PDF yükle; aynı adla yeni sürüm yükle; indir; dosyayı diskte değiştir ve indir; başka kurumun sponsoru indirsin | Önceki sürüm "eskimiş"; indirme 200 ve `goruntule` kaydı; özet uyuşmazlığında 409; sponsor 403 | TMF-01, TMF-02, BŞ-03 | `tests/test_izlem.py::test_belge_indirme_surum_zinciri_ve_yetki`, `GET /calismalar/{calisma_id}/belgeler/{belge_id}/indir` | |
| OQ-34 | TMF: yükleme kontrolleri | EXE, içeriği uyuşmayan PDF, 25 MB üstü dosya yükle | Hepsi reddedilir, mesaj gösterilir | TMF-03 | `tests/test_izlem.py::test_belge_yukleme_kontrolleri` | |
| OQ-35 | Pasifleştirme ve saklama | Kullanıcıyı pasifleştir; hasta saklama betiğini kuru ve gerçek çalıştır; veri sahibi talebiyle tekil kayıt | Giriş engellenir, kayıtlarda kullanıcı adı korunur; süresi dolan bağsız kayıtlar silinir, bağlı kayıt kısıtlanır; denetim izinde takma ad yok | YT-04, KM-05 | `tests/test_web.py::test_rol_kisiti`, `tests/test_P3.py::test_hasta_saklama` | |
| OQ-36 | ODM, CSV paketi, OMOP ve analiz | ODM indir (xml); CSV paketi; OMOP dışa aktar; analiz sayfaları | Her StudyEventRef tanımlı; OID'ler ASCII; merkez, AE, dispozisyon var; BOM; OMOP CSV'leri; analiz taslak kayıtları dışlar | EDC-07, ENT-03, SİS-06 | `tests/test_disa_aktar.py::test_study_event_ref_ve_oidler`, `tests/test_disa_aktar.py::test_merkez_ae_dispozisyon_ve_tekrar`, `tests/test_fhir.py::test_omop_disa_aktar`, `tests/test_analiz.py::test_sayfalar_ve_csv` | |
| OQ-37 | API anahtarı ve belgeler | Anahtar üret, `X-SC-Anahtar` ile çağır, iptal et; oturumsuz `/api/belgeler` | Anahtar sahibinin izinleri geçerli; iptal sonrası 401; belgeler oturumsuz açılmaz | ENT-05 | `tests/test_web.py::test_api_anahtari_ve_sponsor`, `tests/test_P3.py::test_api_belgeleri_oturum_ister` | |
| OQ-38 | Zaman damgası ve açık gün | Kayıt oluştur; DB zamanını kontrol et; sorgu açık gün hesabı | DB UTC; açık gün negatif olmaz | SİS-04 | `tests/test_gonullu.py::test_acik_gun_negatif_degil` | |

## 4. Sapmalar

Uygulama sırasında beklenen sonuçtan sapmalar SAP-OQ-xx numarasıyla aşağıya işlenir (senaryo,
açıklama, sınıf, düzeltme, tekrar test, durum).

| No | Senaryo | Açıklama | Sınıf | Düzeltme | Tekrar test | Durum |
|---|---|---|---|---|---|---|
| | | | | | | |

## 5. Sonuç

Bölüm 3'teki tüm GK senaryoları geçmeden ve açık majör/kritik sapma kalmadan sistem PQ-001'e geçmez.
Sonuç özeti uygulama sonrası doldurulur.

## 6. Onaylar

| Rol | İmza |
|---|---|
| Test uygulayıcıları (T1, T2, T3) | |
| Validasyon Sorumlusu | |
| Kalite Güvence Yöneticisi | |
