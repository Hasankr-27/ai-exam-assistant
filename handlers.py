from collections import defaultdict
from datetime import datetime
import time
import base64

from anthropic import Anthropic
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    kullanici_olustur,
    kullanici_durumu,
    sinav_turu_guncelle,
    kalan_hak_azalt,
    gunluk_mesaj_artir,
    mesaj_hakki_kontrol,
)
from ai import intent_kontrol, ai_cevap_al, soru_hazirla, SINAV_DERSLERI
import os
from dotenv import load_dotenv

load_dotenv()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ───────────────────────────────────────────
# RATE LİMİTİNG
# ───────────────────────────────────────────

son_mesaj_zamani = defaultdict(float)
BEKLEME_SURESI = 3

# ───────────────────────────────────────────
# HAZIR MESAJLAR
# ───────────────────────────────────────────

HAZIR_CEVAPLAR = {
    "merhaba":    "👋 Merhaba! /start yazarak başlayabilirsin.",
    "selam":      "👋 Selam! /start yazarak başlayabilirsin.",
    "fiyat":      "💳 Aylık abonelik 80 ⭐ — 3 aylık 250 ⭐!",
    "ucret":      "💳 Aylık abonelik 80 ⭐ — 3 aylık 250 ⭐!",
    "sen kimsin": "🤖 Ben YKS, KPSS, DGS, ALES ve diğer ÖSYM sınavlarında uzman bir asistanım!",
}

ABONELIK_MESAJI = (
    "⛔ Ücretsiz hakkın bitti!\n\n"
    "📚 Devam etmek için abone ol:\n"
    "• Günde 70 mesaj hakkı\n"
    "• 1 Aylık → 80 ⭐\n"
    "• 3 Aylık → 250 ⭐\n\n"
    "Abone olmak için /abone yaz."
)

