from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import abone_yap, kullanici_durumu
from config import ABONELIK_STARS, ABONELIK_3AY_STARS

# ───────────────────────────────────────────
# /abone KOMUTU — seçenek göster
# ───────────────────────────────────────────

async def abone_ol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    durum = kullanici_durumu(user_id)

    if durum["abone_mi"]:
        await update.message.reply_text(
            f"✅ Zaten abonesin!\n"
            f"Bitiş tarihi: {durum['abone_bitis_tarihi']}"
        )
        return

    keyboard = [
        [
            InlineKeyboardButton("1 Aylık — 50 ⭐", callback_data="odeme_1ay"),
            InlineKeyboardButton("3 Aylık — 150 ⭐", callback_data="odeme_3ay"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "💳 Abonelik seçenekleri:\n\n"
        "• 1 Aylık → 50 Stars\n"
        "• 3 Aylık → 150 Stars (%20 indirimli 🎉)\n\n"
        "Hangisini tercih edersin?",
        reply_markup=reply_markup,
    )


# ───────────────────────────────────────────
# ÖDEME SEÇİMİ (callback)
# ───────────────────────────────────────────

async def odeme_sec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    secim = query.data

    if secim == "odeme_1ay":
        stars = ABONELIK_STARS
        baslik = "1 Aylık Abonelik"
        aciklama = "✅ Günde 70 mesaj\n✅ 30 gün geçerli"
        gun = 30
    else:
        stars = ABONELIK_3AY_STARS
        baslik = "3 Aylık Abonelik"
        aciklama = "✅ Günde 70 mesaj\n✅ 90 gün geçerli\n✅ %20 indirimli 🎉"
        gun = 90

    context.user_data["abonelik_gun"] = gun

    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title=f"Sınav Asistanı — {baslik}",
        description=aciklama,
        payload=f"abonelik_{gun}gun",
        provider_token="",  # BAK BURASI ÇOK KRİTİK! Burayı böyle BOMBOŞ bırak kanka.
        currency="XTR",  # Yıldız birimi
        prices=[LabeledPrice(baslik, stars)],
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
    user_id = update.effective_user.id
    gun = context.user_data.get("abonelik_gun", 30)
    abone_yap(user_id, gun=gun)

    await update.message.reply_text(
        f"🎉 Ödeme alındı, hoş geldin!\n\n"
        f"✅ {gun} günlük aboneliğin aktif.\n"
        f"📚 Günde 70 mesaj hakkın var.\n\n"
        "Hemen başlamak için bir şeyler sor! 🚀"
    )