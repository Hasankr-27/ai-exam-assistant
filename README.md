# 🎯 Sınav Asistanı - Telegram Botu

YKS, KPSS, DGS, ALES ve YDT sınavlarına hazırlanan öğrenciler
için yapay zeka destekli Telegram botu.

## 📹 Demo

https://github.com/user-attachments/assets/58db7be1-ad8a-45a0-b517-adb68a82f1b2

## ✨ Özellikler
- 📖 Konu anlatımı (Claude Sonnet AI)
- ❓ Çoktan seçmeli soru hazırlama
- 📸 Fotoğrafla soru çözme
- 📅 Kişiselleştirilmiş çalışma planı
- 💳 Abonelik sistemi (Telegram Stars)
- 🔒 Rate limiting ve güvenlik

## 🛠️ Teknolojiler
- Python 3.13
- python-telegram-bot
- Anthropic Claude API
- PostgreSQL
- Railway (Deploy)

## ⚙️ Kurulum
1. Repoyu klonla
2. .env.example dosyasını .env olarak kopyala
3. API key'leri doldur
4. pip install -r requirements.txt
5. python main.py

## 📁 Proje Yapısı
- main.py - Ana bot dosyası
- handlers.py - Komut işleyiciler
- ai.py - Claude AI entegrasyonu
- database.py - PostgreSQL işlemleri
- payments.py - Ödeme sistemi
- config.py - Ayarlar
