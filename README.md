# ◈ DISMAKER — EVRENSEL DİSCORD MİMARI VE SİSTEM MÜHENDİSİ

**DisMaker**, kullanıcının doğal dilde verdiği komutları analiz ederek her türlü tema (yazılım, oyun, e-spor, sanat, eğitim, finans, rol yapma, şirket vb.) için en yüksek tipografik, hiyerarşik ve güvenlik standartlarında **üretim kalitesinde (production-ready)** Discord sunucuları tasarlayan ve tek tıkla inşa eden otonom bir sistemdir.

---

## ✦ ÖNE ÇIKAN ÖZELLİKLER VE MİMARİ İLKELER

### 1. Anti-Slop ve Rafine Tasarım İlkeleri
- **Sıfır Emoji Çöplüğü:** Kanallara ve rollere anlamsız, göz yoran mobil emojiler (🔥, 👑, 💎, 🚀 vb.) doldurulmaz. Yalnızca temaya uygun, şık ve minimalist UTF-8 sembolleri (`◈`, `⬡`, `›`, `✦`, `│`, `—`, `•`) kullanılır.
- **Tipografik Hiyerarşi:** Kategori isimleri tamamı büyük harf ve estetik sınırlarla ayrılmış (`◈ BİLGİLENDİRME ◈`, `│ TOPLULUK │`), metin kanalları temiz `kebab-case` formatındadır (`› genel-sohbet`, `› proje-paylasim`).
- **Mat ve Dengeli Renkler:** Discord'un karanlık modunda göz yormayan, Vercel/Linear tasarım standardında sofistike HEX renk kodları seçilir.

### 2. Ağaç Dalı Kanal Hiyerarşisi & Semantik İzin Matrisi
- **Ağaç Dalı Görsel Düzeni:** Kanallar kategori içinde `├・` ve `╰・` sembolleriyle hiyerarşik ağaç dalı formatında düzenlenir (`├・duyurular`, `╰・foto-paylasim`, `╰・➕・Oda Oluştur`).
- **Doğrulama Kapısı (Verification Gate):** Sunucuya yeni gelenler için sunucu kilitlenir; yalnızca `#kurallar` kanalını görürler. Kurallar altındaki butona basıldığında tüm sunucu açılır.
- **Canlı Destek & Bilet Sistemi (Tickets):** `#sunucu-destek` kanalından tek tıkla özel destek talebi (`bilet-kullanici`) açılabilir.
- **Dinamik Ses Odaları (Join-to-Create):** `➕・Oda Oluştur` kanalına tıklandığında üyeye özel geçici oda açılır, boşaldığında otomatik silinir.
- **İnteraktif Rol Paneli:** `#rol-secim` kanalında hem açılır menü (SelectMenu) hem de hızlı tıklama butonlarıyla üyeler diledikleri rolleri alabilir.
- **Semantik İzinler:** Bilgi ve kural kanalları salt-okunur, medya kanalları yavaş modlu (`slowmode: 5s`), yönetim alanları `@everyone` rolüne tamamen gizlidir.

### 3. Akıllı Gemini Modeli Zinciri (Flash Serisi Fallback)
- Sistem öncelikle Google'ın en hızlı ve güncel Flash serisi modellerini hedefler (`gemini-flash-lite-latest`, `gemini-3.5-flash-lite`, `gemini-3-flash-preview`, `gemini-3.1-flash-lite`).
- Herhangi bir modelde anlık yoğunluk (HTTP 503) veya kota kısıtlaması yaşanırsa, sistem çökmeden kesintisiz olarak yedek modellere otomatik geçiş yapar.

### 4. 7/24 Dinamik Güvenlik ve Moderasyon Motoru
- Prompt içinde özel kural veya ceza istendiğinde (`küfür edenlere 15 dk mute atılsın`, `reklam yasak olsun` vb.), bot bu kuralları 7/24 arka planda yürütür.
- Küfür/hakaret ve Discord davet linki paylaşımlarını anında siler, kullanıcıya Discord'un yerel Timeout API'si ile ceza verir ve log kanalına (`› mod-log`) detaylı denetim kaydı düşer.

