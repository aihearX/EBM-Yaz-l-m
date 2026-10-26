# TM-001 İzlenebilirlik Matrisi

| | |
|---|---|
| Belge No | TM-001 |
| Sistem | EBM SmartClinical |
| Hazırlayan | Validasyon Sorumlusu |
| Onaylayan | Kalite Güvence Yöneticisi |

URS → FRS → kod (rota, betik, modül) → otomatik test → kalifikasyon senaryosu izlenebilirliği.
Kritiklik: GK (GCP-kritik) / İK (iş-kritik) / D (destekleyici). Her satırdaki test ve rota
referansı depoda bulunur; `tests/test_P3.py::test_izlenebilirlik_matrisi_kodla_eslesir` bu
belgeyi her sürümde kodla karşılaştırır (olmayan test, betik ya da rota referansı testi düşürür).
"Kalifikasyon" sütunu OQ-001 / IQ-001 / PQ-001 senaryo numarasıdır; sonuçlar ilgili raporda tutulur.

## 1. Çalışma yönetimi

| URS | Kritiklik | FRS | Kod | Otomatik test | Kalifikasyon |
|---|---|---|---|---|---|
| URS-ÇY-01 | İK | FRS-01 | `GET /calismalar/yeni`, `smartclinical/models/calisma.py` | `tests/test_web.py::test_calisma_olustur_ve_denetim`, `tests/test_sihirbaz.py::test_kurum_turlerinde_etiket_ve_faz` | OQ-01 |
| URS-ÇY-02 | GK | FRS-02 | `POST /calismalar/{calisma_id}/durum`, `smartclinical/web/calismalar.py` (`kontrol_listesi`) | `tests/test_roller.py::test_kontrol_listesi_veriden_hesaplanir`, `tests/test_roller.py::test_asama_degisimi_gerekce_zorunlu` | OQ-01 |
| URS-ÇY-03 | GK | FRS-03 | `POST /calismalar/{calisma_id}/protokol/versiyon` | `tests/test_web.py::test_calisma_olustur_ve_denetim` (sayfa erişimi) | OQ-02 |
| URS-ÇY-04 | GK | FRS-04 | `POST /calismalar/{calisma_id}/protokol/kriter`, `POST /calismalar/{calisma_id}/protokol/kriter/{kriter_id}/onayla` | `tests/test_web.py::test_kriter_ekle_yapilandirilir`, `tests/test_kriter.py::test_lab_hemoglobin` | OQ-19 |
| URS-ÇY-05 | İK | FRS-05 | `smartclinical/models/merkez.py` (aktivasyon, ilk hasta tarihleri), `smartclinical/models/izlem.py` (SIV) | `tests/test_izlem.py::test_ziyaret_raporu_ve_py_onayi` | OQ-08 |
| URS-ÇY-06 | D | FRS-06 | `GET /`, `smartclinical/web/pano.py` | `tests/test_roller.py::test_cra_panosu_yalnizca_atandigi_calismalar`, `tests/test_roller.py::test_genel_bakis_ve_liste_ayni_sayilari_gosterir` | PQ-M11 |
| URS-ÇY-07 | İK | FRS-72 | `GET /sihirbaz/1` … `/4`, `smartclinical/services/kurulum.py` | `tests/test_sihirbaz.py::test_sihirbaz_dort_adim_tek_islemde_olusturur`, `tests/test_sihirbaz.py::test_arastirmaci_tekil_modda_kurar_cro_modda_403` | OQ-03 |

## 2. Merkez yönetimi ve merkez zekâsı

