from collections import defaultdict
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    kullanici_olustur,
    kullanici_durumu,
    sinav_turu_guncelle,
    kalan_hak_azalt,
    gunluk_mesaj_kontrol,
    gunluk_mesaj_artir,
)
from ai import intent_kontrol, ai_cevap_al, soru_hazirla

# ───────────────────────────────────────────
# RATE LİMİTİNG
# ───────────────────────────────────────────

son_mesaj_zamani = defaultdict(float)
BEKLEME_SURESI = 3  # saniye

# ───────────────────────────────────────────
# HAZIR MESAJLAR
# ───────────────────────────────────────────

HAZIR_CEVAPLAR = {
    "merhaba":    "👋 Merhaba! /start yazarak başlayabilirsin.",
    "selam":      "👋 Selam! /start yazarak başlayabilirsin.",
    "fiyat":      "💳 Aylık abonelik 70 TL — günde sadece 2.3 TL!",
    "ucret":      "💳 Aylık abonelik 70 TL — günde sadece 2.3 TL!",
    "sen kimsin": "🤖 Ben YKS, KPSS ve DGS konularında yardımcı olan bir sınav asistanıyım!",
}

ABONELIK_MESAJI = (
    "⛔ Ücretsiz hakkın bitti!\n\n"
    "📚 Devam etmek için abone ol:\n"
    "• Günde 50 mesaj hakkı\n"
    "• Aylık sadece 70 TL\n\n"
    "Abone olmak için /abone yaz."
)

LIMIT_MESAJI = (
    "⏰ Bugünlük 50 mesaj hakkını kullandın!\n"
    "Yarın sıfırlanacak. Yarın görüşürüz 💪"
)

ALAKASIZ_MESAJ = (
    "📚 Sadece YKS, KPSS ve DGS konularında yardımcı olabiliyorum.\n"
    "Sınav ile ilgili bir şeyler sor!"
)


# ───────────────────────────────────────────
# /start KOMUTU
# ───────────────────────────────────────────

