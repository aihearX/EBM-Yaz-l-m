"""Protokol-hasta eslestirme motoru.

Akis (her kriter icin):
  1. Kriter.yapisal varsa kural degerlendirici (services/kriter) ile yapisal veride bak.
  2. Belirsizse ya da guven dusukse hasta metinleri (epikriz, patoloji, radyoloji) uzerinden
     RAG + BDM ile kanit cumlesi ara.
  3. Haric kriter saglandiysa hasta uygun degil; dahil kriterlerin tamami saglandiysa uygun;
     belirsiz orani yuksekse 'belirsiz' (arastirmaci incelemesine duser).

Her sonuc kaynak cumleyle gerekcelendirilir; arastirmaci ekranda kanitini gorur ve onaylar/reddeder.
"""

import logging
import time
from dataclasses import asdict, dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import Calisma, CalismaMerkez, EslestirmeSonucu, Hasta, Kriter
from ...models._ortak import simdi
from ..bdm import SURUM as BDM_SURUM
from ..bdm import BDMIstemci
from ..bdm.rag import Parcalayici
from ..kriter import degerlendir, yapilandir
from ..kriter.degerlendirici import Degerlendirme

log = logging.getLogger(__name__)

# Karar esikleri. Pilot (golge mod) sonuclarina gore ayarlanacak; su an muhafazakar.
UYGUN_ESIK = 0.85           # skor >= -> uygun
OLASI_ESIK = 0.55           # skor >= -> olasi
BELIRSIZ_ORAN_ESIGI = 0.5   # dahil kriterlerin yarisindan fazlasi belirsizse karar 'belirsiz'
YAPISAL_TEYIT_GUVENI = 0.7  # yapisal sonuc bu guvenin altindaysa metinle teyit denenir
HARIC_IHLAL_SKORU = 0.05


@dataclass
class EslestirmeCiktisi:
    skor: float
    karar: str
    kriter_sonuclari: list[dict]
    belirsiz_sayisi: int
    model_surumu: str
    sure_ms: int
    aciklama: str = ""
    kanit_parcalari: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("kanit_parcalari", None)
        return d


def _hasta_parcalari(hasta) -> list[str]:
    metinler = getattr(hasta, "metinler", None) or (hasta.get("metinler") if isinstance(hasta, dict) else None) or []
    p = Parcalayici()
    out = []
    for m in metinler:
        metin = m.get("metin") if isinstance(m, dict) else str(m)
        if metin:
            out.extend(p.parcala(metin))
    return out


def _tani_onekleri(calisma: Calisma) -> tuple[str, ...]:
    onekler: set[str] = set()
    for k in calisma.kriterler:
        if k.tip != "dahil":
            continue
        y = k.yapisal or {}
        if isinstance(y, dict) and "sorgu" in y:
            y = y["sorgu"]
        yigin = [y]
        while yigin:
            s = yigin.pop()
            if not isinstance(s, dict):
                continue
            if s.get("alan") == "tani":
                onekler.update(str(x).upper() for x in s.get("icd10", []))
            for alt in ("ve", "veya"):
                yigin.extend(s.get(alt, []))
    return tuple(sorted(onekler))