| URS | Kritiklik | FRS | Kod | Otomatik test | Kalifikasyon |
|---|---|---|---|---|---|
| URS-MZ-01 | İK | FRS-07 | `POST /merkezler`, `POST /merkezler/{mid}/arastirmaci` | `tests/test_roller.py::test_sponsor_merkez_detayi_kendi_calismalari` | OQ-04 |
| URS-MZ-02 | İK | FRS-08 | `POST /calismalar/{calisma_id}/merkezler/{cm_id}/durum` | `tests/test_roller.py::test_kontrol_listesi_veriden_hesaplanir` | OQ-04 |
| URS-MZ-03 | İK | FRS-09 | `smartclinical/services/merkez_zekasi/kazanim.py`, `POST /calismalar/{calisma_id}/merkez-zekasi/guncelle` | `tests/test_merkez_zekasi.py::test_kazanim_tahmini_temel`, `tests/test_merkez_zekasi.py::test_kazanim_buzulme_az_veride_daha_fazla`, `tests/test_merkez_zekasi.py::test_kazanim_havuz_yok_oncul` | OQ-31, PQ-M7 |
| URS-MZ-04 | İK | FRS-10 | `smartclinical/services/merkez_zekasi/aktivasyon.py` | `tests/test_merkez_zekasi.py::test_gecikme_fit_ve_auc`, `tests/test_merkez_zekasi.py::test_gecikme_modeli_oncul` | PQ-M8 |
| URS-MZ-05 | İK | FRS-11 | `smartclinical/services/merkez_zekasi/siralama.py` | `tests/test_merkez_zekasi.py::test_merkez_sirala`, `tests/test_merkez_zekasi.py::test_merkez_sirala_agirlik_ezme` | – |
| URS-MZ-06 | D | FRS-12 | `smartclinical/services/merkez_zekasi/kazanim.py` (`calisma_kazanim_projeksiyonu`) | `tests/test_merkez_zekasi.py::test_projeksiyon_monte_carlo` | – |
| URS-MZ-07 | İK | FRS-73 | `smartclinical/scripts/gece_isleri.py` | `tests/test_P3.py::test_gece_isleri_aktif_calismalar` | IQ-11 |

## 3. Etik kurul ve TİTCK başvuruları

| URS | Kritiklik | FRS | Kod | Otomatik test | Kalifikasyon |
|---|---|---|---|---|---|
| URS-BŞ-01 | GK | FRS-13 | `POST /calismalar/{calisma_id}/basvurular`, `smartclinical/models/basvuru.py` | `tests/test_web.py::test_calisma_olustur_ve_denetim` (sayfa erişimi) | OQ-14 |
| URS-BŞ-02 | İK | FRS-14 | `POST /calismalar/{calisma_id}/basvurular/{basvuru_id}/karar`, `smartclinical/models/basvuru.py` (`sure_gun`) | `tests/test_roller.py::test_kontrol_listesi_veriden_hesaplanir` | OQ-14 |
| URS-BŞ-03 | İK | FRS-15 | `GET /calismalar/{calisma_id}/belgeler` (bölge 03/04) | `tests/test_izlem.py::test_belge_indirme_surum_zinciri_ve_yetki` | OQ-33 |

## 4. Elektronik veri toplama

