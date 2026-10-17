# 📚 Sınav Asistanı — Yapay Zekâ Destekli Telegram Sınav Hazırlık Botu

YKS, KPSS, DGS, ALES ve YDT sınavlarına hazırlanan öğrenciler için yapay zekâ destekli bir Telegram asistanı. Claude (Anthropic) modelleriyle çalışır; konu anlatımı yapar, soru çözer, test hazırlar, çalışma planı çıkarır ve fotoğrafla gönderilen soruları analiz eder.

🇬🇧 [Click here for the English version](./README.md)

---

## ✨ Özellikler

- 🎯 **Çok sınavlı destek** — YKS (TYT/AYT), KPSS, DGS, ALES, YDT (İngilizce / Arapça / Almanca / Fransızca / Rusça)
- 📖 **Konu anlatımı** — Seçilen derse göre adım adım, örnekli anlatım
- ❓ **Test hazırlama** — Kolay/Orta/Zor seviyede 1-5 arası çoktan seçmeli soru, şıklar karıştırılır
- 💬 **Soru çözdürme** — Yazılı veya fotoğraflı sorulara detaylı çözüm
- 📸 **Fotoğraf analizi** — Vision modeliyle görsel soru çözümü
- 📅 **Çalışma planı** — Kalan gün ve günlük çalışma saatine göre haftalık program
- 🤔 **"Anlamadım" & "Yanlış Cevap"** — Çözümü farklı yaklaşımla yeniden anlatır veya baştan çözer
- 💳 **Telegram Stars** ile abonelik ödemesi
- 🚀 **Yanıt streaming** — Cevaplar yazılırken gösterilir, bekleme hissini azaltır
- ⚡ **Model seçimi** — Matematik/Fizik/Kimya/Biyoloji/Türkçe için Sonnet, diğerleri için Haiku (maliyet verimi)

## 🛠 Kullanılan Teknolojiler

- **Python 3.11+**
- **python-telegram-bot** 21.6 (async, rate limiter)
- **Anthropic SDK** — Claude Sonnet 4.6 ve Haiku 4.5 modelleri
- **asyncpg** — PostgreSQL async bağlantı havuzu
- **python-dotenv** — Ortam değişkeni yönetimi
- **Railway** — Deployment platformu

## 📦 Kurulum

### 1. Depoyu klonla
```bash
git clone https://github.com/Hasankr-27/sinav-botu.git
cd sinav-botu
```

### 2. Sanal ortam oluştur
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 3. Bağımlılıkları yükle
```bash
pip install -r requirements.txt
```

### 4. Ortam değişkenlerini ayarla
`.env.example` dosyasını `.env` olarak kopyala ve doldur:
```bash
cp .env.example .env
```

Gerekli değerler:
- `TELEGRAM_TOKEN` — [BotFather](https://t.me/BotFather)'dan `/newbot` ile al
- `ANTHROPIC_API_KEY` — [console.anthropic.com](https://console.anthropic.com/settings/keys) üzerinden oluştur
- `DATABASE_URL` — PostgreSQL bağlantı URL'i (Railway, Supabase, Neon vs.)

### 5. Botu çalıştır
```bash
python main.py
```

İlk çalıştırmada PostgreSQL tabloları otomatik oluşturulur.

## 🗂 Proje Yapısı

```
sinav-botu/
├── main.py              # Bot başlatıcı ve handler kayıtları
├── handlers.py          # Mesaj/callback handler'ları
├── ai.py                # Claude API entegrasyonu, sistem promptları
├── database.py          # PostgreSQL işlemleri (asyncpg)
├── payments.py          # Telegram Stars ödeme akışı
├── config.py            # Konfigürasyon sabitleri
├── requirements.txt     # Python bağımlılıkları
├── .env.example         # Örnek ortam değişkeni dosyası
└── .gitignore
```

## 💡 Kullanım

Botu başlattıktan sonra Telegram'da `/start` komutuyla kullan:

1. Hangi sınava hazırlandığını seç (YKS / KPSS / DGS / ALES / YDT)
2. Ne yapmak istediğini seç:
   - 📖 Konu Anlat
   - ❓ Soru Hazırla (ders → konu → zorluk → sayı)
   - 💬 Soru Çözdür (yazılı/fotoğraflı)
   - 📅 Çalışma Planı
3. Günlük mesaj hakkı: ücretsiz **4**, abone **50**
4. Abonelik: Telegram Stars ile (1 ay: 70⭐, 3 ay: 200⭐)

## 📝 Notlar

- Bot `claude-sonnet-4-6` ve `claude-haiku-4-5` modellerini kullanır
- Sistem promptları `cache_control: ephemeral` ile cache'lenir (maliyet avantajı)
- Streaming yanıtlar sayesinde kullanıcı beklerken ilerlemeyi görür
- Per-user asyncio lock ile eşzamanlı mesaj çatışması önlenir
- Atomik `FOR UPDATE` transaction'larıyla kota kontrolü yapılır
