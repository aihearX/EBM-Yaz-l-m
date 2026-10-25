"""Turkce Klinik BDM istemcisi.

Gorev bazli arayuz: kriter yapilandirma, kanit cikarma, ozet, soru-cevap. Her gorev once modeli
dener; model yoksa / hata verirse / ciktisi dogrulanamazsa kural tabanli yola duser. Boylece
platform modelsiz de calisir, model sadece kapsama ve dogrulugu artirir.
"""

import logging
import re
from dataclasses import dataclass, field

from ...config import ayarlar as _ayarlar
from ..kriter import KriterYapisi
from ..kriter import sozluk as S
from ..kriter import yapilandir as _kural_yapilandir
from . import istemler, korumalar, metin_kurallari
from .rag import HibritArama, cumlelere_bol
from .saglayicilar import BDMErisimHatasi, KuralTabanliSaglayici, Saglayici, saglayici_olustur

log = logging.getLogger(__name__)

SURUM = "ebm-klinik-tr/istemci-1.3"

# Protokol taslagi: uzun metinlerde yalnizca bu basliklarin cevresi modele gider
PROTOKOL_METIN_SINIRI = 12000
PROTOKOL_BASLIKLARI = ("dahil etme", "dahil olma", "hariç tutma", "haric tutma", "dışlama", "dislama",
                       "çalışma kolları", "calisma kollari", "tedavi grupları", "tedavi gruplari",
                       "vizit takvimi", "değerlendirme çizelgesi", "degerlendirme cizelgesi", "vizit çizelgesi")


def _baslik_cevresi(metin: str, basliklar, genislik: int = 2500) -> str:
    """Basliklarin gectigi yerlerin cevresindeki bolumleri birlestirir (ortusen pencereler tek parca)."""
    kucuk = metin.translate(str.maketrans("İI", "iı")).lower()
    pencereler: list[tuple[int, int]] = []
    for b in basliklar:
        bas = 0
        while True:
            i = kucuk.find(b, bas)
            if i < 0:
                break
            pencereler.append((max(0, i - 200), min(len(metin), i + genislik)))
            bas = i + len(b)
    if not pencereler:
        return metin[:PROTOKOL_METIN_SINIRI]
    pencereler.sort()
    birlesik = [pencereler[0]]
    for a, b in pencereler[1:]:
        if a <= birlesik[-1][1]:
            birlesik[-1] = (birlesik[-1][0], max(b, birlesik[-1][1]))
        else:
            birlesik.append((a, b))
    return "\n...\n".join(metin[a:b] for a, b in birlesik)


@dataclass
class KanitSonucu:
    sonuc: str                      # saglandi | saglanmadi | belirsiz
    kanit_cumlesi: str | None
    guven: float
    parca_indeks: int | None
    yontem: str = "bdm"             # bdm | kural
    notlar: list[str] = field(default_factory=list)


# Kural tabanli kanit aramasinda kullanilan olumsuzlama kaliplari (cumle icinde)
_OLUMSUZ = re.compile(r"\b(yok|yoktur|saptanmadı|saptanmadi|izlenmedi|görülmedi|gorulmedi|bulunmadı|bulunmadi|negatif|"
                      r"olmadı|olmadi|değil|degil|mevcut değil|mevcut degil|tespit edilmedi|gözlenmedi|gozlenmedi|"
                      r"almamış|almamis|kullanmıyor|kullanmiyor|geçirmemiş|gecirmemis|ekarte|dışlandı|dislandi|"
                      r"no |not |denies|negative for|without|absent)\b")


# "kanser" klinik metinde cogu zaman baska sozcukle gecer
_ESANLAM = {"kanser": ("karsinom", "malign", "tumor", "tümör", "neoplazm", "ca", "adenokarsinom"),
            "enfarktus": ("mi", "stemi", "nstemi", "infarkt", "enfarkt", "infarktus"), "enfarktusu": ("mi", "stemi", "nstemi", "infarkt"),
            "miyokard": ("mi", "stemi", "nstemi"), "yetmezlik": ("yetersizlik",), "stabil": ("kararli",),
            "kararsiz": ("unstabil", "anstabil", "unstable"), "angina": ("anjina",), "metastaz": ("metastatik", "met"),
            "gebe": ("hamile",), "kemoterapi": ("kt", "kemoterapisi"), "radyoterapi": ("rt",)}


