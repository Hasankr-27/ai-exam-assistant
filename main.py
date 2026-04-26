import os
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    filters,
)

from database import tablolari_olustur
from handlers import (
    baslat,
    sinav_sec,
    islem_sec,
    mesaj_isle,
    sinav_degistir,
)
from payments import abone_ol, on_odeme_kontrol, odeme_tamamlandi

load_dotenv()


def main():
    # Veritabanı tablolarını oluştur
    tablolari_olustur()

    # Botu oluştur
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()

    # ── Komutlar ──────────────────────────────
    app.add_handler(CommandHandler("baslat", baslat))
    app.add_handler(CommandHandler("start", baslat))
    app.add_handler(CommandHandler("abone", abone_ol))

    # ── Buton tıklamaları (callback) ──────────
    app.add_handler(CallbackQueryHandler(sinav_sec,      pattern="^sinav_(YKS|KPSS|DGS)$"))
    app.add_handler(CallbackQueryHandler(sinav_degistir, pattern="^sinav_degistir$"))
    app.add_handler(CallbackQueryHandler(islem_sec,      pattern="^islem_(konu|soru|plan)$"))

    # ── Ödeme ─────────────────────────────────
    app.add_handler(PreCheckoutQueryHandler(on_odeme_kontrol))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, odeme_tamamlandi))

    # ── Normal mesajlar ───────────────────────
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mesaj_isle))

    # ── Botu başlat ───────────────────────────
    print("✅ Bot çalışıyor... Durdurmak için CTRL+C")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()