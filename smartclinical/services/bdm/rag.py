"""Kanita dayali eslestirme icin metin parcalama ve arama (BM25 + opsiyonel gomme)."""

import logging
import math
import re
from collections import Counter

import httpx

log = logging.getLogger(__name__)

_TR = str.maketrans("İIÇĞÖŞÜÂÎÛ", "iıçğöşüaiu")
# "Dr.", "vb." gibi kisaltmalarda cumle bolmemek icin
_KISALTMA = {"dr", "prof", "doc", "doç", "uzm", "op", "vb", "vs", "bkz", "no", "tel", "mg", "ml", "cm", "mm", "yak", "ort", "sn", "hs"}

STOP = set("""ve veya ile de da ki bu şu o bir için olan olarak ise ama fakat ancak gibi kadar sonra önce daha en çok az
the a an of in on at to and or is are was were be been for with by from as that this it its""".split())


def _kucuk(s: str) -> str:
    return s.translate(_TR).lower()


# Hafif Turkce govdeleme: sik cekim eklerini sondan kirpar. Tam bir stemmer degil, BM25 icin yeterli.
_EKLER = ("larının", "lerinin", "ların", "lerin", "ları", "leri", "lar", "ler", "ndan", "nden", "dan", "den", "tan", "ten",
          "nın", "nin", "nun", "nün", "ın", "in", "un", "ün", "da", "de", "ta", "te", "ya", "ye", "yı", "yi", "yu", "yü",
          "sı", "si", "su", "sü", "ı", "i", "u", "ü", "a", "e")


def govde(kelime: str) -> str:
    k = kelime
    for _ in range(2):
        for ek in _EKLER:
            if len(k) - len(ek) >= (5 if len(ek) == 1 else 4) and k.endswith(ek):
                k = k[: -len(ek)]
                break
    return k


def tokenize(metin: str) -> list[str]:
    kelimeler = re.findall(r"[a-zçğıöşü0-9][a-zçğıöşü0-9.,%-]*", _kucuk(metin))
    out = []
    for k in kelimeler:
        k = k.strip(".,-%")
        if not k or k in STOP:
            continue
        out.append(govde(k) if k.isalpha() else k)
    return out


def cumlelere_bol(metin: str) -> list[str]:
    metin = re.sub(r"\s+", " ", metin or "").strip()
    if not metin:
        return []
    parcalar, bas = [], 0
    for e in re.finditer(r"[.!?;](?=\s+[A-ZÇĞİÖŞÜ0-9(\[]|\s*$)", metin):
        onceki = metin[bas:e.start()].rsplit(" ", 1)[-1].lower().strip("(")
        if onceki in _KISALTMA:
            continue
        parcalar.append(metin[bas:e.end()].strip())
        bas = e.end()
    if bas < len(metin):
        parcalar.append(metin[bas:].strip())
    return [p for p in parcalar if p]


class Parcalayici:
    """Cumle penceresi: `pencere` cumleyi `kaydirma` adimla gruplar. Paragraf sinirlarina saygi duyar."""

    def __init__(self, pencere: int = 3, kaydirma: int = 2, maks_karakter: int = 900):
        self.pencere, self.kaydirma, self.maks_karakter = pencere, kaydirma, maks_karakter

    def parcala(self, metin: str) -> list[str]:
        out = []
        for paragraf in re.split(r"\n\s*\n|\r\n\s*\r\n", metin or ""):
            cumleler = cumlelere_bol(paragraf)
            if not cumleler:
                continue
            if len(cumleler) <= self.pencere:
                out.append(" ".join(cumleler))
                continue
            i = 0
            while i < len(cumleler):
                p = " ".join(cumleler[i:i + self.pencere])
                if len(p) > self.maks_karakter:
                    p = p[: self.maks_karakter]
                out.append(p)
                if i + self.pencere >= len(cumleler):
                    break
                i += self.kaydirma
        return out