class Eslestirici:
    def __init__(self, bdm: BDMIstemci | None = None):
        self.bdm = bdm or BDMIstemci.olustur()

    @property
    def model_surumu(self) -> str:
        return f"{BDM_SURUM}; model={self.bdm.model_adi}; kriter=kural-1.2"

    # -- tek kriter ---------------------------------------------------------

    def _kriter_degerlendir(self, kriter: Kriter, hasta, parcalar: list[str]) -> dict:
        yapisal = kriter.yapisal
        if isinstance(yapisal, dict) and "sorgu" in yapisal:  # KriterYapisi.to_dict() ile kaydedilmis
            yapisal = yapisal["sorgu"]
        if not yapisal:
            yapisal = yapilandir(kriter.metin, kriter.tip).sorgu
        d = degerlendir(yapisal, hasta)
        if d.sonuc == "belirsiz":
            # ic aciklamalar ("... yapisal olarak degerlendirilemiyor") kullaniciya kanit olarak gosterilmez
            d = Degerlendirme("belirsiz", None, d.guven, d.kullanilan_veri)
        sonuc = {"kriter_id": kriter.id, "tip": kriter.tip, "metin": kriter.metin, "sonuc": d.sonuc,
                 "kanit": d.kanit, "guven": round(d.guven, 3), "yontem": "yapisal"}
        if d.sonuc != "belirsiz" and d.guven >= YAPISAL_TEYIT_GUVENI:
            return sonuc
        if not parcalar:
            return sonuc
        # yapisal veri yetersiz -> metin kaniti
        k = self.bdm.kanit_cikar(kriter.metin, parcalar, sorgu=yapisal)
        if k.sonuc == "belirsiz":
            if d.sonuc != "belirsiz":
                return sonuc  # dusuk guvenli yapisal sonucu koru
            sonuc.update({"kanit": k.kanit_cumlesi or d.kanit, "guven": round(max(d.guven, k.guven), 3),
                          "yontem": k.yontem})
            return sonuc
        if d.sonuc != "belirsiz" and d.sonuc != k.sonuc:
            # yapisal ile metin celisiyor: arastirmaciya birak
            sonuc.update({"sonuc": "belirsiz", "kanit": f"yapısal: {d.kanit} | metin: {k.kanit_cumlesi}",
                          "guven": 0.3, "yontem": "celiskili"})
            return sonuc
        guven = k.guven if d.sonuc == "belirsiz" else round(min(0.98, (d.guven + k.guven) / 2 + 0.15), 3)
        sonuc.update({"sonuc": k.sonuc, "kanit": k.kanit_cumlesi, "guven": guven, "yontem": k.yontem})
        return sonuc

    # -- hasta -------------------------------------------------------------

    def hasta_degerlendir(self, calisma: Calisma, hasta) -> EslestirmeCiktisi:
        t0 = time.monotonic()
        parcalar = _hasta_parcalari(hasta)
        sonuclar = [self._kriter_degerlendir(k, hasta, parcalar) for k in calisma.kriterler]
        dahil = [s for s in sonuclar if s["tip"] == "dahil"]
        haric = [s for s in sonuclar if s["tip"] == "haric"]
        belirsiz = sum(1 for s in sonuclar if s["sonuc"] == "belirsiz")

        haric_ihlal = [s for s in haric if s["sonuc"] == "saglandi"]
        dahil_eksik = [s for s in dahil if s["sonuc"] == "saglanmadi"]
        dahil_ok = [s for s in dahil if s["sonuc"] == "saglandi"]

        if haric_ihlal:
            skor = HARIC_IHLAL_SKORU
            karar = "uygun_degil"
            aciklama = f"Hariç tutma kriteri sağlandı: {haric_ihlal[0]['metin'][:80]}"
        elif dahil_eksik:
            skor = round(max(0.0, 0.4 * len(dahil_ok) / max(1, len(dahil)) - 0.1 * len(dahil_eksik)), 3)
            karar = "uygun_degil"
            aciklama = f"Dahil etme kriteri sağlanmadı: {dahil_eksik[0]['metin'][:80]}"
        else:
            toplam = len(dahil) + len(haric)
            # dahil: saglandi tam puan; haric: saglanmadi tam puan; belirsiz yarim puan * guven
            puan = len(dahil_ok) + sum(1 for s in haric if s["sonuc"] == "saglanmadi")
            puan += sum(0.5 * max(0.3, s["guven"]) for s in sonuclar if s["sonuc"] == "belirsiz")
            skor = round(puan / toplam, 3) if toplam else 0.0
            belirsiz_oran = belirsiz / toplam if toplam else 1.0
            if belirsiz_oran > BELIRSIZ_ORAN_ESIGI:
                karar, aciklama = "belirsiz", f"{belirsiz}/{toplam} kriter değerlendirilemedi; araştırmacı incelemesi gerekli"
            elif skor >= UYGUN_ESIK and belirsiz == 0:
                karar, aciklama = "uygun", "Tüm dahil etme kriterleri sağlandı, hariç tutma kriteri saptanmadı"
            elif skor >= OLASI_ESIK:
                karar = "olasi"
                aciklama = f"{len(dahil_ok)}/{len(dahil)} dahil kriteri sağlandı; {belirsiz} kriter teyit bekliyor"
            else:
                karar, aciklama = "belirsiz", "Yeterli kanıt yok"

        return EslestirmeCiktisi(skor=skor, karar=karar, kriter_sonuclari=sonuclar, belirsiz_sayisi=belirsiz,
                                 model_surumu=self.model_surumu, sure_ms=int((time.monotonic() - t0) * 1000),
                                 aciklama=aciklama, kanit_parcalari=parcalar)

    def toplu(self, calisma: Calisma, hastalar) -> list[EslestirmeCiktisi]:
        return [self.hasta_degerlendir(calisma, h) for h in hastalar]

    # -- kalicilik ----------------------------------------------------------

    def kaydet(self, db: Session, calisma: Calisma, hasta: Hasta, cikti: EslestirmeCiktisi,
               golge_mod: bool = False) -> EslestirmeSonucu:
        mevcut = db.scalar(select(EslestirmeSonucu).where(EslestirmeSonucu.calisma_id == calisma.id,
                                                          EslestirmeSonucu.hasta_id == hasta.id))
        if mevcut is None:
            mevcut = EslestirmeSonucu(calisma_id=calisma.id, hasta_id=hasta.id, kriter_sonuclari=[], skor=0.0, karar="belirsiz",
                                      model_surumu=self.model_surumu)
            db.add(mevcut)
        elif mevcut.inceleme_karari and mevcut.karar == cikti.karar:
            # arastirmaci karar vermis, model karari degismemis: incelemeyi koru
            pass
        else:
            mevcut.inceleyen_id = None
            mevcut.inceleme_karari = None
            mevcut.inceleme_notu = None
            mevcut.inceleme_zamani = None
        mevcut.skor = cikti.skor
        mevcut.karar = cikti.karar
        mevcut.kriter_sonuclari = cikti.kriter_sonuclari
        mevcut.belirsiz_sayisi = cikti.belirsiz_sayisi
        mevcut.model_surumu = cikti.model_surumu
        mevcut.sure_ms = cikti.sure_ms
        mevcut.olusturma = simdi()
        mevcut.golge_mod = golge_mod
        db.flush()
        return mevcut

    def calisma_icin_tara(self, db: Session, calisma: Calisma, merkez_id: int | None = None,
                          limit: int = 500, golge_mod: bool = False) -> list[EslestirmeSonucu]:
        if merkez_id is not None:
            merkez_idler = [merkez_id]
        else:
            merkez_idler = [cm.merkez_id for cm in db.scalars(
                select(CalismaMerkez).where(CalismaMerkez.calisma_id == calisma.id))]
        if not merkez_idler:
            log.info("calisma %s icin merkez yok, tarama atlandi", calisma.kod)
            return []
        hastalar = db.scalars(select(Hasta).where(Hasta.merkez_id.in_(merkez_idler)).limit(limit)).all()
        # On filtre: dahil etme kriterlerinde ICD-10 on eki varsa (ör. C50) sadece o taniya sahip hastalar
        # taranir. HBYS havuzundaki alakasiz kayitlari BDM'ye gondermek hem yavas hem gereksiz.
        onekler = _tani_onekleri(calisma)
        if onekler:
            hastalar = [h for h in hastalar if any(str(t.get("icd10", "")).upper().startswith(onekler)
                                                   for t in (h.tanilar or []) if isinstance(t, dict))]
            log.info("calisma %s: ICD on filtresi %s -> %d hasta", calisma.kod, onekler, len(hastalar))
        sonuclar = []
        for h in hastalar:
            cikti = self.hasta_degerlendir(calisma, h)
            sonuclar.append(self.kaydet(db, calisma, h, cikti, golge_mod=golge_mod))
        db.commit()
        log.info("calisma %s: %d hasta tarandi, %d uygun/olasi", calisma.kod, len(sonuclar),
                 sum(1 for s in sonuclar if s.karar in ("uygun", "olasi")))
        return sonuclar