| URS | Kritiklik | FRS | Kod | Otomatik test | Kalifikasyon |
|---|---|---|---|---|---|
| URS-EDC-01 | GK | FRS-16 | `smartclinical/services/ecrf.py`, `POST /calismalar/{calisma_id}/tasarim/form/yeni` | `tests/test_ecrf.py::test_kol_vizit_form_ekle`, `tests/test_ecrf.py::test_sozlesme_fonksiyonlari_mevcut`, `tests/test_ecrf.py::test_kayitli_formda_alan_silme_reddi_ve_versiyon` | OQ-10 |
| URS-EDC-02 | GK | FRS-17 | `smartclinical/services/ecrf.py` (edit-check), `POST /gonulluler/{gid}/form/{form_id}` | `tests/test_ecrf.py::test_edit_check_kosul_ve_yeni_tipler`, `tests/test_gonullu.py::test_sorgulu_tamamlamada_formda_kalma` | OQ-10 |
| URS-EDC-03 | GK | FRS-18 | `POST /gonulluler/{gid}/sorgu/{sid}`, `POST /calismalar/{calisma_id}/veri/sorgu-toplu` | `tests/test_gonullu.py::test_acik_gun_negatif_degil`, `tests/test_izlem.py::test_sorgu_toplu_kapatma_ve_csv` | OQ-10 |
| URS-EDC-04 | GK | FRS-19 | `POST /gonulluler/{gid}/form-kaydi/{fk_id}/sdv`, `POST /calismalar/{calisma_id}/veri/kilit`, `POST /calismalar/{calisma_id}/veri/kilit-ac/{fk_id}` | `tests/test_izlem.py::test_arastirmaci_imzasi_ve_toplu_kilit` | OQ-05 |
| URS-EDC-05 | GK | FRS-20 | `smartclinical/services/denetim.py` | `tests/test_gonullu.py::test_ae_duzenleme_denetim_izi`, `tests/test_denetim.py::test_zincir_gecerli` | OQ-05, OQ-06 |
| URS-EDC-06 | GK | FRS-21 | `smartclinical/models/tasarim.py`, `POST /gonulluler/{gid}/vizit/{vid}` | `tests/test_ecrf.py::test_randomizasyonda_vizitler_tanimdan_uretilir`, `tests/test_gonullu.py::test_kacirilan_vizit_gerekce` | OQ-11 |
| URS-EDC-07 | İK | FRS-22 | `GET /calismalar/{calisma_id}/veri/disa-aktar`, `smartclinical/web/disa_aktar.py` | `tests/test_disa_aktar.py::test_study_event_ref_ve_oidler`, `tests/test_disa_aktar.py::test_merkez_ae_dispozisyon_ve_tekrar`, `tests/test_disa_aktar.py::test_csv_paketi_bom_ve_ayirici` | OQ-36 |
| URS-EDC-08 | GK | FRS-74 | `POST /calismalar/{calisma_id}/veri/imza/{gid}`, `GET /calismalar/{calisma_id}/veri/imza` | `tests/test_izlem.py::test_arastirmaci_imzasi_ve_toplu_kilit`, `tests/test_izlem.py::test_imzadan_sonra_degisen_kayit_yenilenmeli` | OQ-09 |
| URS-EDC-09 | GK | FRS-75 | `POST /calismalar/{calisma_id}/randomizasyon/uret` | `tests/test_randomizasyon.py::test_blok_dengesi_oranlara_uyar`, `tests/test_randomizasyon.py::test_eimza_olmadan_liste_uretilmez` | OQ-08 |

## 5. Güvenlik (farmakovijilans)

| URS | Kritiklik | FRS | Kod | Otomatik test | Kalifikasyon |
|---|---|---|---|---|---|
| URS-GV-01 | GK | FRS-23 | `POST /gonulluler/{gid}/advers-olay`, `smartclinical/models/guvenlik.py` | `tests/test_gonullu.py::test_ae_duzenleme_denetim_izi`, `tests/test_analiz.py::test_advers_olay_ozeti` | OQ-12 |
| URS-GV-02 | GK | FRS-24 | `smartclinical/models/guvenlik.py` (`susar`) | `tests/test_rbm.py::test_kri_hesapla_sorunlu_merkez` | OQ-13 |
| URS-GV-03 | GK | FRS-25 | `smartclinical/models/guvenlik.py` (`bildirim_suresi_gun`), `smartclinical/scripts/gece_isleri.py` | `tests/test_P3.py::test_gece_isleri_aktif_calismalar`, `tests/test_rbm.py::test_kri_hesapla_sorunlu_merkez` | OQ-12 |
| URS-GV-04 | GK | FRS-26 | `POST /gonulluler/{gid}/advers-olay/{aid}/bildirim`, `smartclinical/services/rbm/gostergeler.py` | `tests/test_rbm.py::test_kri_hesapla_sorunlu_merkez` | OQ-15 |

## 6. Risk bazlı izlem

