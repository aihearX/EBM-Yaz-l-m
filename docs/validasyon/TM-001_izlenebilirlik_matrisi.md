# TM-001 İzlenebilirlik Matrisi

| | |
|---|---|
| Belge No | TM-001 |
| Sistem | EBM SmartClinical v1.4.2 |
| Sürüm | 2.0 |
| Tarih | 2026-06-10 |
| Hazırlayan | Validasyon Sorumlusu |
| Onaylayan | Kalite Güvence Yöneticisi |

URS → FRS → test senaryosu izlenebilirliği. Kritiklik: GK / İK / D. Durum: OQ/IQ/PQ sonucu.

| URS | Kritiklik | FRS | Birim/entegrasyon testi | IQ / OQ / PQ | Durum |
|---|---|---|---|---|---|
| URS-ÇY-01 | İK | FRS-01 | tests/test_calisma.py | OQ-01 (dolaylı) | Geçti |
| URS-ÇY-02 | GK | FRS-02 | tests/test_calisma.py::test_durum_on_kosul | OQ-01 | Geçti |
| URS-ÇY-03 | GK | FRS-03 | tests/test_calisma.py | OQ-19 | Geçti |
| URS-ÇY-04 | GK | FRS-04 | tests/test_kriter.py | OQ-19 | Geçti |
| URS-ÇY-05 | İK | FRS-05 | tests/test_merkez.py | – | Birim testi |
| URS-ÇY-06 | D | FRS-06 | tests/test_web.py | PQ-M11 | PQ sürüyor |
| URS-MZ-01 | İK | FRS-07 | tests/test_merkez.py | – | Birim testi |
| URS-MZ-02 | İK | FRS-08 | tests/test_merkez.py | – | Birim testi |
| URS-MZ-03 | İK | FRS-09 | tests/test_merkez_zekasi.py::test_kazanim_* | OQ-31, PQ-M7 | OQ geçti, PQ sürüyor |
| URS-MZ-04 | İK | FRS-10 | tests/test_merkez_zekasi.py::test_gecikme_* | PQ-M8 | PQ sürüyor |
| URS-MZ-05 | İK | FRS-11 | tests/test_merkez_zekasi.py::test_siralama | – | Birim testi |
| URS-MZ-06 | D | FRS-12 | tests/test_merkez_zekasi.py::test_projeksiyon | – | Birim testi |
| URS-BŞ-01 | GK | FRS-13 | tests/test_basvuru.py | OQ-14 | Geçti |
| URS-BŞ-02 | İK | FRS-14 | tests/test_basvuru.py | OQ-14 | Geçti |
| URS-BŞ-03 | İK | FRS-15 | tests/test_belge.py | OQ-33 | Geçti |
| URS-EDC-01 | GK | FRS-16 | tests/test_edc.py | OQ-10 | Geçti |
| URS-EDC-02 | GK | FRS-17 | tests/test_edc.py::test_edit_check | OQ-10 | Geçti |
| URS-EDC-03 | GK | FRS-18 | tests/test_edc.py | OQ-10, OQ-15 | Geçti |
| URS-EDC-04 | GK | FRS-19 | tests/test_edc.py::test_kilit | OQ-05 | Geçti |
| URS-EDC-05 | GK | FRS-20 | tests/test_denetim.py | OQ-05, OQ-06 | Geçti |
| URS-EDC-06 | GK | FRS-21 | tests/test_edc.py::test_vizit_penceresi | OQ-11 | Geçti |
| URS-EDC-07 | İK | FRS-22 | tests/test_disa_aktar.py | – | Birim testi |
| URS-GV-01 | GK | FRS-23 | tests/test_guvenlik.py | OQ-12 | Geçti |
| URS-GV-02 | GK | FRS-24 | tests/test_guvenlik.py::test_susar | OQ-13 | Geçti |
| URS-GV-03 | GK | FRS-25 | tests/test_guvenlik.py::test_bildirim_suresi | OQ-12 | Geçti |
| URS-GV-04 | GK | FRS-26 | tests/test_rbm.py | OQ-15 | Geçti |
| URS-RBM-01 | GK | FRS-27 | tests/test_rbm.py | OQ-15 | Geçti |
| URS-RBM-02 | GK | FRS-28 | tests/test_rbm.py::test_qtl | OQ-18 | Geçti |
| URS-RBM-03 | İK | FRS-29 | tests/test_rbm.py::test_anomali | OQ-16 | Geçti |
| URS-RBM-04 | İK | FRS-30 | tests/test_rbm.py::test_erken_uyari | OQ-17, PQ-M9 | OQ geçti |
| URS-RBM-05 | İK | FRS-31 | tests/test_rbm.py | OQ-17 | Geçti |
| URS-RBM-06 | İK | FRS-32 | tests/test_rbm.py | – | Birim testi |
| URS-RBM-07 | İK | FRS-33 | tests/test_izlem.py | OQ-08 | Geçti |
| URS-RBM-08 | GK | FRS-34 | tests/test_izlem.py | OQ-11 (dolaylı) | Geçti |
| URS-ES-01 | GK | FRS-04 | tests/test_kriter.py | OQ-19 | Geçti |
| URS-ES-02 | İK | FRS-35 | tests/test_eslestirme.py | OQ-21, OQ-22 | Geçti |
| URS-ES-03 | GK | FRS-36 | tests/test_bdm.py::test_kanit_dogrulama | OQ-21, OQ-24 | Geçti |
| URS-ES-04 | GK | FRS-37 | tests/test_eslestirme.py::test_gonullu_olusmaz | OQ-20 | Geçti |
| URS-ES-05 | İK | FRS-38 | ml/degerlendirme | IQ-21, PQ-M1 | IQ geçti, PQ sürüyor |
| URS-ES-06 | İK | FRS-39 | tests/test_eslestirme.py::test_golge_mod | OQ-38, PQ-M2/M3 | OQ geçti |
| URS-ES-07 | D | FRS-40 | – | OQ-32, IQ-13 | Geçti |
| URS-BDM-01 | GK | FRS-41 | tests/test_bdm.py | IQ-14 | Geçti |
| URS-BDM-02 | GK | FRS-42 | tests/test_bdm.py | OQ-23 | Geçti |
| URS-BDM-03 | GK | FRS-36 | tests/test_bdm.py::test_halusinasyon | OQ-24, PQ-M5 | OQ geçti |
| URS-BDM-04 | GK | FRS-43 | tests/test_bdm.py::test_guven_esigi | OQ-24 | Geçti |
| URS-BDM-05 | İK | FRS-44 | tests/test_bdm.py::test_fallback | OQ-26 | Geçti |
| URS-BDM-06 | GK | FRS-45 | tests/test_eslestirme.py | OQ-25 | Geçti |
| URS-BDM-07 | GK | FRS-46 | tests/test_bdm.py::test_phi | OQ-27 | Geçti |
| URS-KM-01 | GK | FRS-47 | tests/test_kimliksizlestirme.py | OQ-28, OQ-29, PQ-M10 | OQ geçti |
| URS-KM-02 | GK | FRS-48 | tests/test_hasta.py | OQ-27 | Geçti |
| URS-KM-03 | İK | FRS-49 | tests/test_kimliksizlestirme.py::test_dogrula | OQ-28 | Geçti |
| URS-KM-04 | GK | FRS-50 | tests/test_fhir.py | OQ-30 | Geçti |
| URS-TMF-01 | İK | FRS-51 | tests/test_belge.py | OQ-33 | Geçti |
| URS-TMF-02 | GK | FRS-51 | tests/test_belge.py::test_sha256 | OQ-33 | Geçti |
| URS-TMF-03 | D | FRS-52 | – | IQ-19 (nginx) | Geçti |
| URS-Dİ-01 | GK | FRS-20, FRS-53 | tests/test_denetim.py | OQ-05, OQ-06 | Geçti |
| URS-Dİ-02 | GK | FRS-53 | – | IQ-9, OQ-07 | Geçti |
| URS-Dİ-03 | GK | FRS-53 | tests/test_denetim.py::test_zincir | OQ-07 | Geçti |
| URS-Dİ-04 | GK | FRS-54 | tests/test_web.py | OQ-34 | Geçti |
| URS-Eİ-01 | GK | FRS-55 | tests/test_imza.py | OQ-08 | Geçti |
| URS-Eİ-02 | GK | FRS-55 | tests/test_imza.py | OQ-08 | Geçti |
| URS-Eİ-03 | GK | FRS-55 | tests/test_imza.py::test_gecersiz | OQ-09 | Geçti |
| URS-YT-01 | GK | FRS-56 | tests/test_yetki.py | OQ-02, OQ-03 | Geçti |
| URS-YT-02 | GK | FRS-56 | tests/test_yetki.py::test_merkez_kapsam | OQ-02, OQ-03 | Geçti |
| URS-YT-03 | GK | FRS-57 | tests/test_yetki.py | OQ-04 | Geçti |
| URS-YT-04 | GK | FRS-58 | tests/test_yetki.py | OQ-35 | Geçti |
| URS-YT-05 | D | FRS-59 | – | – | v1.5'e ertelendi (DK-2026-031) |
| URS-ENT-01 | İK | FRS-60 | tests/test_fhir.py | IQ-16, OQ-30 | Geçti |
| URS-ENT-02 | D | FRS-61 | tests/test_fhir.py | – | Birim testi |
| URS-ENT-03 | D | FRS-62 | tests/test_fhir.py::test_omop | OQ-36 | Geçti |
| URS-ENT-04 | İK | FRS-63 | tests/test_csv.py | – | Birim testi |
| URS-ENT-05 | D | FRS-64 | tests/test_api.py | – | Birim testi |
| URS-SİS-01 | İK | FRS-65 | – | IQ-1..3 | Geçti |
| URS-SİS-02 | GK | FRS-66 | – | IQ-7 | Geçti |
| URS-SİS-03 | GK | FRS-67 | – | IQ-5, IQ-6 | Geçti |
| URS-SİS-04 | D | FRS-68 | tests/performans | PQ-M12 | PQ sürüyor |
| URS-SİS-05 | D | FRS-69 | – | – | İngilizce arayüz v1.5 (DK-2026-032) |
| URS-SİS-06 | GK | FRS-70 | tests/test_denetim.py | OQ-37 | Geçti |
| URS-SİS-07 | GK | FRS-71 | – | IQ-18, sızma testi raporu | Geçti |

Özet: 78 gereksinim; 41 GK (tamamı OQ/IQ ile doğrulandı), 2 D sınıfı gereksinim
değişiklik kontrolüyle v1.5'e ertelendi, 6 gereksinim PQ sonucu bekliyor.