def golge_mod_karsilastir(sonuclar, manuel: dict[int, bool]) -> dict:
    """Platform onerilerini manuel on tarama kararlariyla karsilastirir (pilot dogrulama, IP5).

    Pozitif = platform 'uygun' veya 'olasi' dedi. 'belirsiz' arastirmaciya gittigi icin pozitif sayilir
    (duyarlilik oncelikli; kacirilan hasta, fazladan incelenen hastadan pahali).
    """
    tp = fp = tn = fn = 0
    for s in sonuclar:
        hid = s.hasta_id if hasattr(s, "hasta_id") else s["hasta_id"]
        karar = s.karar if hasattr(s, "karar") else s["karar"]
        if hid not in manuel:
            continue
        tahmin = karar in ("uygun", "olasi", "belirsiz")
        gercek = bool(manuel[hid])
        if tahmin and gercek:
            tp += 1
        elif tahmin and not gercek:
            fp += 1
        elif not tahmin and gercek:
            fn += 1
        else:
            tn += 1
    n = tp + fp + tn + fn

    def oran(a, b):
        return round(a / b, 3) if b else None

    return {"n": n, "duyarlilik": oran(tp, tp + fn), "ozgulluk": oran(tn, tn + fp), "ppv": oran(tp, tp + fp),
            "npv": oran(tn, tn + fn), "karisiklik": {"tp": tp, "fp": fp, "tn": tn, "fn": fn}}
