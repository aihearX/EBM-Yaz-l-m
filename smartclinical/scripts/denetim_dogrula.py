"""Denetim izi zincirini dogrular. Zincir ozetleri HMAC-SHA256'dir; dogrulama calisirken SC_SECRET_KEY uygulamadakiyle
ayni olmalidir (aksi halde ilk kayitta "bozuk" raporlanir). Gunluk calistirilmasi onerilir (bkz. deploy/KURULUM.md)."""
import sys

from ..db import db_oturumu
from ..services.denetim import zinciri_dogrula


def main():
    with db_oturumu() as db:
        gecerli, bozuk = zinciri_dogrula(db)
    if gecerli:
        print("Denetim izi zinciri gecerli.")
        return 0
    print(f"UYARI: zincir {bozuk} numarali kayitta bozuk! (anahtar degistiyse ilk kayitta durur)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