async def baslat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    isim = update.effective_user.first_name
    kullanici_olustur(update.effective_user.id)

    keyboard = [
        [
            InlineKeyboardButton("📘 YKS", callback_data="sinav_YKS"),
            InlineKeyboardButton("📗 KPSS", callback_data="sinav_KPSS"),
        ],
        [
            InlineKeyboardButton("📙 DGS", callback_data="sinav_DGS"),
            InlineKeyboardButton("📒 ALES", callback_data="sinav_ALES"),
        ],
        [
            InlineKeyboardButton("📓 Diğer", callback_data="sinav_DIGER"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"👋 Merhaba {isim}!\n\n"
        "Ben senin sınav asistanınım 🎯\n"
        "Hangi sınava hazırlanıyorsun?",
        reply_markup=reply_markup,
    )


# ───────────────────────────────────────────
# SINAV SEÇİMİ (callback)
# ───────────────────────────────────────────

async def sinav_sec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    sinav = query.data.replace("sinav_", "")
    sinav_turu_guncelle(user_id, sinav)

    keyboard = [
        [
            InlineKeyboardButton("📖 Konu Anlat", callback_data="islem_konu"),
            InlineKeyboardButton("❓ Soru Hazırla", callback_data="islem_soru"),
        ],
        [
            InlineKeyboardButton("📅 Çalışma Planı", callback_data="islem_plan"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"✅ {sinav} seçildi!\n\n"
        "Ne yapmak istersin?",
        reply_markup=reply_markup,
    )


# ───────────────────────────────────────────
# İŞLEM SEÇİMİ (callback)
# ───────────────────────────────────────────

async def islem_sec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    islem = query.data.replace("islem_", "")

    mesajlar = {
        "konu": "📖 Hangi konuyu anlatmamı istersin?\nÖrnek: *türev*, *Atatürk ilkeleri*, *integral*",
        "soru": "❓ Hangi konuda soru hazırlayayım?\nÖrnek: *limit*, *Osmanlı tarihi*, *paragraf*",
        "plan": "📅 Sınava kaç günün var ve günde kaç saat çalışabilirsin?\nÖrnek: *60 gün, 4 saat*",
    }

    context.user_data["beklenen_islem"] = islem

    await query.edit_message_text(
        mesajlar[islem],
        parse_mode="Markdown",
    )


# ───────────────────────────────────────────
# MESAJ HANDLER (ana akış)
# ───────────────────────────────────────────

async def mesaj_isle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    metin = update.message.text.lower().strip()

    # 0) Rate limit kontrolü
    simdi = time.time()
    if simdi - son_mesaj_zamani[user_id] < BEKLEME_SURESI:
        await update.message.reply_text("⏳ Çok hızlı! Lütfen 3 saniye bekle.")
        return
    son_mesaj_zamani[user_id] = simdi

    # 1) Hazır cevap var mı?
    if metin in HAZIR_CEVAPLAR:
        await update.message.reply_text(HAZIR_CEVAPLAR[metin])
        return

    # 2) Kullanıcıyı oluştur / getir
    kullanici_olustur(user_id)
    durum = kullanici_durumu(user_id)

    # 3) Sınav türü seçilmiş mi?
    if not durum["sinav_turu"]:
        await update.message.reply_text(
            "⚠️ Önce sınav türünü seç!\n/start yazarak başlayabilirsin."
        )
        return

    # 4) Ücretsiz hak kontrolü
    if not durum["abone_mi"] and durum["kalan_hak"] <= 0:
        await update.message.reply_text(ABONELIK_MESAJI)
        return

    # 5) Günlük limit kontrolü (sadece aboneler için)
    if durum["abone_mi"] and not gunluk_mesaj_kontrol(user_id):
        await update.message.reply_text(LIMIT_MESAJI)
        return

    # 6) Intent filtre
    if not intent_kontrol(metin):
        await update.message.reply_text(ALAKASIZ_MESAJ)
        return

    # 7) "Yazıyor..." göster
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    # 8) AI'a gönder
    beklenen = context.user_data.get("beklenen_islem", "genel")
    sinav = durum["sinav_turu"]

    try:
        if beklenen == "soru":
            cevap = soru_hazirla(metin, sinav)
            context.user_data["beklenen_islem"] = None
        else:
            gecmis = context.user_data.get("sohbet_gecmisi", [])
            cevap = ai_cevap_al(metin, sinav, gecmis)

            gecmis.append({"role": "user", "content": metin})
            gecmis.append({"role": "assistant", "content": cevap})
            context.user_data["sohbet_gecmisi"] = gecmis[-10:]

        # 9) Hak / sayaç güncelle
        if not durum["abone_mi"]:
            kalan_hak_azalt(user_id)
            kalan = durum["kalan_hak"] - 1

            if kalan == 1:
                cevap += "\n\n⚠️ *Son ücretsiz hakkın!* Devam için /abone yaz."
            elif kalan == 0:
                cevap += "\n\n⛔ *Ücretsiz hakkın bitti.* Devam için /abone yaz."
        else:
            gunluk_mesaj_artir(user_id)

        # 10) Cevabı gönder + menüyü tekrar göster
        await update.message.reply_text(cevap, parse_mode="Markdown")
        await _menu_goster(update, sinav)

    except Exception as e:
        await update.message.reply_text(
            "⚠️ Bir hata oluştu, tekrar dener misin?"
        )
        print(f"Hata: {e}")


# ───────────────────────────────────────────
# YARDIMCI: menüyü tekrar göster
# ───────────────────────────────────────────

async def _menu_goster(update: Update, sinav: str):
    keyboard = [
        [
            InlineKeyboardButton("📖 Konu Anlat", callback_data="islem_konu"),
            InlineKeyboardButton("❓ Soru Hazırla", callback_data="islem_soru"),
        ],
        [
            InlineKeyboardButton("📅 Çalışma Planı", callback_data="islem_plan"),
            InlineKeyboardButton("🔄 Sınav Değiştir", callback_data="sinav_degistir"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"📚 {sinav} — Başka ne yapmak istersin?",
        reply_markup=reply_markup,
    )


# ───────────────────────────────────────────
# SINAV DEĞİŞTİR (callback)
# ───────────────────────────────────────────

async def sinav_degistir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [
            InlineKeyboardButton("📘 YKS", callback_data="sinav_YKS"),
            InlineKeyboardButton("📗 KPSS", callback_data="sinav_KPSS"),
            InlineKeyboardButton("📙 DGS", callback_data="sinav_DGS"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "Hangi sınava geçmek istersin?",
        reply_markup=reply_markup,
    )