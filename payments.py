from telegram import Update, LabeledPrice
from telegram.ext import ContextTypes

from database import abone_yap, kullanici_durumu
from config import ABONELIK_STARS, ABONELIK_FIYAT_TL, ABONELIK_GUN

# ───────────────────────────────────────────
# /abone KOMUTU — fatura gönder
# ───────────────────────────────────────────

async def abone_ol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    durum = kullanici_durumu(user_id)

    # Zaten abone mi?
    if durum["abone_mi"]:
        await update.message.reply_text(
            f"✅ Zaten abonesin!\n"
            f"Bitiş tarihi: {durum['abone_bitis_tarihi']}"
        )
        return

    # Telegram Stars faturası gönder
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="Sınav Asistanı — Aylık Abonelik",
        description=(
            f"✅ Günde {50} mesaj hakkı\n"
            f"✅ YKS, KPSS, DGS desteği\n"
            f"✅ {ABONELIK_GUN} gün geçerli\n"
            f"✅ Konu anlatım + soru hazırlama"
        ),
        payload="abonelik_30gun",
        currency="XTR",                          # XTR = Telegram Stars
        prices=[LabeledPrice("Aylık Abonelik", ABONELIK_STARS)],
    )


# ───────────────────────────────────────────
# ÖN ÖDEME KONTROLÜ
# ───────────────────────────────────────────

async def on_odeme_kontrol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telegram ödeme öncesi otomatik onay verir."""
    await update.pre_checkout_query.answer(ok=True)


# ───────────────────────────────────────────
# ÖDEME TAMAMLANDI
# ───────────────────────────────────────────

async def odeme_tamamlandi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ödeme başarılı → kullanıcıyı abone yap."""
    user_id = update.effective_user.id

    # Veritabanında abone yap
    abone_yap(user_id, gun=ABONELIK_GUN)

    await update.message.reply_text(
        "🎉 Ödeme alındı, hoş geldin!\n\n"
        f"✅ {ABONELIK_GUN} günlük aboneliğin aktif.\n"
        f"📚 Günde {50} mesaj hakkın var.\n\n"
        "Hemen başlamak için bir şeyler sor! 🚀"
    )