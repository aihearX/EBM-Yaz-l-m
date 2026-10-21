# Geliştirme Kuralları

- Python 3.11+. Kod ve tanımlayıcılar Türkçe (ASCII), standart terimler (FHIR, LOINC, CDASH)
  olduğu gibi. Kullanıcıya görünen metinler Türkçe karakterli.
- Her davranış değişikliği için test (`tests/`). PR öncesi `make test` ve `make lint` temiz olmalı.
- Servisler `commit` etmez; web/API katmanı eder. Uzun süren toplu işler istisna (yorumla belirt).
- Denetim izine yazılmayan hiçbir veri değişikliği kabul edilmez (`services/denetim.kaydet`).
- Hasta verisi içeren hiçbir şey loglanmaz. Log satırlarında `kayit_no` bile yazılmaz; sadece sayılar.
- Veritabanı şema değişiklikleri: geliştirmede `create_all`, üretimde Alembic migrasyonu
  (`alembic/` dizini 1.5 ile repoya girecek; şimdilik migrasyonlar `deploy/KURULUM.md`'deki SQL ile).
- Sürüm numarası `smartclinical/__init__.py` ve `pyproject.toml` içinde birlikte artırılır,
  `CHANGELOG.md` güncellenir.
- Yapay zekâ bileşenlerinde değişiklik: `ml/degerlendirme/degerlendir.py` ile altın standart
  üzerinde referans metrikler alınır ve PR açıklamasına eklenir.
