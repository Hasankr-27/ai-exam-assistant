# 📚 Sınav Asistanı — AI-Powered Telegram Exam Prep Bot

An AI-powered Telegram bot that helps students prepare for Turkish national exams (YKS, KPSS, DGS, ALES, YDT). Powered by Claude (Anthropic) models — explains topics, solves problems, generates practice questions, builds study plans, and analyzes photo-based questions.

[🇹🇷 Türkçe için aşağıya kaydır](#-türkçe-sürüm)

---

## ✨ Features

- 🎯 **Multi-exam support** — YKS (TYT/AYT), KPSS, DGS, ALES, YDT (English / Arabic / German / French / Russian)
- 📖 **Topic explanations** — Step-by-step, example-based explanations by subject
- ❓ **Question generation** — 1-5 multiple-choice questions at Easy/Medium/Hard difficulty, answer positions randomized
- 💬 **Problem solving** — Detailed solutions to text or photo questions
- 📸 **Photo analysis** — Vision model handles image-based questions
- 📅 **Study plan** — Weekly schedule based on days remaining and daily hours available
- 🤔 **"I didn't get it" & "Wrong answer"** — Re-explain with a different approach, or re-solve from scratch
- 💳 **Telegram Stars** integration for subscription payments
- 🚀 **Response streaming** — Answers appear as they're generated
- ⚡ **Model routing** — Sonnet for Math/Physics/Chemistry/Biology/Turkish, Haiku for others (cost optimization)

## 🛠 Tech Stack

- **Python 3.11+**
- **python-telegram-bot** 21.6 (async, rate limiter)
- **Anthropic SDK** — Claude Sonnet 4.6 & Haiku 4.5 models
- **asyncpg** — PostgreSQL async connection pool
- **python-dotenv** — Environment variable management
- **Railway** — Deployment platform

## 📦 Installation

### 1. Clone the repository
```bash
git clone https://github.com/Hasankr-27/sinav-botu.git
cd sinav-botu
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Copy `.env.example` to `.env` and fill in the values:
```bash
cp .env.example .env
```

Required values:
- `TELEGRAM_TOKEN` — Create a bot via [BotFather](https://t.me/BotFather) (`/newbot`)
- `ANTHROPIC_API_KEY` — Generate at [console.anthropic.com](https://console.anthropic.com/settings/keys)
- `DATABASE_URL` — PostgreSQL connection URL (Railway, Supabase, Neon, etc.)

### 5. Run the bot
```bash
python main.py
```

PostgreSQL tables are created automatically on first run.

## 🗂 Project Structure

```
sinav-botu/
├── main.py              # Bot entrypoint and handler registration
├── handlers.py          # Message/callback handlers
├── ai.py                # Claude API integration, system prompts
├── database.py          # PostgreSQL operations (asyncpg)
├── payments.py          # Telegram Stars payment flow
├── config.py            # Configuration constants
├── requirements.txt     # Python dependencies
├── .env.example         # Example environment file
└── .gitignore
```

## 💡 Usage

Start the bot and use `/start` in Telegram:

1. Pick an exam (YKS / KPSS / DGS / ALES / YDT)
2. Choose an action:
   - 📖 Explain Topic
   - ❓ Generate Questions (subject → topic → difficulty → count)
   - 💬 Solve Problem (text/photo)
   - 📅 Study Plan
3. Daily message quota: **4** free, **50** for subscribers
4. Subscription via Telegram Stars (1 month: 70⭐, 3 months: 200⭐)

## 📝 Notes

- Uses `claude-sonnet-4-6` and `claude-haiku-4-5` models
- System prompts are cached with `cache_control: ephemeral` for cost efficiency
- Streaming responses show progress while generating
- Per-user asyncio locks prevent concurrent message conflicts
- Atomic `FOR UPDATE` transactions handle quota enforcement

---

## 🇹🇷 Türkçe Sürüm

YKS, KPSS, DGS, ALES ve YDT sınavlarına hazırlanan öğrenciler için yapay zeka destekli bir Telegram asistanı. Claude (Anthropic) modelleriyle çalışır; konu anlatımı yapar, soru çözer, test hazırlar, çalışma planı çıkarır ve fotoğrafla gönderilen soruları analiz eder.

### ✨ Özellikler

- 🎯 **Çok sınavlı destek** — YKS (TYT/AYT), KPSS, DGS, ALES, YDT (İngilizce / Arapça / Almanca / Fransızca / Rusça)
- 📖 **Konu anlatımı** — Seçilen derse göre adım adım, örnekli anlatım
- ❓ **Test hazırlama** — Kolay/Orta/Zor seviyede 1-5 arası çoktan seçmeli soru, şıklar karıştırılır
- 💬 **Soru çözdürme** — Yazılı veya fotoğraflı sorulara detaylı çözüm
- 📸 **Fotoğraf analizi** — Vision modeliyle görsel soru çözümü
- 📅 **Çalışma planı** — Kalan gün ve günlük çalışma saatine göre haftalık program
- 🤔 **"Anlamadım" & "Yanlış Cevap"** — Çözümü farklı yaklaşımla yeniden anlatır veya baştan çözer
- 💳 **Telegram Stars** ile abonelik ödemesi
- 🚀 **Yanıt streaming** — Cevaplar yazılırken gösterilir
- ⚡ **Model seçimi** — Matematik/Fizik/Kimya/Biyoloji/Türkçe için Sonnet, diğerleri için Haiku

### 📦 Kurulum

#### 1. Depoyu klonla
```bash
git clone https://github.com/Hasankr-27/sinav-botu.git
cd sinav-botu
```

#### 2. Sanal ortam oluştur
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

#### 3. Bağımlılıkları yükle
```bash
pip install -r requirements.txt
```

#### 4. Ortam değişkenlerini ayarla
`.env.example` dosyasını `.env` olarak kopyala ve doldur:
```bash
cp .env.example .env
```

Gerekli değerler:
- `TELEGRAM_TOKEN` — [BotFather](https://t.me/BotFather)'dan `/newbot` ile al
- `ANTHROPIC_API_KEY` — [console.anthropic.com](https://console.anthropic.com/settings/keys) üzerinden oluştur
- `DATABASE_URL` — PostgreSQL bağlantı URL'i (Railway, Supabase, Neon vs.)

#### 5. Botu çalıştır
```bash
python main.py
```

İlk çalıştırmada PostgreSQL tabloları otomatik oluşturulur.

### 💡 Kullanım

Botu başlattıktan sonra Telegram'da `/start` komutuyla kullan:

1. Hangi sınava hazırlandığını seç (YKS / KPSS / DGS / ALES / YDT)
2. Ne yapmak istediğini seç:
   - 📖 Konu Anlat
   - ❓ Soru Hazırla (ders → konu → zorluk → sayı)
   - 💬 Soru Çözdür (yazılı/fotoğraflı)
   - 📅 Çalışma Planı
3. Günlük mesaj hakkı: ücretsiz **4**, abone **50**
4. Abonelik: Telegram Stars ile (1 ay: 70⭐, 3 ay: 200⭐)