| URS | Kritiklik | FRS | Kod | Otomatik test | Kalifikasyon |
|---|---|---|---|---|---|
| URS-RBM-01 | GK | FRS-27 | `smartclinical/services/rbm/gostergeler.py` | `tests/test_rbm.py::test_varsayilan_kri_listesi`, `tests/test_rbm.py::test_calismaya_ozel_kri_tanimi` | OQ-15 |
| URS-RBM-02 | GK | FRS-28 | `smartclinical/services/rbm/uyari.py` (`qtl_guncelle`) | `tests/test_rbm.py::test_qtl` | OQ-18 |
| URS-RBM-03 | İK | FRS-29 | `smartclinical/services/rbm/anomali.py` | `tests/test_rbm.py::test_anomali_aykiri_tespit`, `tests/test_rbm.py::test_anomali_az_merkez_ve_none` | OQ-16 |
| URS-RBM-04 | İK | FRS-30 | `POST /calismalar/{calisma_id}/rbm/calistir` | `tests/test_rbm.py::test_erken_uyari_uretimi`, `tests/test_rbm.py::test_erken_uyari_tekrar_calisma_cogaltmaz`, `tests/test_rbm.py::test_erken_uyari_otomatik_kapanis` | OQ-17 |
| URS-RBM-05 | İK | FRS-31 | `POST /calismalar/{calisma_id}/rbm/uyari/{uyari_id}` | `tests/test_izlem.py::test_aksiyon_uyarisindan_tetiklenmis_ziyaret` | OQ-17 |
| URS-RBM-06 | İK | FRS-32 | `smartclinical/services/rbm/uyari.py` (`bilesik_risk_puani`, `izlem_onerisi`) | `tests/test_rbm.py::test_bilesik_puan_ve_oneri` | – |
| URS-RBM-07 | İK | FRS-33 | `POST /calismalar/{calisma_id}/izlem/ziyaret`, `POST /calismalar/{calisma_id}/izlem/tetikle/{uyari_id}`, `POST /calismalar/{calisma_id}/izlem/ziyaret/{zid}/onay` | `tests/test_izlem.py::test_ziyaret_raporu_ve_py_onayi`, `tests/test_izlem.py::test_acik_bulgu_sonraki_ziyarete_tasinir`, `tests/test_izlem.py::test_aksiyon_uyarisindan_tetiklenmis_ziyaret` | OQ-08 |
| URS-RBM-08 | GK | FRS-34 | `POST /calismalar/{calisma_id}/izlem/sapma`, `POST /calismalar/{calisma_id}/izlem/sapma/{sid}` | `tests/test_izlem.py::test_sapma_kapatma_majorde_etik_bildirim_zorunlu` | OQ-20 |

## 7. Eşleştirme ve BDM

| URS | Kritiklik | FRS | Kod | Otomatik test | Kalifikasyon |
|---|---|---|---|---|---|
| URS-ES-01 | GK | FRS-04 | `smartclinical/services/kriter/ayristirici.py` | `tests/test_kriter.py::test_lab_hemoglobin`, `tests/test_kriter.py::test_tani_zaman_penceresi` | OQ-19 |
| URS-ES-02 | İK | FRS-35 | `POST /calismalar/{calisma_id}/eslestirme/calistir` | `tests/test_eslestirme.py::test_uygun_hasta`, `tests/test_eslestirme.py::test_haric_kriter_ihlali`, `tests/test_eslestirme.py::test_yapisal_veri_yok_belirsiz` | OQ-21, OQ-22 |
| URS-ES-03 | GK | FRS-36 | `smartclinical/services/bdm/korumalar.py` | `tests/test_bdm.py::test_kanit_dogrula_birebir_ve_yakin`, `tests/test_eslestirme.py::test_metin_ile_teyit` | OQ-21, OQ-24 |
| URS-ES-04 | GK | FRS-37 | `POST /calismalar/{calisma_id}/eslestirme/{sonuc_id}/incele` | `tests/test_eslestirme.py::test_kaydet_ve_guncelle`, `tests/test_eslestirme.py::test_calisma_icin_tara` | OQ-23 |
| URS-ES-05 | İK | FRS-38 | `ml/degerlendirme/degerlendir.py` | `tests/test_ml_metrikler.py::test_karisiklik_ve_duyarlilik`, `tests/test_ml_metrikler.py::test_halusinasyon_orani` | IQ-13, PQ-M1 |
| URS-ES-06 | İK | FRS-39 | `GET /calismalar/{calisma_id}/eslestirme-golge` | `tests/test_eslestirme.py::test_golge_mod_karsilastir` | PQ-M2, PQ-M3 |
| URS-BDM-01 | GK | FRS-41 | `smartclinical/services/bdm/istemci.py`, `deploy/docker-compose.yml` (internal ağ) | `tests/test_bdm.py::test_saglayici_fabrikasi` | IQ-10 |
| URS-BDM-02 | GK | FRS-42 | `smartclinical/services/bdm/istemci.py` (sıcaklık 0) | `tests/test_bdm.py::test_kriter_yapilandir_kural` | OQ-25 |
| URS-BDM-03 | GK | FRS-36 | `smartclinical/services/bdm/korumalar.py` | `tests/test_bdm.py::test_kanit_dogrula_birebir_ve_yakin` | OQ-24, PQ-M5 |
| URS-BDM-04 | GK | FRS-43 | `smartclinical/services/bdm/korumalar.py` | `tests/test_bdm.py::test_belirsizlik_esigi`, `tests/test_bdm.py::test_cogunluk_oyu` | OQ-24 |
| URS-BDM-05 | İK | FRS-44 | `smartclinical/services/bdm/istemci.py` | `tests/test_bdm.py::test_istemci_ag_hatasinda_kurala_duser`, `tests/test_bdm.py::test_ag_hatasi_turkce_istisna` | OQ-26 |
| URS-BDM-06 | GK | FRS-45 | `smartclinical/models/hasta.py` (`EslestirmeSonucu.model_surumu`) | `tests/test_eslestirme.py::test_kaydet_ve_guncelle` | OQ-25 |
| URS-BDM-07 | GK | FRS-46 | `smartclinical/services/bdm/korumalar.py` (`phi_kontrol`) | `tests/test_bdm.py::test_phi_kontrol` | OQ-27 |

