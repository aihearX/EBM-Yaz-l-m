import time
from collections import defaultdict
from types import SimpleNamespace

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Kullanici, Merkez, Rol
from ..models._ortak import simdi
from ..services import denetim, yetki
from ..services import kurulum as kurulum_svc
from ._ortak import ip
from .sablon import goster

router = APIRouter()

# IP basina hatali giris sinirlama: bellek ici, tek surec. Basarili giris sayaci temizler.
IP_PENCERE_SN = 15 * 60
IP_SINIR = 20
_ip_denemeleri: dict[str, list[float]] = defaultdict(list)


def _ip_asildi(adres: str | None) -> bool:
    if not adres:
        return False
    simdi_sn = time.monotonic()
    liste = [t for t in _ip_denemeleri[adres] if simdi_sn - t < IP_PENCERE_SN]
    _ip_denemeleri[adres] = liste
    return len(liste) >= IP_SINIR


def _ip_hata(adres: str | None) -> None:
    if adres:
        _ip_denemeleri[adres].append(time.monotonic())


def _giris_sayfasi(request: Request, sonraki: str, hata: str | None, kod: int = 200):
    yanit = goster(request, "giris.html", sonraki=sonraki, hata=hata, kilit_dk=yetki.KILIT_DAKIKA)
    yanit.status_code = kod
    return yanit


@router.get("/giris")
def giris_formu(request: Request, sonraki: str = "/", db: Session = Depends(get_db)):
    if kurulum_svc.kullanici_sayisi_sifir(db):
        return RedirectResponse("/kurulum", status_code=303)
    kid = request.session.get("kid")
    if kid:
        k = db.get(Kullanici, kid)
        if k and k.aktif and yetki.parola_degisimi_gerekli(k):
            return RedirectResponse("/hesap/parola", status_code=303)
        return RedirectResponse("/", status_code=303)
    return _giris_sayfasi(request, sonraki, None)


@router.post("/giris")
def giris(request: Request, kullanici_adi: str = Form(...), parola: str = Form(...),
          sonraki: str = Form("/"), db: Session = Depends(get_db)):
    adres = ip(request)
    if _ip_asildi(adres):
        denetim.kaydet(db, None, "giris_engellendi", "kullanici", yeni={"kullanici_adi": kullanici_adi, "neden": "ip_siniri"}, ip=adres)
        db.commit()
        return _giris_sayfasi(request, sonraki, "Bu adresten çok sayıda hatalı deneme yapıldı. 15 dakika sonra yeniden deneyin.", 429)
    k = yetki.giris_yap(db, kullanici_adi.strip(), parola, ip=adres)
    if not k:
        _ip_hata(adres)
        denetim.kaydet(db, None, "giris_basarisiz", "kullanici", yeni={"kullanici_adi": kullanici_adi}, ip=adres)
        db.commit()
        return _giris_sayfasi(request, sonraki, f"Kullanıcı adı veya parola hatalı. {yetki.MAKS_HATALI_GIRIS} hatalı "
                              f"denemeden sonra hesap {yetki.KILIT_DAKIKA} dakika kilitlenir.")
    _ip_denemeleri.pop(adres, None)
    request.session["kid"] = k.id
    denetim.kaydet(db, k, "giris", "kullanici", k.id, ip=adres)
    db.commit()
    if not sonraki.startswith("/") or sonraki.startswith("//"):
        sonraki = "/"
    if yetki.parola_degisimi_gerekli(k):
        request.session["mesaj"] = ("İlk girişte parolanızı değiştirmeniz gerekir." if k.ilk_giris_degisim
                                    else f"Parolanızın süresi doldu; {yetki.parola_gun()} günde bir yenilenmesi gerekir.")
        return RedirectResponse("/hesap/parola", status_code=303)
    return RedirectResponse(sonraki, status_code=303)


