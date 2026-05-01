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
    ders_sec,
    soru_sayisi_sec,
    mesaj_isle,
    sinav_degistir,
    cevap_kontrol,
    fotograf_isle,
    sorun_bildir_handler,
    sorun_bildir_komut,
)
from payments import abone_ol, on_odeme_kontrol, odeme_tamamlandi, odeme_sec

load_dotenv()


def main():
    tablolari_olustur()

    app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()

    # ── Komutlar ──────────────────────────────
    app.add_handler(CommandHandler("baslat", baslat))
    app.add_handler(CommandHandler("start",  baslat))
    app.add_handler(CommandHandler("abone",  abone_ol))
    app.add_handler(CommandHandler("sorun", sorun_bildir_komut))

    # ── Buton tıklamaları ─────────────────────
    app.add_handler(CallbackQueryHandler(sinav_sec,       pattern="^sinav_(YKS|KPSS|DGS|ALES|YDT|YDT_Ingilizce|YDT_Arapca|YDT_Almanca|YDT_Fransizca|YDT_Rusca)$"))
    app.add_handler(CallbackQueryHandler(sinav_degistir,  pattern="^sinav_degistir$"))
    app.add_handler(CallbackQueryHandler(islem_sec,       pattern="^islem_(konu|soru|sor|plan|sorun)$"))
    app.add_handler(CallbackQueryHandler(ders_sec,        pattern="^ders_.+$"))
    app.add_handler(CallbackQueryHandler(soru_sayisi_sec, pattern="^sayi_[1-5]$"))
    app.add_handler(CallbackQueryHandler(cevap_kontrol,   pattern="^cevap_\\d+_(A|B|C|D|E)$"))
    app.add_handler(CallbackQueryHandler(odeme_sec,       pattern="^odeme_(1ay|3ay)$"))
    app.add_handler(CallbackQueryHandler(sorun_bildir_handler, pattern="^sorun_bildir$"))

    # ── Ödeme ─────────────────────────────────
    app.add_handler(PreCheckoutQueryHandler(on_odeme_kontrol))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, odeme_tamamlandi))

    # ── Fotoğraf ──────────────────────────────
    app.add_handler(MessageHandler(filters.PHOTO, fotograf_isle))

    # ── Normal mesajlar ───────────────────────
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mesaj_isle))

    print("✅ Bot çalışıyor... Durdurmak için CTRL+C")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()