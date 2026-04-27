from collections import defaultdict
import time
import os
import base64

from anthropic import Anthropic
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from dotenv import load_dotenv

from database import (
    kullanici_olustur,
    kullanici_durumu,
    sinav_turu_guncelle,
    kalan_hak_azalt,
    gunluk_mesaj_kontrol,
    gunluk_mesaj_artir,
)

# YENİ FONKSİYONU DA BURAYA EKLEDİK (soru_hazirla)
from ai import intent_kontrol, ai_cevap_al, soru_hazirla

load_dotenv()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ───────────────────────────────────────────
# RATE LİMİTİNG
# ───────────────────────────────────────────

son_mesaj_zamani = defaultdict(float)
BEKLEME_SURESI = 3  # saniye

# ───────────────────────────────────────────
# HAZIR MESAJLAR
# ───────────────────────────────────────────

HAZIR_CEVAPLAR = {
    "merhaba": "👋 Merhaba! /start yazarak başlayabilirsin.",
    "selam": "👋 Selam! /start yazarak başlayabilirsin.",
    "fiyat": "💳 **Güncel Abonelik Paketleri:**\n\n• 1 Aylık Premium: 100 ⭐\n• 3 Aylık Premium: 250 ⭐ (Avantajlı Paket!)\n\nDetaylar ve satın alma için /paketler komutunu kullanabilirsin.",
    "ucret": "💳 **Abonelik Ücretleri:**\n\nSana özel 1 Aylık sadece 100 Yıldız! 🌟 Günde 3 Yıldız'dan bile ucuza geliyor. Hemen denemek için /paketler yaz.",
    "sen kimsin": "🤖 Ben YKS, KPSS, DGS, ALES ve diğer ÖSYM sınavlarında yardımcı olan bir sınav asistanıyım!",
}

ABONELIK_MESAJI = (
    "⛔ Ücretsiz hakkın bitti!\n\n"
    "📚 Devam etmek için abone ol:\n"
    "• Günde 50 mesaj hakkı\n"
    "• Aylık sadece 80 TL\n\n"
    "Abone olmak için /abone yaz."
)

LIMIT_MESAJI = (
    "⏰ Bugünlük 50 mesaj hakkını kullandın!\n"
    "Yarın sıfırlanacak. Yarın görüşürüz 💪"
)

ALAKASIZ_MESAJ = (
    "📚 Sadece sınav konularında yardımcı olabiliyorum.\n"
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
    context.user_data["sinav_turu"] = sinav  # Sınavı hafızada tutuyoruz

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
    sinav = context.user_data.get("sinav_turu", "YKS")

    # YENİ SİSTEM: Soru hazırlama seçildiyse dersleri listele
    if islem == "soru":
        dersler_sozlugu = {
            "YKS": ["Matematik", "Türkçe", "Fizik", "Kimya", "Biyoloji", "Tarih", "Coğrafya"],
            "KPSS": ["Matematik", "Türkçe", "Tarih", "Coğrafya", "Vatandaşlık", "Eğitim Bilimleri"],
            "DGS": ["Matematik", "Türkçe"],
            "ALES": ["Matematik", "Türkçe"]
        }

        aktif_dersler = dersler_sozlugu.get(sinav, ["Genel Yetenek", "Genel Kültür"])
        keyboard = []

        for i in range(0, len(aktif_dersler), 2):
            satir = [InlineKeyboardButton(aktif_dersler[i], callback_data=f"ders_{aktif_dersler[i]}")]
            if i + 1 < len(aktif_dersler):
                satir.append(InlineKeyboardButton(aktif_dersler[i + 1], callback_data=f"ders_{aktif_dersler[i + 1]}"))
            keyboard.append(satir)

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"📚 {sinav} sınavı için hangi dersten soru hazırlayayım?",
                                      reply_markup=reply_markup)
        return  # İşlemi burada kesiyoruz ki mesajlar sözlüğüne girmesin

    # Diğer normal işlemler
    mesajlar = {
        "konu": "📖 Hangi konuyu anlatmamı istersin?\nÖrnek: *türev*, *Atatürk ilkeleri*, *integral*",
        "plan": "📅 Sınava kaç günün var ve günde kaç saat çalışabilirsin?\nÖrnek: *60 gün, 4 saat*",
        "sor": "💬 Aklındaki soruyu yaz, cevaplayayım!\nÖrnek: *türev ne işe yarar*, *KPSS'de en çok hangi konular çıkıyor*",
    }

    context.user_data["beklenen_islem"] = islem

    await query.edit_message_text(
        mesajlar[islem],
        parse_mode="Markdown",
    )


# ───────────────────────────────────────────
# YENİ: DERS SEÇİLDİ (callback)
# ───────────────────────────────────────────