@router.get("/cikis")
def cikis(request: Request, db: Session = Depends(get_db)):
    kid = request.session.get("kid")
    if kid:
        k = db.get(Kullanici, kid)
        denetim.kaydet(db, k, "cikis", "kullanici", kid, ip=ip(request))
        db.commit()
    request.session.clear()
    return RedirectResponse("/giris", status_code=303)


# --- Ilk kurulum ------------------------------------------------------------
# Hic kullanici yokken tek sayfada mod secimi, kurum ve yonetici hesabi. Kullanici varsa 404.

def _kurulum_kontrol(db: Session) -> None:
    if not kurulum_svc.kullanici_sayisi_sifir(db):
        raise HTTPException(404, "Kurulum tamamlanmış")


@router.get("/kurulum")
def kurulum_formu(request: Request, db: Session = Depends(get_db)):
    _kurulum_kontrol(db)
    return goster(request, "kurulum.html", modlar=kurulum_svc.MODLAR, hata=None, veri={})


@router.post("/kurulum")
def kurulum_yap(request: Request, db: Session = Depends(get_db),
                mod: str = Form("tekil"), kurum_adi: str = Form(...), kullanici_adi: str = Form(...),
                ad_soyad: str = Form(...), eposta: str = Form(...), parola: str = Form(...),
                merkez_adi: str = Form(""), merkez_sehir: str = Form("")):
    _kurulum_kontrol(db)
    veri = {"mod": mod, "kurum_adi": kurum_adi, "kullanici_adi": kullanici_adi, "ad_soyad": ad_soyad,
            "eposta": eposta, "merkez_adi": merkez_adi, "merkez_sehir": merkez_sehir}

    def hata(metin):
        return goster(request, "kurulum.html", modlar=kurulum_svc.MODLAR, hata=metin, veri=veri)

    if mod not in kurulum_svc.MOD_ETIKET:
        return hata("Kullanım modu seçin.")
    if not kurum_adi.strip():
        return hata("Kurum adı boş olamaz.")
    h = yetki.parola_politikasi(parola)
    if h:
        return hata(h)
    merkez = None
    if mod in ("tekil", "universite"):
        ad = merkez_adi.strip() or kurum_adi.strip()
        if not merkez_sehir.strip():
            return hata("Merkez (hastane) şehri boş olamaz.")
        merkez = Merkez(kod=kurulum_svc.kurum_kisaltmasi(ad)[:12] + "-01", ad=ad[:200], sehir=merkez_sehir.strip()[:60],
                        kurum_tipi="universite" if mod == "universite" else "egitim_arastirma")
        db.add(merkez)
        db.flush()
    yonetici = Kullanici(kullanici_adi=kullanici_adi.strip().lower(), ad_soyad=ad_soyad.strip(), eposta=eposta.strip(),
                         parola_hash=yetki.parola_hashle(parola), rol=Rol.YONETICI, parola_degisim=simdi(),
                         merkez_id=merkez.id if (merkez and mod == "tekil") else None,
                         kurum=kurum_adi.strip() if mod == "cro" else None, ilk_giris_degisim=False)
    db.add(yonetici)
    db.flush()
    ayar = kurulum_svc.ayar_yaz(db, mod, kurum_adi, merkez.id if merkez else None,
                                kurum_adi if mod == "cro" else None)
    sistem = SimpleNamespace(id=None, kullanici_adi="sistem")  # denetim izinde islem sahibi
    if merkez:
        denetim.kaydet(db, sistem, "olustur", "merkez", merkez.id, yeni=denetim.varlik_sozluk(merkez), ip=ip(request))
    denetim.kaydet(db, sistem, "olustur", "kullanici", yonetici.id, yeni=denetim.varlik_sozluk(yonetici), ip=ip(request))
    denetim.kaydet(db, sistem, "kurulum", "kurulum_ayari", ayar.id, yeni=denetim.varlik_sozluk(ayar), ip=ip(request))
    db.commit()
    request.session["kid"] = yonetici.id
    request.session["mesaj"] = "Kurulum tamamlandı. İlk çalışmanızı sihirbazla oluşturabilirsiniz."
    return RedirectResponse("/", status_code=303)
