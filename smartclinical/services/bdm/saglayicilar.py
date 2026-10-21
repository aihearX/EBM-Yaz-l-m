"""BDM saglayicilari. Hepsi hastane ici (on-premise) sunuculara HTTP ile baglanir.

kural     : ag gerektirmez; kriter servisine ve terim aramasina delege eder (varsayilan / yedek)
ollama    : /api/chat
vllm      : OpenAI uyumlu /v1/chat/completions
llamacpp  : llama.cpp sunucusu /completion
"""

import json
import logging
import time
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)


class BDMErisimHatasi(Exception):
    """Model sunucusuna ulasilamadi ya da gecersiz yanit dondu."""


@dataclass
class Uretim:
    metin: str
    token_sayisi: int
    sure_ms: int
    model: str


class Saglayici:
    ad = "temel"

    def __init__(self, url: str = "", model: str = "", zaman_asimi: float = 60.0):
        self.url = url.rstrip("/")
        self.model = model
        self.zaman_asimi = zaman_asimi

    def uret(self, istem: str, sistem: str | None = None, json_cikti: bool = False,
             sicaklik: float = 0.0, maks_token: int = 512) -> Uretim:
        raise NotImplementedError

    def hazir(self) -> bool:
        try:
            r = httpx.get(self.url, timeout=2.0)
            return r.status_code < 500
        except httpx.HTTPError:
            return False

    def _post(self, yol: str, govde: dict) -> dict:
        try:
            r = httpx.post(self.url + yol, json=govde, timeout=self.zaman_asimi)
        except httpx.ConnectError as e:
            raise BDMErisimHatasi(f"{self.ad} sunucusuna bağlanılamadı ({self.url}): {e}") from e
        except httpx.TimeoutException as e:
            raise BDMErisimHatasi(f"{self.ad} yanıt vermedi ({self.zaman_asimi} sn)") from e
        except httpx.HTTPError as e:
            raise BDMErisimHatasi(f"{self.ad} HTTP hatası: {e}") from e
        if r.status_code >= 400:
            raise BDMErisimHatasi(f"{self.ad} {r.status_code} döndü: {r.text[:200]}")
        try:
            return r.json()
        except json.JSONDecodeError as e:
            raise BDMErisimHatasi(f"{self.ad} geçersiz JSON döndü") from e


class KuralTabanliSaglayici(Saglayici):
    """Model yokken calisan yedek. `uret` serbest metin uretemez; istemci gorev bazli
    kural yollarini dogrudan kullanir (bkz. istemci.BDMIstemci._kural_*)."""

    ad = "kural"

    def __init__(self, *_, **__):
        super().__init__("", "kural-tabanli-v1")

    def hazir(self) -> bool:
        return True

    def uret(self, istem, sistem=None, json_cikti=False, sicaklik=0.0, maks_token=512) -> Uretim:
        raise BDMErisimHatasi("kural tabanlı sağlayıcı serbest metin üretmez")


class OllamaSaglayici(Saglayici):
    ad = "ollama"

    def hazir(self) -> bool:
        try:
            r = httpx.get(self.url + "/api/tags", timeout=2.0)
            return r.status_code == 200 and any(m.get("name", "").startswith(self.model.split(":")[0])
                                                for m in r.json().get("models", []))
        except (httpx.HTTPError, ValueError):
            return False

    def uret(self, istem, sistem=None, json_cikti=False, sicaklik=0.0, maks_token=512) -> Uretim:
        mesajlar = ([{"role": "system", "content": sistem}] if sistem else []) + [{"role": "user", "content": istem}]
        govde = {"model": self.model, "messages": mesajlar, "stream": False,
                 "options": {"temperature": sicaklik, "num_predict": maks_token}}
        if json_cikti:
            govde["format"] = "json"
        t0 = time.monotonic()
        v = self._post("/api/chat", govde)
        return Uretim(v.get("message", {}).get("content", ""), int(v.get("eval_count", 0)),
                      int((time.monotonic() - t0) * 1000), self.model)


class VLLMSaglayici(Saglayici):
    ad = "vllm"

    def hazir(self) -> bool:
        try:
            r = httpx.get(self.url + "/v1/models", timeout=2.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def uret(self, istem, sistem=None, json_cikti=False, sicaklik=0.0, maks_token=512) -> Uretim:
        mesajlar = ([{"role": "system", "content": sistem}] if sistem else []) + [{"role": "user", "content": istem}]
        govde = {"model": self.model, "messages": mesajlar, "temperature": sicaklik, "max_tokens": maks_token}
        if json_cikti:
            govde["response_format"] = {"type": "json_object"}
        t0 = time.monotonic()
        v = self._post("/v1/chat/completions", govde)
        try:
            metin = v["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise BDMErisimHatasi("vllm yanıtında choices yok") from e
        return Uretim(metin, int(v.get("usage", {}).get("completion_tokens", 0)),
                      int((time.monotonic() - t0) * 1000), v.get("model", self.model))


class LlamaCppSaglayici(Saglayici):
    ad = "llamacpp"

    def hazir(self) -> bool:
        try:
            return httpx.get(self.url + "/health", timeout=2.0).status_code == 200
        except httpx.HTTPError:
            return False

    def uret(self, istem, sistem=None, json_cikti=False, sicaklik=0.0, maks_token=512) -> Uretim:
        # llama.cpp sohbet sablonunu kendisi uygulamiyor; ChatML kullaniyoruz (egitimle ayni)
        tam = ""
        if sistem:
            tam += f"<|im_start|>system\n{sistem}<|im_end|>\n"
        tam += f"<|im_start|>user\n{istem}<|im_end|>\n<|im_start|>assistant\n"
        govde = {"prompt": tam, "temperature": sicaklik, "n_predict": maks_token, "stop": ["<|im_end|>"]}
        if json_cikti:
            # NOT: grammar dosyasi deploy/llamacpp/json.gbnf ; sunucu tarafinda yuklu olmali
            govde["grammar"] = _JSON_GBNF
        t0 = time.monotonic()
        v = self._post("/completion", govde)
        return Uretim(v.get("content", ""), int(v.get("tokens_predicted", 0)),
                      int((time.monotonic() - t0) * 1000), self.model)


_JSON_GBNF = r'''
root   ::= object
value  ::= object | array | string | number | ("true" | "false" | "null") ws
object ::= "{" ws ( string ":" ws value ("," ws string ":" ws value)* )? "}" ws
array  ::= "[" ws ( value ("," ws value)* )? "]" ws
string ::= "\"" ( [^"\\\x7F\x00-\x1F] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F]) )* "\"" ws
number ::= ("-"? ([0-9] | [1-9] [0-9]*)) ("." [0-9]+)? ([eE] [-+]? [0-9]+)? ws
ws     ::= ([ \t\n] ws)?
'''

SAGLAYICILAR = {
    "kural": KuralTabanliSaglayici,
    "ollama": OllamaSaglayici,
    "vllm": VLLMSaglayici,
    "llamacpp": LlamaCppSaglayici,
}


def saglayici_olustur(ad: str, url: str = "", model: str = "", zaman_asimi: float = 60.0) -> Saglayici:
    sinif = SAGLAYICILAR.get((ad or "kural").lower())
    if sinif is None:
        log.warning("bilinmeyen BDM saglayici '%s', kural tabanliya donuluyor", ad)
        sinif = KuralTabanliSaglayici
    return sinif(url, model, zaman_asimi)