async def ders_secildi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    secilen_ders = query.data.replace("ders_", "")
    context.user_data["secilen_ders"] = secilen_ders
    context.user_data["durum"] = "KONU_BEKLENIYOR"  # Bot artık konuyu bekleyecek

    await query.edit_message_text(
        f"✅ Ders: **{secilen_ders}**\n\n"
        "Şimdi bana hangi konudan soru istediğini yaz.\n"
        "(Örn: Limit, Paragrafta Anlam, Kurtuluş Savaşı...)",
        parse_mode="Markdown"
    )


# ───────────────────────────────────────────
# YENİ: ADET SEÇİLDİ (callback) -> AI TETİKLENİR
# ───────────────────────────────────────────

async def adet_secildi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    adet = int(query.data.replace("adet_", ""))
    sinav = context.user_data.get("sinav_turu", "YKS")
    ders = context.user_data.get("secilen_ders", "Matematik")
    konu = context.user_data.get("secilen_konu", "Genel")

    user_id = update.effective_user.id
    durum = kullanici_durumu(user_id)
    abone_mi = durum["abone_mi"]

    # Hak kontrolü (Yapay zekaya gitmeden önce)
    if not abone_mi and durum["kalan_hak"] <= 0:
        await query.edit_message_text(ABONELIK_MESAJI)
        return
    if abone_mi and not gunluk_mesaj_kontrol(user_id):
        await query.edit_message_text(LIMIT_MESAJI)
        return

    await query.edit_message_text(
        f"🚀 {sinav} uzmanımız {adet} adet {ders} - {konu} sorusunu hazırlıyor...\n\nLütfen bekle...")

    try:
        cevap = soru_hazirla(sinav_turu=sinav, ders=ders, konu=konu, adet=adet, abone_mi=abone_mi)

        # Hakları düş
        if not abone_mi:
            kalan_hak_azalt(user_id)
        else:
            gunluk_mesaj_artir(user_id)

        await context.bot.send_message(chat_id=query.message.chat_id, text=cevap)
        context.user_data["durum"] = "BOSTA"  # İşlem bitti
        await _menu_goster(update, sinav)  # Menüyü geri çağır

    except Exception as e:
        await context.bot.send_message(chat_id=query.message.chat_id, text="Sistem yoğun kanka, birazdan tekrar dene!")
        context.user_data["durum"] = "BOSTA"
        print(f"Soru Hazırlama Hatası: {e}")


# ───────────────────────────────────────────
# MESAJ HANDLER (ana akış)
# ───────────────────────────────────────────

