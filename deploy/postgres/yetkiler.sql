-- EBM SmartClinical – veritabanı yetkileri
-- İlk kurulumda docker-entrypoint tarafından çalıştırılır (APP_DB_PASSWORD ortam değişkeni).
-- Elle kurulumda: psql -U postgres -d smartclinical -v app_parola='...' -f yetkiler.sql
--
-- İlke: Uygulama kullanıcısı (smartclinical) denetim izi tablosunda yalnızca INSERT ve SELECT
-- yapabilir. UPDATE/DELETE veritabanı seviyesinde engellenir (21 CFR Part 11 §11.10(e),
-- EU GMP Annex 11 madde 9). Tablo şeması uygulama tarafından (SQLAlchemy) oluşturulduğu için
-- tablo yoksa tetikleyici kurulumunu ikinci blok şema oluştuktan sonra tekrar çalıştırır.

\set ON_ERROR_STOP on

-- Uygulama rolü. Parola APP_DB_PASSWORD ortam değişkeninden (docker) ya da -v app_parola=... ile gelir.
\getenv app_parola APP_DB_PASSWORD
\if :{?app_parola}
\else
\echo 'UYARI: app_parola tanimsiz, gecici parola kullaniliyor; ALTER ROLE ile degistirin'
\set app_parola 'gecici-parola-degistir'
\endif

SELECT format('CREATE ROLE smartclinical LOGIN PASSWORD %L', :'app_parola')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smartclinical') \gexec

GRANT CONNECT ON DATABASE smartclinical TO smartclinical;
GRANT USAGE, CREATE ON SCHEMA public TO smartclinical;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO smartclinical;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO smartclinical;

-- Salt okunur raporlama / denetçi rolü (BI aracı, dış denetim)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smartclinical_okuyucu') THEN
        CREATE ROLE smartclinical_okuyucu NOLOGIN;
    END IF;
END $$;
GRANT CONNECT ON DATABASE smartclinical TO smartclinical_okuyucu;
GRANT USAGE ON SCHEMA public TO smartclinical_okuyucu;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO smartclinical_okuyucu;

-- ---------------------------------------------------------------------------
-- Denetim izi koruması. Uygulama tabloları oluşturduktan sonra çalıştırılır:
--   psql -U smartclinical_admin -d smartclinical -f yetkiler.sql  (ikinci kez)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION denetim_kaydi_degistirilemez() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'denetim_kaydi tablosunda % islemi yasaktir (kayit id=%)', TG_OP,
        CASE WHEN TG_OP = 'DELETE' THEN OLD.id ELSE NEW.id END
        USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF to_regclass('public.denetim_kaydi') IS NOT NULL THEN
        REVOKE UPDATE, DELETE, TRUNCATE ON denetim_kaydi FROM smartclinical;
        GRANT SELECT, INSERT ON denetim_kaydi TO smartclinical;

        DROP TRIGGER IF EXISTS denetim_kaydi_koru ON denetim_kaydi;
        CREATE TRIGGER denetim_kaydi_koru
            BEFORE UPDATE OR DELETE ON denetim_kaydi
            FOR EACH ROW EXECUTE FUNCTION denetim_kaydi_degistirilemez();

        -- Aynı koruma elektronik imzalar için
        REVOKE UPDATE, DELETE, TRUNCATE ON e_imza FROM smartclinical;
        GRANT SELECT, INSERT ON e_imza TO smartclinical;
        DROP TRIGGER IF EXISTS e_imza_koru ON e_imza;
        CREATE TRIGGER e_imza_koru
            BEFORE UPDATE OR DELETE ON e_imza
            FOR EACH ROW EXECUTE FUNCTION denetim_kaydi_degistirilemez();

        RAISE NOTICE 'denetim_kaydi ve e_imza korumasi kuruldu';
    ELSE
        RAISE NOTICE 'denetim_kaydi tablosu henuz yok; uygulama ilk calistiktan sonra bu dosyayi tekrar calistirin';
    END IF;
END $$;
