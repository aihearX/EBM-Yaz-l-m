-- EBM SmartClinical – veritabanı rolleri ve yetkileri
--
-- İlke: iki ayrı rol.
--   smartclinical_sema : şema sahibi; tabloları oluşturur (docker "sema" servisi / güncelleme adımı). Uygulama bu rolle çalışmaz.
--   smartclinical      : uygulama rolü; yalnızca DML (SELECT/INSERT/UPDATE/DELETE). DDL yetkisi yoktur.
-- Denetim izi (denetim_kaydi) ve elektronik imza (e_imza) tablolarında uygulama rolü yalnızca INSERT ve SELECT yapabilir;
-- UPDATE/DELETE veritabanı seviyesinde engellenir (21 CFR Part 11 §11.10(e), EU GMP Annex 11 madde 9).
--
-- Çalıştırma sırası:
--   1) İlk kurulumda docker-entrypoint (roller; tablo yok, ikinci blok "henüz yok" der)
--   2) Şema oluşturulduktan sonra (docker "yetki" servisi ya da elle): tablo yetkileri + tetikleyiciler
-- Elle: psql -U smartclinical_admin -d smartclinical -v app_parola='...' -v sema_parola='...' -f yetkiler.sql

\set ON_ERROR_STOP on

\getenv app_parola APP_DB_PASSWORD
\if :{?app_parola}
\else
\echo 'UYARI: app_parola tanimsiz, gecici parola kullaniliyor; ALTER ROLE ile degistirin'
\set app_parola 'gecici-parola-degistir'
\endif
\getenv sema_parola SEMA_DB_PASSWORD
\if :{?sema_parola}
\else
\echo 'UYARI: sema_parola tanimsiz, gecici parola kullaniliyor; ALTER ROLE ile degistirin'
\set sema_parola 'gecici-sema-parola-degistir'
\endif

SELECT format('CREATE ROLE smartclinical_sema LOGIN PASSWORD %L', :'sema_parola')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smartclinical_sema') \gexec
SELECT format('CREATE ROLE smartclinical LOGIN PASSWORD %L', :'app_parola')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smartclinical') \gexec

GRANT CONNECT ON DATABASE smartclinical TO smartclinical_sema, smartclinical;
GRANT USAGE, CREATE ON SCHEMA public TO smartclinical_sema;
GRANT USAGE ON SCHEMA public TO smartclinical;
REVOKE CREATE ON SCHEMA public FROM smartclinical;

-- Şema sahibinin ileride oluşturacağı tablolar için uygulama rolüne otomatik DML
ALTER DEFAULT PRIVILEGES FOR ROLE smartclinical_sema IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO smartclinical;
ALTER DEFAULT PRIVILEGES FOR ROLE smartclinical_sema IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO smartclinical;

-- Salt okunur raporlama / denetçi rolü (BI aracı, dış denetim)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smartclinical_okuyucu') THEN
        CREATE ROLE smartclinical_okuyucu NOLOGIN;
    END IF;
END $$;
GRANT CONNECT ON DATABASE smartclinical TO smartclinical_okuyucu;
GRANT USAGE ON SCHEMA public TO smartclinical_okuyucu;
ALTER DEFAULT PRIVILEGES FOR ROLE smartclinical_sema IN SCHEMA public GRANT SELECT ON TABLES TO smartclinical_okuyucu;

-- ---------------------------------------------------------------------------
-- Tablo yetkileri ve denetim izi koruması. Şema oluşturulduktan sonra çalışır (docker: "yetki" servisi).
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
        -- mevcut tablolarda DML (yeni tablolar için default privileges yeterli)
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO smartclinical;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO smartclinical;
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO smartclinical_okuyucu;

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

        -- denetim_zincir tek satırlık zincir ucu; uygulama günceller, silemez
        REVOKE DELETE, TRUNCATE ON denetim_zincir FROM smartclinical;

        RAISE NOTICE 'denetim_kaydi ve e_imza korumasi kuruldu';
    ELSE
        RAISE NOTICE 'denetim_kaydi tablosu henuz yok; sema olusturulduktan sonra bu dosyayi tekrar calistirin';
    END IF;
END $$;
