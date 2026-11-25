# ppgen – Google Play Privacy Policy Generator

Mobil oyunlar için Google Play'in kabul ettiği gizlilik politikası, veri silme sayfası ve Play Console
**Data safety** cevaplarını tek bir YAML dosyasından üretir. Ajanlar (Claude Code vb.) için tasarlandı:
her komut `--json` verir, hata kodları anlamlıdır, Unity projesini tarayıp SDK'ları kendisi bulur.

## Kurulum
```powershell
pip install -r requirements.txt
```

## Kullanım (5 adım)
```powershell
# 1) Unity projesini tara, config'i oluştur (SDK'lar, paket adı, şirket adı otomatik)
python ppgen.py detect "C:\Projects\SandSwipe" --write

# 2) apps/<slug>.yaml içindeki TODO alanlarını kontrol et (çocuk hedefi, mediation ağları). E-posta hep help@waow.games

# 3) Play kurallarına göre kontrol et
python ppgen.py validate

# 4) Sayfaları ve Play Console cevaplarını üret
python ppgen.py build

# 5) GitHub'a push et, sonra canlı URL'yi kontrol et
python ppgen.py verify-live
```
Unity projesi yoksa: `python ppgen.py new my-game`.

Ajanla kullanım: Claude Code'a "Sand Swipe için privacy policy hazırla" demen yeterli;
`.claude/skills/privacy-policy/SKILL.md` akışı yürütür.

## Çıktılar
| Dosya | Ne işe yarar |
|---|---|
| `docs/<slug>/index.html` | Gizlilik politikası → Play Console > App content > **Privacy policy URL** |
| `docs/<slug>/data-deletion.html` | Data safety'deki **veri silme URL'si** (hesap varsa hesap silme URL'si) |
| `reports/<slug>-play-console.md` | Data safety, Ads, Advertising ID, Target audience için birebir cevaplar ve kontrol listesi |
| `docs/index.html` | Tüm oyunların listesi |

## GitHub Pages (bir kere)
1. Bu klasörü bir GitHub reposuna push et (ör. `privacy-policies`). Ücretsiz planda Pages için repo **public** olmalı.
2. Repo > Settings > Pages > Source: **Deploy from a branch**, Branch: `main`, Folder: **/docs**.
3. URL `https://<kullanici>.github.io/privacy-policies/` olur; bunu config'teki `hosting.base_url`'a yaz.
4. Her oyunun URL'si: `https://<kullanici>.github.io/privacy-policies/<slug>/`.

## Play'in kabul etmesi için neye dikkat ediliyor
- Herkese açık, giriş istemeyen, HTTPS, HTML sayfa (PDF/Google Docs değil). `verify-live` bunu kontrol eder.
- Sayfada "Privacy Policy" başlığı, oyun adı, geliştirici adı, iletişim e-postası var. `build` sırasında otomatik kontrol edilir.
- Kullanılan her SDK politika linkiyle listelenir. Aynı veriler Data safety raporuna da yazılır, ikisi çelişmez.
- Reklam varsa: Advertising ID, kişiselleştirilmiş reklam, onay (UMP/CMP) ve reklam kimliğini silme anlatılır.
- Veri silme yolu ve sayfası, GDPR/UK, ABD (CCPA), Türkiye (KVKK, `country: TR`) hakları.
- Çocuk hedefliyse: COPPA/Families bölümü. Kişiselleştirilmiş reklam ve sertifikasız reklam SDK'ları `validate` ile engellenir.

## Yeni SDK eklemek
`data/sdks.yaml` içine benzer bir girdiyi kopyala, alanları doldur, sonra `python ppgen.py check-links`.
Not: 403/429 dönen linkler genelde bot engelidir; tarayıcıda açılıyorsa sorun yok.

## Komutlar
| Komut | Açıklama |
|---|---|
| `sdks` | Desteklenen SDK id'leri |
| `new <slug>` | Boş config oluşturur |
| `detect <unity-yolu> [--write] [--slug x] [--force]` | Unity projesini tarar |
| `validate [slug]` | Play kurallarına göre kontrol (slug yoksa hepsi) |
| `build [slug]` | Sayfaları ve raporu üretir |
| `verify-live [slug]` | Yayındaki URL'leri kontrol eder |
| `check-links` | SDK linklerini kontrol eder |

> Bu araç hukuki danışmanlık değildir. Üretilen metni gözden geçir; şüphede bir hukukçuya danış.
