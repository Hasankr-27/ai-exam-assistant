import os
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    AIORateLimiter,
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
    geri_baslat,
    geri_menu,
    yanlis_cevap_handler,
)
from payments import abone_ol, on_odeme_kontrol, odeme_tamamlandi, odeme_sec

load_dotenv()


async def _api_test(app):
    """Bot başlarken tabloları oluşturur ve Anthropic API bağlantısını test eder."""
    await tablolari_olustur()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY ayarlanmamış! AI özellikleri çalışmaz.")
        return
    try:
        from anthropic import AsyncAnthropic
        test_client = AsyncAnthropic(api_key=api_key)
        await test_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=5,
            messages=[{"role": "user", "content": "test"}]
        )
        print("✅ Anthropic API bağlantısı başarılı.")
    except Exception as e:
        print(f"❌ Anthropic API HATASI: {type(e).__name__}: {e}")
        print("❌ ANTHROPIC_API_KEY geçerli mi? AI özellikleri çalışmayacak!")


def main():
    app = (
        ApplicationBuilder()
        .token(os.getenv("TELEGRAM_TOKEN"))
        .rate_limiter(AIORateLimiter())
        .post_init(_api_test)
        .build()
    )

    # ── Komutlar ──────────────────────────────
    app.add_handler(CommandHandler("baslat", baslat))
    app.add_handler(CommandHandler("start",  baslat))
    app.add_handler(CommandHandler("abone",  abone_ol))
    app.add_handler(CommandHandler("sorun",  sorun_bildir_komut))

    # ── Buton tıklamaları ─────────────────────
    app.add_handler(CallbackQueryHandler(sinav_sec,       pattern="^sinav_(YKS|KPSS|DGS|ALES|YDT|YDT_Ingilizce|YDT_Arapca|YDT_Almanca|YDT_Fransizca|YDT_Rusca)$"))
    app.add_handler(CallbackQueryHandler(sinav_degistir,  pattern="^sinav_degistir$"))
    app.add_handler(CallbackQueryHandler(islem_sec,       pattern="^islem_(konu|soru|sor|plan|sorun)$"))
    app.add_handler(CallbackQueryHandler(ders_sec,        pattern="^ders_.+$"))
    app.add_handler(CallbackQueryHandler(soru_sayisi_sec, pattern="^sayi_[1-5]$"))
    app.add_handler(CallbackQueryHandler(cevap_kontrol,   pattern="^cevap_\\d+_(A|B|C|D|E)$"))
    app.add_handler(CallbackQueryHandler(odeme_sec,       pattern="^odeme_(1ay|3ay)$"))
    app.add_handler(CallbackQueryHandler(sorun_bildir_handler, pattern="^sorun_bildir$"))
    app.add_handler(CallbackQueryHandler(geri_baslat,     pattern="^geri_baslat$"))
    app.add_handler(CallbackQueryHandler(geri_menu,           pattern="^geri_menu$"))
    app.add_handler(CallbackQueryHandler(yanlis_cevap_handler, pattern="^yanlis_cevap$"))

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