def _terim_cumlede(terim: str, cumle: str) -> bool:
    """Terimin anlamli parcalari cumlede (on ek esleme ile) geciyor mu? 'meme kanseri' ~ 'meme ... karsinom'.

    Kisa/sayisal parcalar ("tip", "2") zorunlu degil; uzun parcalarin en az yarisi eslesmeli.
    """
    ct = [S.sade(k) for k in re.findall(r"[a-zçğıöşü0-9]+", S.normalize(cumle))]
    parcalar = [S.sade(x) for x in re.findall(r"[a-zçğıöşü0-9]+", S.normalize(terim))]
    onemli = [x for x in parcalar if len(x) >= 3 and not x.isdigit()]
    # "tip 1 diyabet" terimi "tip 2 diyabet" cumlesiyle eslesmesin; ama "diyabet oykusu yok" ile eslesebilsin
    for i, x in enumerate(parcalar):
        if x.isdigit() and i > 0 and x not in ct:
            onceki = parcalar[i - 1]
            for j, k in enumerate(ct[:-1]):
                if k == onceki and ct[j + 1].isdigit() and ct[j + 1] != x:
                    return False
    if not onemli:
        return any(x in ct for x in parcalar)
    eslesen = 0
    for x in onemli:
        adaylar = (x,) + tuple(S.sade(e) for e in _ESANLAM.get(x, ()))
        kok = x[:5] if len(x) >= 6 else x[:4]
        if any(t == a or (len(a) >= 4 and len(t) >= 4 and (t.startswith(a) or a.startswith(t))) for t in ct for a in adaylar) \
                or any(t.startswith(kok) for t in ct):
            eslesen += 1
    return eslesen / len(onemli) >= 0.5 and (eslesen == len(onemli) or any(len(x) >= 5 for x in onemli))


def _olumsuz_mu(cumle: str, terimler: list[str]) -> bool:
    """Cumlede olumsuzlama var mi? Kriterin kendi sozcukleri ('HER2-negatif') olumsuzlama sayilmaz.

    Olumsuzlama, terimin gectigi yan cumlede (virgul/noktali virgulle ayrilmis) aranir:
    "Akut koroner sendrom bulgusu yok, kararli angina" cumlesinde angina olumsuzlanmamistir.
    """
    terim_kelimeleri = {S.sade(k) for t in terimler for k in re.findall(r"[a-zçğıöşü0-9]+", S.normalize(t))}
    parcalar = [p for p in re.split(r"[,;]", cumle) if p.strip()]
    ilgili = [p for p in parcalar if any(_terim_cumlede(t, p) for t in terimler if len(t) > 2)] or parcalar
    for p in ilgili:
        kalan = " ".join(k for k in re.findall(r"[a-zçğıöşü0-9]+", S.normalize(p)) if S.sade(k) not in terim_kelimeleri)
        if _OLUMSUZ.search(kalan):
            return True
    return False