### 5. Otomatik Rol (Autorole)
- Sunucuya yeni katılan üyelere belirlenen temel başlangıç rolünü (`Üye`, `Geliştirici`, `Gezgin` vb.) gecikmesiz olarak otomatik atar.

---

## 🛠 KURULUM ADIMLARI

### Adım 1: Depoyu Hazırlayın ve Bağımlılıkları Yükleyin

Komut istemcisinde (Terminal / PowerShell) proje dizinine gelin:

```powershell
pip install -r requirements.txt
```

*(Gerekli paketler: `discord.py`, `aiohttp`, `python-dotenv`, `pydantic`, `rich`)*

---

### Adım 2: `.env` Dosyasını Yapılandırın

Proje kök dizinindeki `.env` dosyasını bir metin düzenleyiciyle açın:

```env
# ==============================================================================
# DISMAKER - GÜVENLİK VE YAPILANDIRMA AYARLARI (.env)
# ==============================================================================

# 1. DISCORD BOT TOKEN
DISCORD_BOT_TOKEN=BURAYA_DISCORD_BOT_TOKENINIZI_GIRIN

# 2. GOOGLE GEMINI API KEY
GEMINI_API_KEY=BURAYA_GEMINI_API_KEYINIZI_GIRIN

# 3. GEMINI MODEL YAPILANDIRMASI
GEMINI_PRIMARY_MODEL=gemini-flash-lite-latest
GEMINI_FALLBACK_MODEL=gemini-3.5-flash-lite

# 4. BOT KONTROL AYARLARI
BOT_PREFIX=!
```