## 8. Kimliksizleştirme

| URS | Kritiklik | FRS | Kod | Otomatik test | Kalifikasyon |
|---|---|---|---|---|---|
| URS-KM-01 | GK | FRS-47 | `smartclinical/services/kimliksizlestirme/__init__.py`, `POST /api/v1/yz/kimliksizlestir` | `tests/test_kimliksizlestirme.py::test_maske_modu_tum_turleri_yakalar`, `tests/test_kimliksizlestirme.py::test_klinik_terimler_korunur`, `tests/test_web.py::test_api_saglik_ve_kimliksizlestir` | OQ-28, OQ-29 |
| URS-KM-02 | GK | FRS-48 | `smartclinical/api/hastalar.py`, `POST /merkezler/{mid}/hasta-yukle` | `tests/test_web.py::test_csv_hasta_yukleme` | OQ-27 |
| URS-KM-03 | İK | FRS-49 | `smartclinical/services/kimliksizlestirme/__init__.py` (`metni_dogrula`) | `tests/test_kimliksizlestirme.py::test_dogrulama_ikinci_gecis`, `tests/test_kimliksizlestirme.py::test_ozet_rapor` | OQ-28 |
| URS-KM-04 | GK | FRS-50 | `smartclinical/services/fhir/__init__.py`, `smartclinical/scripts/yeniden_anahtarla.py` | `tests/test_fhir.py::test_kimlik_alanlari_asla_tasinmaz`, `tests/test_fhir.py::test_takma_kayit_no_deterministik_ve_merkeze_bagli`, `tests/test_web.py::test_takma_ad_hmac_ve_yeniden_anahtarla` | OQ-30 |
| URS-KM-05 | GK | FRS-76 | `smartclinical/scripts/hasta_saklama.py` | `tests/test_P3.py::test_hasta_saklama` | OQ-35 |

## 9. TMF, denetim izi, e-imza, yetki