async def mesaj_isle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    metin = update.message.text.strip()
    metin_lower = metin.lower()

    # 0) YENİ SİSTEM: Konu bekleme durumu yakalayıcısı
    if context.user_data.get("durum") == "KONU_BEKLENIYOR":
        context.user_data["secilen_konu"] = metin
        context.user_data["durum"] = "ADET_BEKLENIYOR"

        keyboard = [[InlineKeyboardButton(str(i), callback_data=f"adet_{i}") for i in range(1, 6)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"🎯 Konu: {metin}\n\nKaç tane soru hazırlayayım? (Maksimum 5)",
                                        reply_markup=reply_markup)
        return  # Normal AI akışına girmemesi için işlemi kesiyoruz

    # 1) Rate limit kontrolü
    simdi = time.time()
    if simdi - son_mesaj_zamani[user_id] < BEKLEME_SURESI:
        await update.message.reply_text("⏳ Çok hızlı! Lütfen 3 saniye bekle.")
        return
    son_mesaj_zamani[user_id] = simdi

    # 2) Hazır cevap var mı?
    if metin_lower in HAZIR_CEVAPLAR:
        await update.message.reply_text(HAZIR_CEVAPLAR[metin_lower])
        return

    # 3) Kullanıcıyı oluştur / getir
    kullanici_olustur(user_id)
    durum = kullanici_durumu(user_id)

    # 4) Sınav türü seçilmiş mi?
    if not durum["sinav_turu"]:
        await update.message.reply_text(
            "⚠️ Önce sınav türünü seç!\n/start yazarak başlayabilirsin."
        )
        return

    # 5) Ücretsiz hak kontrolü
    if not durum["abone_mi"] and durum["kalan_hak"] <= 0:
        await update.message.reply_text(ABONELIK_MESAJI)
        return

    # 6) Günlük limit kontrolü (sadece aboneler için)
    if durum["abone_mi"] and not gunluk_mesaj_kontrol(user_id):
        await update.message.reply_text(LIMIT_MESAJI)
        return

        # 7) Intent filtre
        if not intent_kontrol(metin):
            await update.message.reply_text(ALAKASIZ_MESAJ)

            await _menu_goster(update, durum["sinav_turu"])
            return

    # 8) "Yazıyor..." göster
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    # 9) Normal AI Muhabbeti (Konu, Plan, Soru Sor vb.)
    sinav = durum["sinav_turu"]

    try:
        gecmis = context.user_data.get("sohbet_gecmisi", [])
        cevap = ai_cevap_al(metin, sinav, gecmis, durum["abone_mi"])

        gecmis.append({"role": "user", "content": metin})
        gecmis.append({"role": "assistant", "content": cevap})
        context.user_data["sohbet_gecmisi"] = gecmis[-10:]

        # 10) Hak / sayaç güncelle
        if not durum["abone_mi"]:
            kalan_hak_azalt(user_id)
            kalan = durum["kalan_hak"] - 1
            if kalan == 1:
                cevap += "\n\n⚠️ *Son ücretsiz hakkın!* Devam için /abone yaz."
            elif kalan == 0:
                cevap += "\n\n⛔ *Ücretsiz hakkın bitti.* Devam için /abone yaz."
        else:
            gunluk_mesaj_artir(user_id)

        # 11) Cevabı gönder + menüyü tekrar göster
        await update.message.reply_text(cevap, parse_mode="Markdown")
        await _menu_goster(update, sinav)

    except Exception as e:
        await update.message.reply_text("⚠️ Bir hata oluştu, tekrar dener misin?")
        print(f"Hata: {e}")


# ───────────────────────────────────────────
# YARDIMCI: menüyü tekrar göster
# ───────────────────────────────────────────

async def _menu_goster(update: Update, sinav: str):
    # Eğer update bir callback_query ise mesajı göndermek için query.message kullanmalıyız
    is_callback = hasattr(update, "callback_query") and update.callback_query is not None

    keyboard = [
        [
            InlineKeyboardButton("📖 Konu Anlat", callback_data="islem_konu"),
            InlineKeyboardButton("❓ Soru Hazırla", callback_data="islem_soru"),
        ],
        [
            InlineKeyboardButton("💬 Soru Sor", callback_data="islem_sor"),
            InlineKeyboardButton("📅 Çalışma Planı", callback_data="islem_plan"),
        ],
        [
            InlineKeyboardButton("🔄 Sınav Değiştir", callback_data="sinav_degistir"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"📚 {sinav} — Başka ne yapmak istersin?"

    if is_callback:
        await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)


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

    await query.edit_message_text(
        "Hangi sınava geçmek istersin?",
        reply_markup=reply_markup,
    )


# ───────────────────────────────────────────
# ESKİ CEVAP KONTROL (Şu an kullanılmıyor ama kalsın)
# ───────────────────────────────────────────

async def cevap_kontrol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    kullanici_cevabi = query.data.replace("cevap_", "")
    dogru_cevap = context.user_data.get("dogru_cevap")
    soru = context.user_data.get("son_soru")
    sinav = kullanici_durumu(query.from_user.id)["sinav_turu"]

    if kullanici_cevabi == dogru_cevap:
        await query.edit_message_text(
            f"{soru}\n\n✅ *Doğru! Tebrikler* 🎉",
            parse_mode="Markdown"
        )
    else:
        await context.bot.send_chat_action(
            chat_id=query.message.chat_id,
            action="typing"
        )

        aciklama = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": f"""Bu {sinav} sorusunda kullanıcı {kullanici_cevabi} şıkkını seçti ama doğru cevap {dogru_cevap}.
Soru: {soru}
Neden yanlış yaptığını kısaca açıkla ve doğru cevabı anlat. 3-4 cümle yeter, kısa tut."""
            }]
        ).content[0].text

        await query.edit_message_text(
            f"{soru}\n\n"
            f"❌ *Yanlış!* Seçtiğin: {kullanici_cevabi}\n"
            f"✅ *Doğru cevap: {dogru_cevap}*\n\n"
            f"📝 {aciklama}",
            parse_mode="Markdown"
        )


# ───────────────────────────────────────────
# FOTOĞRAF İŞLEME (abonelere özel)
# ───────────────────────────────────────────

async def fotograf_isle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    kullanici_olustur(user_id)
    durum = kullanici_durumu(user_id)

    if not durum["abone_mi"]:
        await update.message.reply_text(
            "📸 Fotoğrafla soru çözme sadece abonelere özel!\n"
            "Abone olmak için /abone yaz."
        )
        return

    if not gunluk_mesaj_kontrol(user_id):
        await update.message.reply_text(LIMIT_MESAJI)
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    try:
        foto = update.message.photo[-1]
        foto_dosyasi = await context.bot.get_file(foto.file_id)
        foto_bytes = await foto_dosyasi.download_as_bytearray()

        foto_base64 = base64.standard_b64encode(bytes(foto_bytes)).decode("utf-8")
        sinav = durum["sinav_turu"] or "ÖSYM"

        response = client.messages.create(
            model="claude-4-5-haiku",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": foto_base64,
                        }
                    },
                    {
                        "type": "text",
                        "text": f"Bu {sinav} sınav sorusunu çöz. Adım adım kısa açıkla, sonucu belirt."
                    }
                ]
            }]
        )

        cevap = response.content[0].text
        gunluk_mesaj_artir(user_id)

        await update.message.reply_text(cevap, parse_mode="Markdown")
        await _menu_goster(update, sinav)

    except Exception as e:
        await update.message.reply_text("⚠️ Fotoğraf işlenemedi, tekrar dener misin?")
        print(f"Fotoğraf hatası: {e}")