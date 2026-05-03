from collections import defaultdict
from datetime import datetime
import time
import base64
import json

from anthropic import Anthropic
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    kullanici_olustur,
    kullanici_durumu,
    sinav_turu_guncelle,
    gunluk_mesaj_artir,
    mesaj_hakki_kontrol,
)
from ai import intent_kontrol, ai_cevap_al, SINAV_DERSLERI, konu_dogrula, calisma_plani_olustur
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
    "fiyat":      "💳 Aylık abonelik 80 ⭐ — 3 aylık 200 ⭐!",
    "ucret":      "💳 Aylık abonelik 80 ⭐ — 3 aylık 200 ⭐!",
    "sen kimsin": "🤖 Ben YKS, KPSS, DGS, ALES, YDT sınavlarında uzman bir asistanım!",
}

ABONELIK_MESAJI = (
    "⛔ Ücretsiz hakkın bitti!\n\n"
    "📚 Devam etmek için abone ol:\n"
    "• Günde 70 mesaj hakkı\n"
    "• 1 Aylık → 80 ⭐\n"
    "• 3 Aylık → 200 ⭐\n\n"
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

MENU_SEC_MESAJI = (
    "👆 Lütfen önce menüden bir seçenek seç!\n"
    "Konu Anlat, Soru Hazırla, Soru Çözdür veya Çalışma Planı."
)


# ───────────────────────────────────────────
# /start KOMUTU
# ───────────────────────────────────────────

async def baslat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    isim = update.effective_user.first_name
    kullanici_olustur(update.effective_user.id)
    context.user_data["beklenen_islem"] = None

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
            InlineKeyboardButton("📓 YDT", callback_data="sinav_YDT"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"👋 Merhaba {isim}!\n\n"
        "🎯 *Sınav Asistanına Hoş Geldin!*\n\n"
        "📚 Yapay zeka destekli asistanın ile:\n"
        "✅ Konu anlatımı al\n"
        "✅ Soru hazırlat ve çöz\n"
        "✅ Çalışma planı oluştur\n"
        "✅ Takıldığın soruyu çözdür\n\n"
        "👇 Hangi sınava hazırlanıyorsun?",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


# ───────────────────────────────────────────
# SINAV SEÇİMİ (callback)
# ───────────────────────────────────────────

async def sinav_sec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    sinav = query.data.replace("sinav_", "")

    # YDT → dil seçimi
    if sinav == "YDT":
        keyboard = [
            [
                InlineKeyboardButton("🇬🇧 İngilizce", callback_data="sinav_YDT_Ingilizce"),
                InlineKeyboardButton("🇸🇦 Arapça", callback_data="sinav_YDT_Arapca"),
            ],
            [
                InlineKeyboardButton("🇩🇪 Almanca", callback_data="sinav_YDT_Almanca"),
                InlineKeyboardButton("🇫🇷 Fransızca", callback_data="sinav_YDT_Fransizca"),
            ],
            [
                InlineKeyboardButton("🇷🇺 Rusça", callback_data="sinav_YDT_Rusca"),
            ],
            [
                InlineKeyboardButton("🔙 Geri", callback_data="geri_baslat"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📓 YDT — Hangi dili seçiyorsun?",
            reply_markup=reply_markup,
        )
        return

    sinav_turu_guncelle(user_id, sinav)
    context.user_data["beklenen_islem"] = None
    await _menu_goster_query(query, sinav)


# ───────────────────────────────────────────
# MENÜ GÖSTER (query ile)
# ───────────────────────────────────────────

async def _menu_goster_query(query, sinav: str):
    keyboard = [
        [
            InlineKeyboardButton("📖 Konu Anlat", callback_data="islem_konu"),
            InlineKeyboardButton("❓ Soru Hazırla", callback_data="islem_soru"),
        ],
        [
            InlineKeyboardButton("💬 Soru Çözdür", callback_data="islem_sor"),
            InlineKeyboardButton("📅 Çalışma Planı", callback_data="islem_plan"),
        ],
        [
            InlineKeyboardButton("🔄 Sınav Değiştir", callback_data="sinav_degistir"),
            InlineKeyboardButton("🚨 Sorun Bildir", callback_data="sorun_bildir"),
        ],
        [
            InlineKeyboardButton("🔙 Geri", callback_data="geri_baslat"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"✅ {sinav} seçildi!\n\nNe yapmak istersin?",
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

        for i in range(0, len(ders_listesi), 2):
            satir = [InlineKeyboardButton(ders_listesi[i], callback_data=f"ders_{ders_listesi[i]}")]
            if i + 1 < len(ders_listesi):
                satir.append(InlineKeyboardButton(ders_listesi[i+1], callback_data=f"ders_{ders_listesi[i+1]}"))
            keyboard.append(satir)

        keyboard.append([InlineKeyboardButton("🔙 Geri", callback_data="geri_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"📚 {sinav} — Hangi dersten soru hazırlayayım?",
            reply_markup=reply_markup,
        )
        return

    mesajlar = {
        "konu": "📖 Hangi konuyu anlatmamı istersin?\nÖrnek: *türev*, *Atatürk ilkeleri*, *paragraf*",
        "sor":  "💬 Sorunuzu yazın, çözeyim!\nÖrnek: *2x + 3 = 7 denklemini çöz*\nFotoğraf da atabilirsin 📸",
        "plan": "📅 Sınava kaç günün var ve günde kaç saat çalışabilirsin?\nÖrnek: *60 gün, 4 saat*",
        "sorun": "🚨 Sorununu şu adrese ilet:\nt.me/Hsn_0134\n\nDirekt mesaj atabilirsin!",
    }

    context.user_data["beklenen_islem"] = islem

    keyboard = [[InlineKeyboardButton("🔙 Geri", callback_data="geri_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        mesajlar.get(islem, "Ne yapmak istersin?"),
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


# ───────────────────────────────────────────
# GERİ TUŞLARI (callback)
# ───────────────────────────────────────────

async def geri_baslat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["beklenen_islem"] = None

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
            InlineKeyboardButton("📓 YDT", callback_data="sinav_YDT"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "👇 Hangi sınava hazırlanıyorsun?",
        reply_markup=reply_markup,
    )


async def geri_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["beklenen_islem"] = None
    durum = kullanici_durumu(query.from_user.id)
    sinav = durum["sinav_turu"] or "YKS"
    await _menu_goster_query(query, sinav)


# ───────────────────────────────────────────
# DERS SEÇİMİ (callback)
# ───────────────────────────────────────────

async def ders_sec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    ders = query.data.replace("ders_", "")
    context.user_data["secilen_ders"] = ders
    context.user_data["beklenen_islem"] = "soru"

    keyboard = [[InlineKeyboardButton("🔙 Geri", callback_data="geri_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"✅ *{ders}* seçildi!\n\n"
        "📝 Hangi konudan soru hazırlayayım?",
        reply_markup=reply_markup,
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

    # 4) Hak kontrolü
    hak_durumu = mesaj_hakki_kontrol(user_id, durum["abone_mi"])

    if not durum["abone_mi"] and not hak_durumu["izin_ver"]:
        await update.message.reply_text(
            "⏰ Bugünlük 7 ücretsiz hakkını doldurdun!\n\n"
            "Gece 00:00'da hakların yenilenecek. Devam için /abone yazabilirsin! 🚀"
        )
        return

    if durum["abone_mi"] and not hak_durumu["izin_ver"]:
        await update.message.reply_text(LIMIT_MESAJI)
        return

    # 5) beklenen ve sinav
    beklenen = context.user_data.get("beklenen_islem", None)
    sinav = durum["sinav_turu"]

    # 6) Menüden seçim yapılmamışsa engelle
    if not beklenen:
        keyboard = [
            [
                InlineKeyboardButton("📖 Konu Anlat", callback_data="islem_konu"),
                InlineKeyboardButton("❓ Soru Hazırla", callback_data="islem_soru"),
            ],
            [
                InlineKeyboardButton("💬 Soru Çözdür", callback_data="islem_sor"),
                InlineKeyboardButton("📅 Çalışma Planı", callback_data="islem_plan"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            MENU_SEC_MESAJI,
            reply_markup=reply_markup,
        )
        return

    # 7) Intent filtre - sadece genel sohbette
    if beklenen == "genel" and not intent_kontrol(metin):
        await update.message.reply_text(ALAKASIZ_MESAJ)
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        # ── SORU KONUSU GELDİ ──
        if beklenen == "soru" and context.user_data.get("secilen_ders"):
            ders = context.user_data.get("secilen_ders")
            if not konu_dogrula(metin, ders, sinav):
                await update.message.reply_text(
                    f"⚠️ *{metin}* konusu {sinav} {ders} müfredatında yok!\n\n"
                    "Lütfen geçerli bir konu yaz.",
                    parse_mode="Markdown"
                )
                return

            context.user_data["soru_konusu"] = metin

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

        # ── ÇALIŞMA PLANI ──
        if beklenen == "plan":
            try:
                parcalar = metin.replace(" ", "").split(",")
                gun = int(''.join(filter(str.isdigit, parcalar[0])))
                saat = int(''.join(filter(str.isdigit, parcalar[1])))
                cevap = calisma_plani_olustur(gun, saat, sinav, durum["abone_mi"])
                context.user_data["beklenen_islem"] = None
            except:
                await update.message.reply_text(
                    "⚠️ Şu formatta yaz:\n*47 gün, 7 saat*",
                    parse_mode="Markdown"
                )
                return

        # ── KONU ANLAT / SORU ÇÖZDÜR / GENEL ──
        else:
            gecmis = context.user_data.get("sohbet_gecmisi", [])
            # Herkes için Sonnet kullan (doğruluk için)
            cevap = ai_cevap_al(metin, sinav, gecmis, True)

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

        try:
            await update.message.reply_text(cevap, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(cevap)
        await _menu_goster(update, sinav)

    except Exception as e:
        await update.message.reply_text("⚠️ Bir hata oluştu, tekrar dener misin?")
        print(f"Hata: {e}")


# ───────────────────────────────────────────
# SORU SAYISI SEÇİMİ (callback)
# ───────────────────────────────────────────

async def soru_sayisi_sec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    sayi = int(query.data.replace("sayi_", ""))
    konu = context.user_data.get("soru_konusu", "")
    ders = context.user_data.get("secilen_ders", "")
    user_id = query.from_user.id
    durum = kullanici_durumu(user_id)
    sinav = durum["sinav_turu"]

    await query.edit_message_text(f"⏳ {sayi} soru hazırlanıyor...")

    gecmis_sorular = context.user_data.get("gecmis_sorular", [])
    gecmis_metin = ""
    if gecmis_sorular:
        son_sorular = gecmis_sorular[-10:]
        gecmis_metin = f"\nÖNEMLİ: Daha önce şu soruları sordun, BUNLARA BENZEMEYEN sorular üret:\n" + "\n".join(son_sorular)

    prompt = f"""
Sen bir {sinav} sınav uzmanısın. SADECE {sinav} sınavının {ders} dersinden soru hazırlıyorsun.
{sinav} {ders} müfredatı dışına KESINLIKLE çıkma!

{sinav} sınavı {ders} dersi {konu} konusu ile ilgili {sayi} adet çoktan seçmeli soru hazırla.{gecmis_metin}

ÖNEMLİ KURALLAR:
- Her soruyu hazırlamadan önce cevabını kendин hesapla/doğrula
- Doğru cevap şıklarda MUTLAKA bulunmalı
- Yanlış şıklar makul ama kesinlikle yanlış olmalı
- Gerçek {sinav} sınav zorluk seviyesinde olsun
- Sorular birbirinden farklı alt konuları kapsasın

Sadece geçerli bir JSON array formatında çıktı ver. Başka hiçbir şey yazma.
[
  {{
    "soru": "Soru metni...\\nA) ...\\nB) ...\\nC) ...\\nD) ...\\nE) ...",
    "cevap": "A",
    "cozum": "Adım adım çözüm: neden bu cevap doğru, diğerleri neden yanlış."
  }}
]
"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )

        cikti = response.content[0].text.strip()

        if cikti.startswith("```json"):
            cikti = cikti[7:-3].strip()
        elif cikti.startswith("```"):
            cikti = cikti[3:-3].strip()

        sorular = json.loads(cikti)

        for i, soru_data in enumerate(sorular):
            context.user_data[f"soru_{i}"] = soru_data["soru"]
            context.user_data[f"cevap_{i}"] = soru_data["cevap"]
            context.user_data[f"cozum_{i}"] = soru_data["cozum"]
            gecmis_sorular.append(soru_data["soru"])

        context.user_data["gecmis_sorular"] = gecmis_sorular
        context.user_data["toplam_soru"] = len(sorular)
        context.user_data["beklenen_islem"] = None
        context.user_data["secilen_ders"] = None

        await _soru_gonder(query.message.chat_id, context, 0)
        gunluk_mesaj_artir(user_id)

    except json.JSONDecodeError:
        await query.edit_message_text("⚠️ Format hatası, tekrar dener misin?")
    except Exception as e:
        print(f"Hata: {e}")
        await query.edit_message_text("⚠️ Bir hata oluştu, tekrar dener misin?")


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

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    parcalar = query.data.split("_")
    index = int(parcalar[1])
    kullanici_cevabi = parcalar[2]

    dogru_cevap = context.user_data.get(f"cevap_{index}")
    soru = context.user_data.get(f"soru_{index}")
    cozum = context.user_data.get(f"cozum_{index}")
    toplam = context.user_data.get("toplam_soru", 1)

    if dogru_cevap is None:
        await query.edit_message_text("⚠️ Bot yeniden başladı, lütfen yeni soru hazırlat!")
        return

    if kullanici_cevabi == dogru_cevap:
        mesaj = f"📊 Soru {index+1}/{toplam}\n\n{soru}\n\n✅ Doğru! Tebrikler 🎉\n\n📝 {cozum}"
    else:
        mesaj = (
            f"📊 Soru {index+1}/{toplam}\n\n{soru}\n\n"
            f"❌ Yanlış! Seçtiğin: {kullanici_cevabi}\n"
            f"✅ Doğru: {dogru_cevap}\n\n"
            f"📝 {cozum}"
        )

    await query.edit_message_text(mesaj)

    if index + 1 < toplam:
        await _soru_gonder(query.message.chat_id, context, index + 1)
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
            InlineKeyboardButton("💬 Soru Çözdür", callback_data="islem_sor"),
            InlineKeyboardButton("📅 Çalışma Planı", callback_data="islem_plan"),
        ],
        [
            InlineKeyboardButton("🔄 Sınav Değiştir", callback_data="sinav_degistir"),
            InlineKeyboardButton("🚨 Sorun Bildir", callback_data="sorun_bildir"),
        ],
        [
            InlineKeyboardButton("🔙 Geri", callback_data="geri_baslat"),
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
            InlineKeyboardButton("💬 Soru Çözdür", callback_data="islem_sor"),
            InlineKeyboardButton("📅 Çalışma Planı", callback_data="islem_plan"),
        ],
        [
            InlineKeyboardButton("🔄 Sınav Değiştir", callback_data="sinav_degistir"),
            InlineKeyboardButton("🚨 Sorun Bildir", callback_data="sorun_bildir"),
        ],
        [
            InlineKeyboardButton("🔙 Geri", callback_data="geri_baslat"),
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
    await geri_baslat(update, context)


# ───────────────────────────────────────────
# FOTOĞRAF İŞLEME
# ───────────────────────────────────────────

async def fotograf_isle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    kullanici_olustur(user_id)
    durum = kullanici_durumu(user_id)

    beklenen = context.user_data.get("beklenen_islem")
    if beklenen != "sor":
        await update.message.reply_text(
            "📸 Fotoğraf göndermek için önce *Soru Çözdür* seçeneğine bas!",
            parse_mode="Markdown"
        )
        return

    hak_durumu = mesaj_hakki_kontrol(user_id, durum["abone_mi"])
    if not hak_durumu["izin_ver"]:
        if durum["abone_mi"]:
            await update.message.reply_text(LIMIT_MESAJI)
        else:
            await update.message.reply_text(
                "⏰ Bugünlük 7 ücretsiz hakkını doldurdun!\n\n"
                "Gece 00:00'da hakların yenilenecek. Devam için /abone olabilirsin."
            )
        return

    bugun = datetime.now().strftime("%Y-%m-%d")
    foto_kullanimi = context.user_data.get(f"foto_{bugun}", 0)
    foto_limiti = 15 if durum["abone_mi"] else 3

    if foto_kullanimi >= foto_limiti:
        await update.message.reply_text(
            f"📸 Bugünlük {foto_limiti} fotoğraf hakkını doldurdun!\n"
            "Yarın tekrar deneyebilirsin."
        )
        return

    context.user_data[f"foto_{bugun}"] = foto_kullanimi + 1
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        foto = update.message.photo[-1]
        foto_dosyasi = await context.bot.get_file(foto.file_id)
        foto_bytes = await foto_dosyasi.download_as_bytearray()
        foto_base64 = base64.standard_b64encode(bytes(foto_bytes)).decode("utf-8")

        sinav = durum["sinav_turu"] or "ÖSYM"

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
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
                        "text": f"""Bu {sinav} sınav sorusunu çöz.

1. Önce soruyu ve şıkları oku
2. Adım adım çözümü göster (matematiksel işlemleri açık yaz)
3. Yanlış şıkların neden eleneceğini belirt
4. En sona: ✅ Doğru cevap: [şık harfi] - [şık metni]

Net ve anlaşılır Türkçe kullan."""
                    }
                ]
            }]
        )

        cevap = response.content[0].text
        gunluk_mesaj_artir(user_id)

        try:
            await update.message.reply_text(cevap, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(cevap)
        await _menu_goster(update, sinav)

    except Exception as e:
        await update.message.reply_text("⚠️ Fotoğraf işlenemedi, tekrar dener misin?")
        print(f"Fotoğraf hatası: {e}")


# ───────────────────────────────────────────
# SORUN BİLDİR
# ───────────────────────────────────────────

async def sorun_bildir_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🚨 Sorununu şu adrese ilet:\n"
        "t.me/Hsn_0134\n\n"
        "Direkt mesaj atabilirsin, en kısa sürede döneceğim!"
    )


async def sorun_bildir_komut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚨 Sorununu şu adrese ilet:\n"
        "t.me/Hsn_0134\n\n"
        "Direkt mesaj atabilirsin, en kısa sürede döneceğim!"
    )