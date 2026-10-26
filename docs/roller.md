# Roller, sekmeler ve izinler

Rol globaldir; çalışma bazlı görünürlük ayrıca uygulanır (`services/yetki.py`):

- Yönetici ve denetçi her çalışmayı görür.
- Sponsor yalnızca kurum adı (`Kullanici.kurum`) çalışmanın sponsor alanıyla eşleşen çalışmaları görür
  (büyük/küçük harf ve boşluk farkı gözetilmez) ve her yerde salt okunurdur.
- Araştırmacı ve koordinatör yalnızca kendi merkezinin (`Kullanici.merkez_id`) yer aldığı çalışmaları görür;
  gönüllü, veri, güvenlik, ziyaret ve belge listeleri de kendi merkeziyle sınırlıdır. Hasta havuzu, CSV yükleme ve
  HBYS eşitleme yalnızca kendi merkezleri için açıktır (`merkez_erisimi`).
- Proje yöneticisi, CRA, veri yöneticisi, biyoistatistikçi ve farmakovijilans (atanabilir roller) herhangi bir
  çalışmada ekip ataması yapıldıysa yalnızca atandıkları çalışmaları görür (`calisma_filtresi`). Sihirbazla çalışma
  kuran kullanıcı atanabilir roldeyse kendiliğinden ekibe eklenir.
- Tasarım ve düzenleme (`calisma_duzenleyebilir`): yönetici ve proje yöneticisi her zaman; araştırmacı yalnızca
  tekil ve üniversite modunda, kendi kurduğu ya da baş araştırmacısı kendi merkezinden olan çalışmada.

Bu dosyadaki tablolar `tests/test_roller.py` tarafından koddaki kurallarla karşılaştırılır; tabloyu ve kodu birlikte
güncelleyin. Semboller: `●` görünür, `—` görünmez, `○` koşullu (çalışma bazlı ya da kurulum moduna bağlı).

## Rol x sekme

| Sekme | Yönetici | Proje Yöneticisi | CRA | Veri Yöneticisi | Sponsor | Araştırmacı | Koordinatör | Denetçi |
|---|---|---|---|---|---|---|---|---|
| ozet | ● | ● | ● | ● | ● | ● | ● | ● |
| tasarim | ● | ● | — | — | — | ○ | — | — |
| protokol | ● | ● | ● | ● | ● | ● | ● | ● |
| merkezler | ● | ● | ● | ● | ● | ○ | ● | ● |
| basvurular | ● | ● | ● | — | ● | ○ | — | ● |
| ekip | ● | ● | — | — | — | — | — | — |
| gonulluler | ● | ● | ● | ● | — | ● | ● | ● |
| veri | ● | ● | ● | ● | — | ● | ● | ● |
| guvenlik | ● | ● | ● | ● | ● | ● | ● | ● |
| eslestirme | ● | — | — | — | — | ● | ● | — |
| rbm | ● | ● | ● | — | ● | — | — | ● |
| merkez-zekasi | ● | ● | ● | — | — | — | — | ● |
| izlem | ● | ● | ● | — | — | ● | ● | ● |
| belgeler | ● | ● | ● | ● | ● | ● | ● | ● |
| analiz | ● | ● | — | ● | — | ● | — | — |
| denetim | ● | ● | — | — | — | — | — | ● |

`○` araştırmacıda moda bağlı: CRO modunda `tasarim`, `merkezler` ve `basvurular` görünmez ve rotaları 403 döner (çalışmayı CRO kurar ve yürütür).

Notlar:

- `basvurular`: CRA ve sponsor salt okunur izler; kayıt ve karar formu `calisma.duzenle` izni ve çalışma bazlı
  düzenleme hakkı ister.