| URS | Kritiklik | FRS | Kod | Otomatik test | Kalifikasyon |
|---|---|---|---|---|---|
| URS-TMF-01 | İK | FRS-51 | `GET /calismalar/{calisma_id}/belgeler`, `smartclinical/models/belge.py` | `tests/test_izlem.py::test_belge_indirme_surum_zinciri_ve_yetki` | OQ-33 |
| URS-TMF-02 | GK | FRS-51 | `POST /calismalar/{calisma_id}/belgeler`, `GET /calismalar/{calisma_id}/belgeler/{belge_id}/indir` | `tests/test_izlem.py::test_belge_indirme_surum_zinciri_ve_yetki` | OQ-33 |
| URS-TMF-03 | D | FRS-52 | `smartclinical/web/belgeler.py` (`dosya_kontrol`), `deploy/nginx/smartclinical.conf` | `tests/test_izlem.py::test_belge_yukleme_kontrolleri` | OQ-34 |
| URS-Dİ-01 | GK | FRS-20, FRS-53 | `smartclinical/services/denetim.py` | `tests/test_denetim.py::test_zincir_gecerli`, `tests/test_gonullu.py::test_ae_duzenleme_denetim_izi` | OQ-05, OQ-06 |
| URS-Dİ-02 | GK | FRS-53 | `deploy/postgres/yetkiler.sql` | – (veritabanı düzeyi) | IQ-9, OQ-07 |
| URS-Dİ-03 | GK | FRS-53 | `smartclinical/scripts/denetim_dogrula.py`, `smartclinical/models/denetim.py` (`DenetimZincir`) | `tests/test_denetim.py::test_zincir_bozulma_tespiti`, `tests/test_denetim.py::test_eszamanli_kayit_zinciri_bozmaz`, `tests/test_denetim.py::test_anahtar_degisince_dogrulama_basarisiz`, `tests/test_denetim.py::test_hash_hmac_anahtara_bagli` | OQ-07 |
| URS-Dİ-04 | GK | FRS-54 | `GET /yonetim/denetim`, `GET /calismalar/{calisma_id}/denetim` | `tests/test_P1.py::test_denetim_izi_filtre_ve_csv`, `tests/test_web.py::test_rol_kisiti` | OQ-32 |
| URS-Eİ-01 | GK | FRS-55 | `smartclinical/services/denetim.py` (`imzala`) | `tests/test_denetim.py::test_eimza`, `tests/test_izlem.py::test_ziyaret_raporu_ve_py_onayi` | OQ-08 |
| URS-Eİ-02 | GK | FRS-55 | `POST /calismalar/{calisma_id}/belgeler/{belge_id}/onayla`, `POST /gonulluler/{gid}/form-kaydi/{fk_id}/kilitle` | `tests/test_izlem.py::test_ziyaret_raporu_ve_py_onayi`, `tests/test_randomizasyon.py::test_eimza_olmadan_liste_uretilmez` | OQ-08 |
| URS-Eİ-03 | GK | FRS-55 | `smartclinical/web/veri_islem.py` (`imza_durumu`) | `tests/test_izlem.py::test_imzadan_sonra_degisen_kayit_yenilenmeli`, `tests/test_denetim.py::test_eimza_icerik_ozeti_anahtardan_bagimsiz` | OQ-09 |
| URS-YT-01 | GK | FRS-56 | `smartclinical/services/yetki.py` (`IZINLER`) | `tests/test_roller.py::test_rol_rota_matrisi`, `tests/test_roller.py::test_matris_dokumanla_uyumlu`, `tests/test_ekip.py::test_izin_haritasi` | OQ-02, OQ-03 |
| URS-YT-02 | GK | FRS-56 | `smartclinical/services/yetki.py` (`calisma_erisimi`, `gonullu_erisimi`) | `tests/test_P1.py::test_arastirmaci_baska_merkezin_hastasina_erisemez`, `tests/test_roller.py::test_merkez_rolleri_kendi_merkezini_gorur`, `tests/test_roller.py::test_sponsor_kurum_filtresi_ve_sekmeler`, `tests/test_izlem.py::test_merkez_rolu_yalnizca_kendi_merkezini_gorur` | OQ-02, OQ-03 |
| URS-YT-03 | GK | FRS-57 | `smartclinical/services/yetki.py`, `POST /hesap/parola` | `tests/test_web.py::test_hatali_giris_ve_sureli_kilit`, `tests/test_web.py::test_parola_degistir_ve_gecmis`, `tests/test_web.py::test_ilk_giriste_parola_degisimi_zorunlu`, `tests/test_web.py::test_ip_basina_deneme_siniri` | OQ-04 |
| URS-YT-04 | GK | FRS-58 | `POST /yonetim/kullanicilar/{kid}/durum` | `tests/test_web.py::test_rol_kisiti` | OQ-35 |
| URS-YT-05 | İK | FRS-77 | `POST /calismalar/{calisma_id}/ekip/ekle`, `smartclinical/services/yetki.py` (`kisit_aktif`) | `tests/test_ekip.py::test_ilk_atama_kisiti_baslatir`, `tests/test_ekip.py::test_kendini_cikaramaz_ve_cikarma_denetimi` | OQ-02 |

## 10. Entegrasyon ve sistem