class BDMIstemci:
    def __init__(self, saglayici: Saglayici, guven_esigi: float = korumalar.GUVEN_ESIGI,
                 oy_sayisi: int = 1, gomme=None):
        self.saglayici = saglayici
        self.guven_esigi = guven_esigi
        self.oy_sayisi = max(1, oy_sayisi)
        self.gomme = gomme
        self._hazir: bool | None = None

    @classmethod
    def olustur(cls, ayarlar=None) -> "BDMIstemci":
        a = ayarlar or _ayarlar()
        s = saglayici_olustur(a.bdm_saglayici, a.bdm_url, a.bdm_model, a.bdm_zaman_asimi_sn)
        return cls(s)

    # -- durum -------------------------------------------------------------

    @property
    def kural_modu(self) -> bool:
        return isinstance(self.saglayici, KuralTabanliSaglayici)

    @property
    def model_adi(self) -> str:
        return self.saglayici.model if not self.kural_modu else "kural-tabanli-v1"

    def hazir(self) -> bool:
        if self._hazir is None:
            self._hazir = self.saglayici.hazir()
        return self._hazir

    def durum(self) -> dict:
        return {"saglayici": self.saglayici.ad, "model": self.model_adi, "url": self.saglayici.url,
                "hazir": self.hazir(), "surum": SURUM, "guven_esigi": self.guven_esigi}

    # -- dusuk seviye ------------------------------------------------------

    def _uret_json(self, istem: str, sema: dict, maks_token: int = 512, sicaklik: float = 0.0) -> dict | None:
        if self.kural_modu:
            return None
        korumalar.phi_kontrol(istem)
        try:
            u = self.saglayici.uret(istem, sistem=istemler.SISTEM, json_cikti=True,
                                    sicaklik=sicaklik, maks_token=maks_token)
        except BDMErisimHatasi as e:
            log.warning("BDM erisim hatasi, kural tabanliya dusuluyor: %s", e)
            self._hazir = False
            return None
        v = korumalar.json_ayikla(u.metin)
        if not korumalar.sema_dogrula(v, sema):
            log.info("BDM ciktisi semaya uymadi: %.200s", u.metin)
            return None
        return v

    # -- gorevler ----------------------------------------------------------

    def kriter_yapilandir(self, metin: str, tip: str = "dahil") -> KriterYapisi:
        kural = _kural_yapilandir(metin, tip)
        if self.kural_modu:
            return kural
        v = self._uret_json(istemler.KRITER_YAPILANDIR.format(tip=tip, metin=metin.strip()),
                            {"kategori": str, "sorgu": dict, "guven": (int, float)})
        if not v or v["kategori"] not in __import__("smartclinical.services.kriter", fromlist=["KATEGORILER"]).KATEGORILER:
            return kural
        # Model ciktisini kural ayristirici ile capraz kontrol: kategori uyusmuyorsa ve kural guveni yuksekse kural kazanir
        if kural.kategori != "serbest" and kural.kategori != v["kategori"] and kural.guven >= 0.8:
            kural.notlar.append(f"BDM '{v['kategori']}' onerdi, kural ayristirici tercih edildi")
            return kural
        y = KriterYapisi(v["kategori"], v["sorgu"], max(0.0, min(1.0, float(v["guven"]))), yontem="bdm",
                         notlar=[str(n) for n in v.get("notlar", [])][:5], metin=metin, tip=tip)
        if y.kategori == "serbest" and kural.kategori != "serbest":
            return kural
        return y

    def kanit_cikar(self, kriter_metni: str, parcalar: list[str], sorgu: dict | None = None) -> KanitSonucu:
        parcalar = [p for p in (parcalar or []) if p and p.strip()]
        if not parcalar:
            return KanitSonucu("belirsiz", None, 0.0, None, "kural", ["metin yok"])
        if self.kural_modu:
            return self._kural_kanit(kriter_metni, parcalar, sorgu=sorgu)

        istem = istemler.KANIT_CIKAR.format(kriter=kriter_metni.strip(), parcalar=istemler.parcalari_bicimle(parcalar))
        sema = {"sonuc": str, "kanit_cumlesi": str, "guven": (int, float)}
        oylar: list[tuple[str, float]] = []
        kanit, indeks = None, None
        for i in range(self.oy_sayisi):
            v = self._uret_json(istem, sema, maks_token=256, sicaklik=0.0 if self.oy_sayisi == 1 else 0.4)
            if v is None:
                if i == 0:
                    return self._kural_kanit(kriter_metni, parcalar, notlar=["BDM yanit vermedi"], sorgu=sorgu)
                continue
            sonuc, guven = korumalar.belirsizlik_uygula(v["sonuc"], v["guven"], self.guven_esigi)
            if sonuc != "belirsiz":
                ok, idx = korumalar.kanit_dogrula(v["kanit_cumlesi"], parcalar, v.get("parca_indeks"))
                if not ok:
                    log.info("halusinasyon korumasi: kanit kaynakta yok -> belirsiz")
                    sonuc, guven = "belirsiz", min(guven, 0.3)
                elif kanit is None:
                    kanit, indeks = v["kanit_cumlesi"], idx
            oylar.append((sonuc, guven))
        if not oylar:
            return self._kural_kanit(kriter_metni, parcalar, notlar=["BDM yanit vermedi"], sorgu=sorgu)
        sonuc, guven = korumalar.cogunluk_oyu(oylar) if len(oylar) > 1 else oylar[0]
        notlar = [] if len(oylar) == 1 else [f"{len(oylar)} ornekleme, cogunluk oyu"]
        if sonuc == "belirsiz":
            kanit, indeks = None, None
        return KanitSonucu(sonuc, kanit, round(guven, 3), indeks, "bdm", notlar)

    def klinik_ozet(self, metin: str) -> list[str]:
        if not self.kural_modu:
            v = self._uret_json(istemler.KLINIK_OZET.format(metin=metin[:6000]), {"maddeler": list}, maks_token=400)
            if v:
                return [str(m) for m in v["maddeler"]][:6]
        return self._kural_ozet(metin)

    def protokol_taslagi(self, metin: str) -> dict | None:
        """Protokol metninden tasarim taslagi (kriter, kol, vizit, form onerisi). Kural modunda None.

        Cikti yalnizca oneridir; uygulanmasi insan onayiyla olur (web/ecrf.py).
        """
        if self.kural_modu or not (metin or "").strip():
            return None
        metin = metin.strip()
        if len(metin) > PROTOKOL_METIN_SINIRI:
            metin = _baslik_cevresi(metin, PROTOKOL_BASLIKLARI)
        v = self._uret_json(istemler.PROTOKOL_TASLAK.format(metin=metin[:PROTOKOL_METIN_SINIRI]),
                            {"dahil": list, "haric": list, "kollar": list, "vizitler": list, "formlar": list,
                             "guven": (int, float)}, maks_token=1500)
        if not v or not korumalar.json_sema(v, {"dahil": [str], "haric": [str], "kollar": [str],
                                                "vizitler": [{"ad": str, "gun": (int, float)}], "formlar": [str]}):
            return None
        v["vizitler"] = [{"ad": x["ad"][:40], "gun": int(x["gun"]), "pencere": int(x.get("pencere") or 0)}
                         for x in v["vizitler"]]
        v["guven"] = max(0.0, min(1.0, float(v["guven"])))
        return v

    def soru_cevap(self, soru: str, baglam: str) -> dict:
        if not self.kural_modu:
            v = self._uret_json(istemler.SORU_CEVAP.format(soru=soru, baglam=baglam[:6000]),
                                {"cevap": str, "guven": (int, float)}, maks_token=300)
            if v:
                dayanak = v.get("dayanak") or ""
                if dayanak and not korumalar.kanit_dogrula(dayanak, [baglam])[0]:
                    v["dayanak"], v["guven"] = "", min(float(v["guven"]), 0.3)
                    v["notlar"] = ["dayanak kaynakta bulunamadi"]
                return v
        # kural: en alakali cumleleri dondur
        arama = HibritArama(cumlelere_bol(baglam), self.gomme)
        hits = arama.ara(soru, k=2)
        if not hits:
            return {"cevap": "Verilen metinde bu bilgi yok.", "dayanak": "", "guven": 0.2, "yontem": "kural"}
        return {"cevap": " ".join(h[2] for h in hits), "dayanak": hits[0][2], "guven": round(min(0.6, hits[0][1]), 2),
                "yontem": "kural"}

    # -- kural tabanli yollar ------------------------------------------------

    def _kriter_terimleri(self, kriter_metni: str) -> list[str]:
        y = _kural_yapilandir(kriter_metni)
        terimler: list[str] = []

        def topla(s):
            if not isinstance(s, dict):
                return
            for k in ("ve", "veya"):
                for alt in s.get(k, []):
                    topla(alt)
            if "degil" in s:
                topla(s["degil"])
            terimler.extend(s.get("terimler", []))
            terimler.extend(s.get("niteleyiciler", []))
            if s.get("alan") == "gebelik":
                terimler.extend(["gebe", "gebelik", "hamile", "emzir", "laktasyon"])
            if s.get("ad"):
                terimler.append(s["ad"])
                terimler.extend(S.LAB_SOZLUGU.get(s["ad"], {}).get("es", []))
            if s.get("olcek"):
                terimler.append(s["olcek"])
        topla(y.sorgu)
        if not terimler:
            # sozlukte yoksa kriterin anlamli kelimeleri
            terimler = [k for k in re.findall(r"[a-zçğıöşü0-9-]{4,}", S.normalize(kriter_metni))
                        if k not in ("olan", "olmayan", "hastalar", "hasta", "veya", "ile", "için", "sonra", "önce", "içinde",
                                     "varlığı", "varlik", "öyküsü", "oykusu", "bulunması", "olması", "mevcut", "bilinen",
                                     "aktif", "tanısı", "tanisi", "kriterleri", "durumu")]
        return terimler

    def _kural_kanit(self, kriter_metni: str, parcalar: list[str], notlar: list[str] | None = None,
                     sorgu: dict | None = None) -> KanitSonucu:
        """BDM olmadan kanit: once kalip tabanli (sayisal/TNM/reseptor) degerlendirme, sonra terim eslesmesi.

        Terim eslesmesi tek basina zayif bir kanittir; en az iki anlamli terim ya da uzun tek bir terim
        ister ve guveni dusuk tutar. Nihai karar her zaman arastirmacinindir.
        """
        notlar = list(notlar or [])
        terimler = self._kriter_terimleri(kriter_metni)
        if sorgu is None:
            sorgu = _kural_yapilandir(kriter_metni).sorgu
        anlamli = [t for t in terimler if len(t) > 2]
        cumleler: list[tuple[int, str]] = []
        for idx, parca in enumerate(parcalar):
            for c in cumlelere_bol(parca):
                if c.strip():
                    cumleler.append((idx, c.strip()))
        if not cumleler:
            return KanitSonucu("belirsiz", None, 0.0, None, "kural", notlar + ["metin yok"])

        # 1) kalip tabanli: sayisal karsilastirma, TNM, reseptor, gebelik, zaman penceresi
        en_iyi = None
        for idx, c in cumleler:
            terim_var = any(_terim_cumlede(t, c) for t in anlamli)
            r = metin_kurallari.degerlendir(sorgu, kriter_metni, c, terim_var, terimler=anlamli)
            if r and (en_iyi is None or r[1] > en_iyi[0][1]):
                en_iyi = (r, idx, c)
        if en_iyi:
            (sonuc, guven, aciklama), idx, c = en_iyi
            return KanitSonucu(sonuc, c, guven, idx, "kural", notlar + [f"kalip: {aciklama}"])

        # 2) terim eslesmesi: en cok terim iceren cumle. Bazi kategorilerde terim eslesmesi
        #    yaniltici oldugundan belirsiz birakip arastirmaciya devrediyoruz.
        alan = (sorgu or {}).get("alan") or ((sorgu or {}).get("degil") or {}).get("alan")
        if metin_kurallari._uln_var(sorgu or {}):
            return KanitSonucu("belirsiz", None, 0.2, None, "kural", notlar + ["ULN karsilastirmasi icin laboratuvar referans araligi gerekli"])
        if alan == "tedavi_gecmisi":
            return KanitSonucu("belirsiz", None, 0.2, None, "kural", notlar + ["tedavi gecmisi metinde net degil"])
        puanli = []
        for idx, c in cumleler:
            eslesen = [t for t in anlamli if _terim_cumlede(t, c)]
            if not eslesen:
                continue
            puan = sum(len(t) for t in eslesen)
            puanli.append((len(eslesen), puan, idx, c, eslesen))
        if not puanli:
            return KanitSonucu("belirsiz", None, 0.0, None, "kural", notlar + ["ilgili cumle bulunamadi"])
        puanli.sort(key=lambda x: (x[0], x[1]), reverse=True)
        n, puan, idx, c, eslesen = puanli[0]
        gerekli = max(1, -(-len(anlamli) // 2))  # anlamli terimlerin en az yarisi (yukari yuvarla)
        yeterli = n >= gerekli
        # uc ve daha fazla terimli ifadelerde niteleyici (ilk iki sozcuk: "sol ana", "kronik total") sart;
        # yoksa "koroner lezyon" gibi genel eslesmeler yanlis pozitif uretiyor
        if yeterli and len(anlamli) >= 3 and not any(t in eslesen for t in anlamli[:2]):
            yeterli = False
        if not yeterli:
            return KanitSonucu("belirsiz", c, 0.3, idx, "kural", notlar + ["zayif terim eslesmesi; arastirmaci degerlendirmeli"])
        olumsuz = _olumsuz_mu(c, terimler)
        guven = round(min(0.72, 0.45 + 0.08 * n), 2)
        return KanitSonucu("saglanmadi" if olumsuz else "saglandi", c, guven, idx, "kural",
                           notlar + ["terim eslesmesi; BDM dogrulamasi onerilir"])

    def _kural_ozet(self, metin: str) -> list[str]:
        cumleler = cumlelere_bol(metin)
        anahtar = ("tanı", "tani", "evre", "metasta", "tedavi", "kemoterapi", "ecog", "performans", "hemoglobin",
                   "kreatinin", "mutasyon", "pozitif", "negatif", "kullanmakta", "almakta")
        secilen = [c for c in cumleler if any(a in S.normalize(c) for a in anahtar)]
        return (secilen or cumleler)[:5]