LIMIT_MESAJI = (
    "⏰ Bugünlük mesaj hakkını kullandın!\n"
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

    keyboard = [
        [
            InlineKeyboardButton("📖 Konu Anlat", callback_data="islem_konu"),
            InlineKeyboardButton("❓ Soru Hazırla", callback_data="islem_soru"),
        ],
        [
            InlineKeyboardButton("💬 Soru Sor", callback_data="islem_sor"),
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
    user_id = query.from_user.id
    durum = kullanici_durumu(user_id)
    sinav = durum["sinav_turu"] or "YKS"

    # Soru hazırla → önce dersler çıksın
    if islem == "soru":
        dersler = SINAV_DERSLERI.get(sinav, {})
        keyboard = []
        ders_listesi = list(dersler.keys())

        # İkili buton sırala
        for i in range(0, len(ders_listesi), 2):
            satir = [InlineKeyboardButton(ders_listesi[i], callback_data=f"ders_{ders_listesi[i]}")]
            if i + 1 < len(ders_listesi):
                satir.append(InlineKeyboardButton(ders_listesi[i+1], callback_data=f"ders_{ders_listesi[i+1]}"))
            keyboard.append(satir)

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"📚 {sinav} — Hangi dersten soru hazırlayayım?",
            reply_markup=reply_markup,
        )
        return

    mesajlar = {
        "konu": "📖 Hangi konuyu anlatmamı istersin?\nÖrnek: *türev*, *Atatürk ilkeleri*, *integral*",
        "sor":  "💬 Aklındaki soruyu yaz, cevaplayayım!\nÖrnek: *türev ne işe yarar*, *KPSS'de en çok hangi konular çıkıyor*",
        "plan": "📅 Sınava kaç günün var ve günde kaç saat çalışabilirsin?\nÖrnek: *60 gün, 4 saat*",
        "sorun": "🚨 Sorununu yaz, en kısa sürede inceleyeceğim!",
    }

    context.user_data["beklenen_islem"] = islem

    await query.edit_message_text(
        mesajlar.get(islem, "Ne yapmak istersin?"),
        parse_mode="Markdown",
    )


# ───────────────────────────────────────────
# DERS SEÇİMİ (callback)
# ───────────────────────────────────────────

async def ders_sec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    ders = query.data.replace("ders_", "")
    context.user_data["secilen_ders"] = ders
    context.user_data["beklenen_islem"] = "soru"

    await query.edit_message_text(
        f"✅ *{ders}* seçildi!\n\n"
        "📝 Hangi konudan soru hazırlayayım?",
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

    hak_durumu = mesaj_hakki_kontrol(user_id, durum["abone_mi"])

    # 4) Ücretsiz hak kontrolü
    if not durum["abone_mi"] and not hak_durumu["izin_ver"]:
        await update.message.reply_text(
            "⏰ Bugünlük 7 ücretsiz hakkını doldurdun!\n\n"
            "Gece 00:00'da hakların otomatik olarak yenilenecek. Hiç beklemeden devam etmek istersen /abone yazarak günlük 70 hakka geçebilirsin! 🚀"
        )
        return

    # 5) Günlük limit kontrolü
    if durum["abone_mi"] and not hak_durumu["izin_ver"]:
        await update.message.reply_text(LIMIT_MESAJI)
        return

    # 6) Intent filtre
    if not intent_kontrol(metin):
        await update.message.reply_text(ALAKASIZ_MESAJ)
        await _menu_goster(update, durum["sinav_turu"])
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    beklenen = context.user_data.get("beklenen_islem", "genel")
    sinav = durum["sinav_turu"]

    try:
        # ── SORU KONUSU GELDİ → kaç soru sor ──
        if beklenen == "soru" and context.user_data.get("secilen_ders"):
            context.user_data["soru_konusu"] = metin
            context.user_data["beklenen_islem"] = "soru_sayi"

            keyboard = [[
                InlineKeyboardButton("1", callback_data="sayi_1"),
                InlineKeyboardButton("2", callback_data="sayi_2"),
                InlineKeyboardButton("3", callback_data="sayi_3"),
                InlineKeyboardButton("4", callback_data="sayi_4"),
                InlineKeyboardButton("5", callback_data="sayi_5"),
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"📝 *{metin}* konusunda kaç soru hazırlayayım?",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            return

        # ── NORMAL SOHBET ──
        else:
            gecmis = context.user_data.get("sohbet_gecmisi", [])
            cevap = ai_cevap_al(metin, sinav, gecmis, durum["abone_mi"])

            gecmis.append({"role": "user", "content": metin})
            gecmis.append({"role": "assistant", "content": cevap})
            context.user_data["sohbet_gecmisi"] = gecmis[-10:]

            # Hak güncelle
            gunluk_mesaj_artir(user_id)

            if not durum["abone_mi"]:
                kalan = hak_durumu["kalan"] - 1
                if kalan == 1:
                    cevap += "\n\n⚠️ *Bugünlük son ücretsiz hakkın!* Devam için /abone yaz."
                elif kalan == 0:
                    cevap += "\n\n⛔ *Bugünlük ücretsiz hakkın bitti.* Yarın yenilenecek veya /abone yazabilirsin."

        await update.message.reply_text(cevap, parse_mode="Markdown")
        await _menu_goster(update, sinav)

    except Exception as e:
        await update.message.reply_text("⚠️ Bir hata oluştu, tekrar dener misin?")
        print(f"Hata: {e}")


# ───────────────────────────────────────────
# SORU SAYISI SEÇİMİ (callback)
# ───────────────────────────────────────────

import json
import asyncio


async def soru_sayisi_sec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    sayi = int(query.data.replace("sayi_", ""))
    konu = context.user_data.get("soru_konusu", "")
    ders = context.user_data.get("secilen_ders", "")
    user_id = query.from_user.id
    durum = kullanici_durumu(user_id)
    sinav = durum["sinav_turu"]
    model = "claude-sonnet-4-5" if durum["abone_mi"] else "claude-haiku-4-5"

    await query.edit_message_text(f"⏳ Senin için tam {sayi} adet yepyeni soru hazırlıyorum, biraz bekle...")

    # --- GEÇMİŞ SORU KONTROLÜ (AYNI SORULARI SORMAMASI İÇİN) ---
    gecmis_sorular = context.user_data.get("gecmis_sorular", [])
    gecmis_metin = ""
    if gecmis_sorular:
        # Prompt çok uzamasın diye sadece son 10 sorunun metnini Claude'a veriyoruz
        son_sorular = gecmis_sorular[-10:]
        gecmis_metin = f"\nÖNEMLİ: Daha önce kullanıcıya şu soruları sordun. LÜTFEN BUNLARA BENZEMEYEN, TAMAMEN FARKLI YENİ SORULAR ÜRET:\n" + "\n".join(
            son_sorular)

    prompt = f"""
{sinav} sınavı {ders} dersi {konu} konusu ile ilgili {sayi} adet çoktan seçmeli soru hazırla.{gecmis_metin}

Sadece ama sadece geçerli bir JSON array formatında çıktı ver. Başka hiçbir şey yazma.
Format tamamen şu şekilde olmalı:
[
  {{
    "soru": "Soru metni buraya...\nA) ...\nB) ...\nC) ...\nD) ...\nE) ...",
    "cevap": "A",
    "cozum": "Doğru cevabın neden A olduğuna dair 2-3 cümlelik kısa, net çözüm açıklaması."
  }}
]
"""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}]
        )

        ciktı = response.content[0].text.strip()

        if ciktı.startswith("```json"):
            ciktı = ciktı[7:-3].strip()
        elif ciktı.startswith("```"):
            ciktı = ciktı[3:-3].strip()

        sorular = json.loads(ciktı)

        for i, soru_data in enumerate(sorular):
            context.user_data[f"soru_{i}"] = soru_data["soru"]
            context.user_data[f"cevap_{i}"] = soru_data["cevap"]
            context.user_data[f"cozum_{i}"] = soru_data["cozum"]

            # Üretilen her yeni soruyu geçmiş listemize ekliyoruz
            gecmis_sorular.append(soru_data["soru"])

        # Geçmişi context'e geri kaydediyoruz
        context.user_data["gecmis_sorular"] = gecmis_sorular

        context.user_data["toplam_soru"] = len(sorular)
        context.user_data["beklenen_islem"] = None
        context.user_data["secilen_ders"] = None

        await _soru_gonder(query.message.chat_id, context, 0)

        # Herkes için ortak sayacı artır
        gunluk_mesaj_artir(user_id)

    except json.JSONDecodeError:
        await query.edit_message_text(
            "⚠️ Yapay zeka soruları oluştururken bir format hatası yaptı. Lütfen tekrar sayı seçerek dene.")
    except Exception as e:
        print(f"Hata: {e}")
        await query.edit_message_text("⚠️ Beklenmeyen bir hata oluştu, tekrar dener misin?")


async def _soru_gonder(chat_id, context, index):
    soru = context.user_data.get(f"soru_{index}", "")
    toplam = context.user_data.get("toplam_soru", 1)

    keyboard = [[
        InlineKeyboardButton("A", callback_data=f"cevap_{index}_A"),
        InlineKeyboardButton("B", callback_data=f"cevap_{index}_B"),
        InlineKeyboardButton("C", callback_data=f"cevap_{index}_C"),
        InlineKeyboardButton("D", callback_data=f"cevap_{index}_D"),
        InlineKeyboardButton("E", callback_data=f"cevap_{index}_E"),
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"📊 Soru {index+1}/{toplam}\n\n{soru}",
        reply_markup=reply_markup,

    )


# ───────────────────────────────────────────
# CEVAP KONTROL (callback)
# ───────────────────────────────────────────

async def cevap_kontrol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # KRİTİK: Kullanıcı butona basar basmaz butonları siliyoruz ki 2 kere basamasın!
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    veri = query.data
    parcalar = veri.split("_")

    index = int(parcalar[1])
    kullanici_cevabi = parcalar[2]

    dogru_cevap = context.user_data.get(f"cevap_{index}")
    soru = context.user_data.get(f"soru_{index}")
    cozum = context.user_data.get(f"cozum_{index}") # Hazırladığımız çözümü çektik
    toplam = context.user_data.get("toplam_soru", 1)

    if dogru_cevap is None:
        await query.edit_message_text("⚠️ Bot yeniden başladı, sorular sıfırlandı.\nLütfen yeni soru hazırlat!")
        return

    # Eğer cevap doğruysa
    if kullanici_cevabi == dogru_cevap:
        mesaj = f"📊 Soru {index + 1}/{toplam}\n\n{soru}\n\n✅ Doğru! Tebrikler 🎉\n\n📝 Çözüm: {cozum}"
    # Eğer cevap yanlışsa (API'ye bağlanmak yok, anında cevap!)
    else:
        mesaj = (
            f"📊 Soru {index + 1}/{toplam}\n\n{soru}\n\n"
            f"❌ Yanlış! Seçtiğin: {kullanici_cevabi}\n"
            f"✅ Doğru: {dogru_cevap}\n\n"
            f"📝 Çözüm: {cozum}"
        )

    # Eski soruyu çözüm ve doğru/yanlış durumuyla güncelliyoruz
    await query.edit_message_text(mesaj)

    # Bir sonraki soru varsa O ZAMAN tek bir yeni soru olarak gönderiyoruz
    if index + 1 < toplam:
        await _soru_gonder(query.message.chat_id, context, index + 1)
    # Sorular bittiyse menüyü gösteriyoruz
    else:
        durum = kullanici_durumu(query.from_user.id)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="🎉 Test bitti! Sonuçlarını yukarıdan inceleyebilirsin."
        )
        await _menu_goster_chat(query.message.chat_id, context, durum["sinav_turu"])


# ───────────────────────────────────────────
# YARDIMCI: menü göster
# ───────────────────────────────────────────

async def _menu_goster(update: Update, sinav: str):
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
            InlineKeyboardButton("🚨 Sorun Bildir", callback_data="islem_sorun"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"📚 {sinav} — Başka ne yapmak istersin?",
        reply_markup=reply_markup,
    )


async def _menu_goster_chat(chat_id, context, sinav: str):
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
            InlineKeyboardButton("🚨 Sorun Bildir", callback_data="islem_sorun"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"📚 {sinav} — Başka ne yapmak istersin?",
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
# FOTOĞRAF İŞLEME (abonelere özel)
# ───────────────────────────────────────────

# ───────────────────────────────────────────
# FOTOĞRAF İŞLEME (abonelere ve ücretsizlere limitli)
# ───────────────────────────────────────────

async def fotograf_isle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    kullanici_olustur(user_id)
    durum = kullanici_durumu(user_id)

    # 1) Genel Günlük Limit Kontrolü (Ortak havuz: 7 veya 70)
    hak_durumu = mesaj_hakki_kontrol(user_id, durum["abone_mi"])
    if not hak_durumu["izin_ver"]:
        if durum["abone_mi"]:
            await update.message.reply_text(LIMIT_MESAJI)
        else:
            await update.message.reply_text(
                "⏰ Bugünlük 7 ücretsiz hakkını doldurdun!\n\n"
                "Gece 00:00'da hakların yenilenecek. Devam etmek için /abone olabilirsin."
            )
        return

    # 2) FOTOĞRAF LİMİTİ KONTROLÜ (Maliyet Koruması)
    bugun = datetime.now().strftime("%Y-%m-%d")
    foto_kullanimi = context.user_data.get(f"foto_{bugun}", 0)

    # Aboneye günde 15 fotoğraf, ücretsiz kullanıcıya 3 fotoğraf hakkı
    foto_limiti = 15 if durum["abone_mi"] else 3

    if foto_kullanimi >= foto_limiti:
        if durum["abone_mi"]:
            await update.message.reply_text(
                f"📸 Aboneler için günlük {foto_limiti} fotoğraf çözüm sınırına ulaştın!\n\n"
                "Yapay zeka görsel işleme maliyetlerinden dolayı bir sınırımız var. Ancak günlük kalan hakkınla metin olarak soru sormaya devam edebilirsin! Yarın fotoğraf hakkın yenilenecek."
            )
        else:
            await update.message.reply_text(
                f"📸 Bugünlük {foto_limiti} adet ücretsiz fotoğraf hakkını doldurdun!\n\n"
                "Yarın tekrar deneyebilir veya fotoğraf limitini artırmak için /abone olabilirsin! 🚀"
            )
        return

    # Hakkı varsa bugünkü fotoğraf sayacını 1 artırıyoruz
    context.user_data[f"foto_{bugun}"] = foto_kullanimi + 1

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        foto = update.message.photo[-1]
        foto_dosyasi = await context.bot.get_file(foto.file_id)
        foto_bytes = await foto_dosyasi.download_as_bytearray()
        foto_base64 = base64.standard_b64encode(bytes(foto_bytes)).decode("utf-8")

        sinav = durum["sinav_turu"] or "ÖSYM"

        response = client.messages.create(
            model="claude-sonnet-4-5",
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
                        "text": f"Bu {sinav} sınav sorusunu adım adım çöz. Kısa ve net açıkla, sonucu belirt."
                    }
                ]
            }]
        )

        cevap = response.content[0].text

        # Ana havuzdan (7 veya 70 limitinden) hakkı düşüyoruz
        gunluk_mesaj_artir(user_id)

        await update.message.reply_text(cevap, parse_mode="Markdown")
        await _menu_goster(update, sinav)

    except Exception as e:
        await update.message.reply_text(
            "⚠️ Fotoğraf işlenemedi, fotoğrafın net olduğundan emin olup tekrar dener misin?")
        print(f"Fotoğraf hatası: {e}")