| URS | Kritiklik | FRS | Kod | Otomatik test | Kalifikasyon |
|---|---|---|---|---|---|
| URS-ENT-01 | İK | FRS-60 | `POST /api/v1/hbys/senkron`, `smartclinical/services/fhir/hbys.py` | `tests/test_fhir.py::test_bundle_to_hasta`, `tests/test_fhir.py::test_mock_hbys` | IQ-12, OQ-30 |
| URS-ENT-02 | D | FRS-61 | `GET /api/v1/fhir/ResearchStudy/{cid}`, `GET /api/v1/fhir/ResearchSubject/{gid}` | `tests/test_fhir.py::test_research_study_ve_subject` | – |
| URS-ENT-03 | D | FRS-62 | `smartclinical/services/fhir/omop.py`, `smartclinical/scripts/omop_aktar.py` | `tests/test_fhir.py::test_omop_disa_aktar` | OQ-36 |
| URS-ENT-04 | İK | FRS-63 | `POST /merkezler/{mid}/hasta-yukle` | `tests/test_web.py::test_csv_hasta_yukleme` | OQ-30 |
| URS-ENT-05 | D | FRS-64 | `POST /yonetim/api-anahtarlari`, `GET /api/belgeler` | `tests/test_web.py::test_api_anahtari_ve_sponsor`, `tests/test_P3.py::test_api_belgeleri_oturum_ister` | OQ-37 |
| URS-ENT-06 | İK | FRS-78 | `GET /calismalar/{calisma_id}/veri/sorgular.csv`, `GET /calismalar/{calisma_id}/gonulluler.csv`, `GET /calismalar/{calisma_id}/izlem/ziyaretler.csv`, `GET /calismalar/{calisma_id}/izlem/sapmalar.csv` | `tests/test_izlem.py::test_sorgu_toplu_kapatma_ve_csv` | OQ-32 |
| URS-SİS-01 | İK | FRS-65 | `deploy/docker-compose.yml`, `deploy/systemd/smartclinical.service` | – | IQ-1..3 |
| URS-SİS-02 | GK | FRS-66 | `deploy/yedekleme.sh` | – | IQ-7 |
| URS-SİS-03 | GK | FRS-67 | `deploy/nginx/smartclinical.conf` | `tests/test_web.py::test_guvenlik_basliklari` | IQ-5, IQ-6 |
| URS-SİS-04 | GK | FRS-70 | `smartclinical/models/_ortak.py` (`simdi`) | `tests/test_gonullu.py::test_acik_gun_negatif_degil` | OQ-38 |
| URS-SİS-05 | GK | FRS-71 | `smartclinical/main.py` (güvenlik başlıkları, oturumlu API belgeleri), `smartclinical/api/sistem.py` | `tests/test_web.py::test_guvenlik_basliklari`, `tests/test_P3.py::test_saglik_anonim_surum_vermez`, `tests/test_P3.py::test_api_belgeleri_oturum_ister` | IQ-14 |
| URS-SİS-06 | İK | FRS-79 | `GET /calismalar/{calisma_id}/analiz`, `GET /calismalar/{calisma_id}/analiz/tablo1.csv` | `tests/test_analiz.py::test_sayfalar_ve_csv`, `tests/test_analiz.py::test_sponsor_ve_cra_403` | OQ-36 |

## 11. Kapsam dışı bırakılan eski gereksinimler

Aşağıdaki maddeler önceki belge sürümlerinde yer alıyordu; kodda karşılığı olmadığı için
gereksinim listesinden çıkarıldı ve bu matriste izlenmez:

- Kurumsal dizin (LDAP/AD) ile kimlik doğrulama.
- İngilizce arayüz.
- E-posta (SMTP) uyarıları; uyarılar arayüzde ve gece işi çıktısında gösterilir.
- Zamanlanmış HBYS eşitlemesi; eşitleme API üzerinden elle tetiklenir.
- Uygulama düzeyinde iki aşamalı doğrulama (TOTP); uzaktan erişim hastane VPN'i ile sağlanır.
- SDTM/XPT dışa aktarımı; veri CSV paketi ve CDISC ODM olarak verilir.
- Yük testi (50 eşzamanlı kullanıcı) ve otomatik şema migrasyonu.