- `izlem`, `belgeler`, `gonulluler`, `veri`: araştırmacı ve koordinatör yalnızca kendi merkezinin kayıtlarını görür.
- `tasarim`: araştırmacı için koşullu; sekme ve rota `calisma_duzenleyebilir` ile belirlenir.
- Gönüllü detay ve veri giriş sayfaları `gonullu_erisimi` ile açılır: çalışma erişimi, sponsor hariç, merkez rolleri
  yalnızca kendi merkezinin gönüllüsü.

## Rol x izin

| İzin | Yönetici | Proje Yöneticisi | CRA | Veri Yöneticisi | Sponsor | Araştırmacı | Koordinatör | Denetçi | Biyoistatistikçi | Farmakovijilans |
|---|---|---|---|---|---|---|---|---|---|---|
| calisma.olustur | ● | ● | — | — | — | ● | — | — | — | — |
| calisma.duzenle | ● | ● | — | — | — | ● | — | — | — | — |
| kriter.onayla | ● | ● | — | — | — | ● | — | — | — | — |
| eslestirme.calistir | ● | ● | — | — | — | ● | ● | — | — | — |
| eslestirme.incele | ● | — | — | — | — | ● | ● | — | — | — |
| hasta.goruntule | ● | — | — | — | — | ● | ● | — | — | — |
| veri.gir | ● | — | — | — | — | ● | ● | — | — | — |
| veri.sdv | ● | — | ● | — | — | — | — | — | — | — |
| veri.kilitle | ● | — | — | ● | — | — | — | — | — | — |
| sorgu.ac | ● | — | ● | ● | — | — | — | — | — | — |
| sorgu.cevapla | ● | — | — | — | — | ● | ● | — | — | — |
| guvenlik.bildir | ● | — | — | — | — | ● | ● | — | — | ● |
| rbm.goruntule | ● | ● | ● | — | ● | — | — | ● | — | — |
| rbm.yonet | ● | ● | ● | — | — | — | — | — | — | — |
| merkez.yonet | ● | ● | ● | — | — | — | — | — | — | — |
| belge.yukle | ● | ● | ● | — | — | — | ● | — | — | — |
| denetim.goruntule | ● | ● | — | — | — | — | — | ● | — | — |
| kullanici.yonet | ● | — | — | — | — | — | — | — | — | — |
| bdm.kullan | ● | ● | ● | — | — | ● | ● | — | — | — |
| disa_aktar | ● | — | — | ● | — | — | — | — | ● | — |
| ekip.yonet | ● | ● | — | — | — | — | — | — | — | — |
| analiz.goruntule | ● | ● | — | ● | — | ● | — | — | ● | — |

Sponsor hiçbir yazma izninde yer almaz; "Yeni çalışma" düğmesi ve sihirbaz sponsora kapalıdır. Araştırmacı
sihirbazı yalnızca tekil ve üniversite modunda kullanabilir; CRO modunda çalışmayı proje yöneticisi kurar.

## Hesap güvenliği

- Beş hatalı girişten sonra hesap 15 dakika kilitlenir; her yeni kilitte süre iki katına çıkar. Süre dolunca
  doğru parola kabul edilir. Kilit denetim izine `kilit` olarak yazılır; yönetici arayüzden ya da
  `scripts/kilit_ac.py` ile açabilir.
- Aynı IP adresinden 15 dakikada 20 hatalı giriş denemesinden sonra yeni denemeler geçici olarak reddedilir.
- Parola en az `SC_PAROLA_MIN` (varsayılan 12) karakter, harf ve rakam içerir; `SC_PAROLA_GUN` (varsayılan 90)
  günde bir yenilenir; son 5 parola yeniden kullanılamaz. Yöneticinin belirlediği geçici parola ilk girişte
  değiştirilmek zorundadır (`/hesap/parola`).
- Hasta takma adları HMAC-SHA256 ile `SC_TAKMA_AD_ANAHTARI` anahtarına bağlıdır; anahtar değişiminde
  `scripts/yeniden_anahtarla.py` mevcut kayıtları günceller.