class BM25Indeks:
    def __init__(self, parcalar: list[str], k1: float = 1.5, b: float = 0.75):
        self.parcalar = parcalar
        self.k1, self.b = k1, b
        self._tok = [tokenize(p) for p in parcalar]
        self._uz = [len(t) for t in self._tok]
        self._ort = (sum(self._uz) / len(self._uz)) if self._uz else 0.0
        df = Counter()
        for t in self._tok:
            df.update(set(t))
        n = len(parcalar)
        self._idf = {k: math.log(1 + (n - v + 0.5) / (v + 0.5)) for k, v in df.items()}
        self._tf = [Counter(t) for t in self._tok]

    def puanla(self, sorgu: str) -> list[float]:
        q = tokenize(sorgu)
        puan = []
        for i in range(len(self.parcalar)):
            s = 0.0
            for k in q:
                tf = self._tf[i].get(k)
                if not tf:
                    continue
                idf = self._idf.get(k, 0.0)
                payda = tf + self.k1 * (1 - self.b + self.b * self._uz[i] / (self._ort or 1))
                s += idf * tf * (self.k1 + 1) / payda
            puan.append(s)
        return puan

    def ara(self, sorgu: str, k: int = 5) -> list[tuple[int, float]]:
        p = self.puanla(sorgu)
        sirali = sorted(range(len(p)), key=lambda i: p[i], reverse=True)
        return [(i, p[i]) for i in sirali[:k] if p[i] > 0]


class GommeIstemci:
    """Gomme sunucusu (SC_GOMME_URL) ile konusur. Sunucu yoksa None dondurulur; arama BM25'e duser."""

    def __init__(self, url: str, model: str = "", zaman_asimi: float = 10.0):
        self.url, self.model, self.zaman_asimi = url.rstrip("/"), model, zaman_asimi

    @classmethod
    def olustur(cls, url: str | None, model: str = "") -> "GommeIstemci | None":
        if not url:
            return None
        ist = cls(url, model)
        try:
            r = httpx.get(ist.url + "/health", timeout=2.0)
            if r.status_code != 200:
                return None
        except httpx.HTTPError:
            log.info("gomme sunucusuna erisilemedi (%s); BM25 ile devam", url)
            return None
        return ist

    def gom(self, metinler: list[str]) -> list[list[float]]:
        r = httpx.post(self.url + "/embed", json={"model": self.model, "input": metinler}, timeout=self.zaman_asimi)
        r.raise_for_status()
        v = r.json()
        return v.get("embeddings") or v.get("data") or []


def _kosinus(a: list[float], b: list[float]) -> float:
    pay = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return pay / (na * nb) if na and nb else 0.0


class HibritArama:
    """BM25 + (varsa) gomme benzerligi. Agirlik: 0.5/0.5, puanlar [0,1] araligina olceklenir."""

    def __init__(self, parcalar: list[str], gomme: GommeIstemci | None = None, agirlik_bm25: float = 0.5):
        self.parcalar = parcalar
        self.bm25 = BM25Indeks(parcalar)
        self.gomme = gomme
        self.agirlik_bm25 = agirlik_bm25
        self._vektorler = None
        if gomme and parcalar:
            try:
                self._vektorler = gomme.gom(parcalar)
            except httpx.HTTPError as e:
                log.warning("gomme alinamadi, BM25 ile devam: %s", e)
                self.gomme = None

    def ara(self, sorgu: str, k: int = 5) -> list[tuple[int, float, str]]:
        if not self.parcalar:
            return []
        bm = self.bm25.puanla(sorgu)
        mx = max(bm) or 1.0
        puan = [x / mx for x in bm]
        if self.gomme and self._vektorler:
            try:
                qv = self.gomme.gom([sorgu])[0]
                kos = [_kosinus(qv, v) for v in self._vektorler]
                puan = [self.agirlik_bm25 * p + (1 - self.agirlik_bm25) * max(0.0, c) for p, c in zip(puan, kos)]
            except (httpx.HTTPError, IndexError) as e:
                log.warning("sorgu gommesi alinamadi: %s", e)
        sirali = sorted(range(len(puan)), key=lambda i: puan[i], reverse=True)
        return [(i, round(puan[i], 4), self.parcalar[i]) for i in sirali[:k] if puan[i] > 0]