#### Discord Bot Token'ı Nasıl Alınır?
1. [Discord Developer Portal](https://discord.com/developers/applications) adresine gidin.
2. **New Application** butonuna basarak uygulamanızı adlandırın.
3. Sol menüden **Bot** sekmesine geçin ve **Reset Token** diyerek token'ınızı kopyalayın.
4. **ÖNEMLİ:** Aynı sayfada aşağı kaydırarak **Privileged Gateway Intents** altındaki:
   - ✅ **SERVER MEMBERS INTENT**
   - ✅ **MESSAGE CONTENT INTENT**
   seçeneklerini **AÇIK** duruma getirin ve kaydedin.
5. Sol menüden **OAuth2 ➔ URL Generator** sekmesine gelin:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Administrator` (veya *Manage Roles, Manage Channels, Moderate Members, View Channels, Send Messages, Manage Messages*)
   - Oluşan davet linkini tarayıcınıza yapıştırarak botu sunucunuza ekleyin.

#### Gemini API Anahtarı Nasıl Alınır?
1. [Google AI Studio](https://aistudio.google.com/) adresine Google hesabınızla giriş yapın.
2. **Get API Key** butonuna tıklayın ve yeni bir anahtar oluşturun.
3. Aldığınız anahtarı `.env` dosyasındaki `GEMINI_API_KEY` alanına yapıştırın.

---

## 🚀 ÇALIŞTIRMA VE KULLANIM

### 1. Discord Botunu Başlatma

```powershell
python main.py
```

Bot çevrimiçi olduğunda konsolda model zincirini, bağlı sunucuları ve durum bilgilerini içeren şık bir özet görüntülenecektir.

---

### 2. Komut Satırı (CLI) Modu (Discord Olmadan Test Edin)

Discord botunu çalıştırmadan doğrudan terminalden mimari üretmek ve doğrulanmış JSON çıktısını almak için:

```powershell
python cli.py "Yapay zeka araştırmacıları ve Python geliştiricileri için profesyonel bir topluluk sunucusu. Reklam yasak olsun, küfür edenlere 10 dk timeout atılsın."
```

Bu komut:
- Gemini 3.5 / 2.5 modellerini çalıştırır.
- Mimariyi terminalde tablolarla gösterir.
- Üretilen katı JSON çıktısını `server_architecture.json` dosyasına kaydeder.

---

## 💬 DİSCORD İÇİ KOMUTLAR

### Slash Komutları (`/dismaker`)

| Komut | Açıklama |
| :--- | :--- |
| `/dismaker build <prompt> [clean_existing]` | Belirttiğiniz temada sunucuyu tasarlar, önizleme sunar ve buton onayıyla inşa eder. |
| `/dismaker preview <prompt>` | Sunucuyu değiştirmeden sadece mimari planını ve kanalları görüntüler. |
| `/dismaker moderation` | Sunucunun 7/24 küfür, davet engeli ve timeout sürelerini görüntüler / düzenler. |
| `/dismaker autorole <rol>` | Yeni katılan üyelere otomatik atanacak başlangıç rolünü belirler. |
| `/dismaker help` | Kapsamlı rehber ve örnek istekleri listeler. |

### Klasik Metin Komutları (`!dismaker`)

Slash komutlarına alternatif olarak metin kanallarından doğrudan çalıştırabilirsiniz:
- `!dismaker build <prompt>`
- `!dismaker help`

---

## 📋 ÖRNEK PROMPT İSTEKLERİ

Aşağıdaki gibi dilediğiniz detayda doğal dille istekte bulunabilirsiniz:

1. **Yazılım & Yapay Zeka:**
   > `/dismaker build Python, Makine Öğrenimi ve Web Geliştiricileri için bir çalışma ve destek sunucusu. Proje vitrini, kod inceleme ve sesli çalışma odaları olsun. Küfür edenlere 15 dk mute atılsın, reklam linkleri engellensin.`

2. **Oyun & Topluluk:**
   > `/dismaker build Valorant ve CS2 oyuncuları için rekabetçi bir klan sunucusu. Takım ses kanalları, klip paylaşım alanı ve turnuva duyuru odaları olsun. Giriş rolü Oyuncu olsun.`

3. **Tasarım & Sanat:**
   > `/dismaker build 3D modelleme, illüstrasyon ve UI/UX tasarımcıları için portfolyo ve geri bildirim sunucusu. Tasarım kanallarında yavaş mod olsun.`

---

## 📂 PROJE MİMARİSİ

```
dismaker/
├── .env                  # Bot token ve Gemini API anahtarı
├── .env.example          # Güvenli örnek şablon
├── requirements.txt      # Gerekli kütüphaneler
├── config.py             # Yapılandırma ve model fallback tanımları
├── main.py               # Bot başlatıcı ve giriş noktası
├── cli.py                # Bağımsız terminal mimari test aracı
├── core/
│   ├── prompt.py         # Evrensel Discord Mimarı KESİN Sistem İstemi
│   ├── schema.py         # Pydantic JSON veri modelleri ve doğrulayıcı
│   ├── gemini_client.py  # 3.5 ➔ 2.5 Dinamik Fallback İstemcisi
│   └── database.py       # SQLite ayar ve moderasyon kayıt yöneticisi
└── discord_bot/
    ├── bot.py            # Discord bot sınıfı ve komut yönlendiricileri
    ├── builder.py        # Canlı sunucu inşa motoru (Roller, Kanallar, İzinler)
    ├── views.py          # Onay butonları ve canlı ilerleme çubuğu
    ├── moderation.py     # 7/24 Küfür, reklam filtresi ve timeout yürütücüsü
    └── autorole.py       # Yeni üye otomatik rol atama motoru
```

---

## 🔒 GÜVENLİK VE İZİNLER NOTU
- Sunucu inşası (`build`) komutu yalnızca **Yönetici (Administrator)** veya **Sunucu Sahibi** tarafından tetiklenebilir.
- Botun diğer rolleri yönetebilmesi ve üyelere rol verebilmesi için, Discord sunucu ayarlarında **DisMaker botunun rolünün diğer rollerin üzerinde yer alması gerekmektedir.**
