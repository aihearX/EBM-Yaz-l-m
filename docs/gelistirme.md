# Geliştirme Kuralları

- Python 3.11+. Kod ve tanımlayıcılar Türkçe (ASCII), standart terimler (FHIR, LOINC, CDASH, ODM)
  olduğu gibi. Kullanıcıya görünen metinler Türkçe karakterli.
- Her davranış değişikliği için test (`tests/`). Değişiklik öncesi `python -m pytest -q` ve
  `ruff check smartclinical ml tests --select E,F,W,I --ignore E501` temiz olmalı.
- Servisler `commit` etmez; web/API katmanı eder. Uzun süren toplu işler ve betikler istisna (yorumla belirt).
- Denetim izine yazılmayan hiçbir veri değişikliği kabul edilmez (`services/denetim.kaydet`; eski/yeni değer
  ve gerekçe). Denetim izi özeti HMAC'dir; `SC_SECRET_KEY` olmadan `zinciri_dogrula` çalışmaz.
- Hasta verisi içeren hiçbir şey loglanmaz ya da denetim kaydına ham olarak yazılmaz. Log satırlarında
  `kayit_no` bile yazılmaz; sadece sayılar.
- Veritabanı şema değişiklikleri: geliştirmede `create_all`; üretimde yeni tablolar `sema` adımıyla, sütun
  eklemeleri sürüm notlarındaki SQL ile uygulanır (deploy/KURULUM.md bölüm 9). Otomatik migrasyon yoktur.
- Paylaşılan dosyalar (`web/__init__.py`, `models/__init__.py`, `base.html`, `demo_veri.py`) küçük ve eklemeli
  değiştirilir; yeni modül kendi dosyasında yazılır ve router olarak kaydedilir.
- Belgeler (`docs/validasyon/*`, `docs/api.md`, `deploy/KURULUM.md`) koddaki rota, betik ve test adlarına
  işaret eder; `tests/test_P3.py::test_izlenebilirlik_matrisi_kodla_eslesir` olmayan referansı ve sürüm/tarih
  damgasını yakalar. Belgelere sürüm numarası, tarih ve araç referansı yazılmaz.
- Yapay zekâ bileşenlerinde değişiklik: `ml/degerlendirme/degerlendir.py` ile altın standart üzerinde referans
  metrikler alınır ve değişiklik açıklamasına eklenir.
