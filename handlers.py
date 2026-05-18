from collections import defaultdict
from datetime import datetime
import time
import base64
import json
import traceback

from anthropic import AsyncAnthropic
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    kullanici_olustur,
    kullanici_durumu,
    sinav_turu_guncelle,
    gunluk_mesaj_artir,
    mesaj_hakki_kontrol,
)
from ai import ai_cevap_al_stream, calisma_plani_stream, SINAV_DERSLERI, calisma_plani_olustur
import os
from dotenv import load_dotenv

load_dotenv()
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

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
    "fiyat":      "💳 Aylık abonelik 60 ⭐ — 3 aylık 150 ⭐!",
    "ucret":      "💳 Aylık abonelik 60 ⭐ — 3 aylık 150 ⭐!",
    "sen kimsin": "🤖 Ben YKS, KPSS, DGS, ALES, YDT sınavlarında uzman bir asistanım!",
}

ABONELIK_MESAJI = (
    "⛔ Ücretsiz hakkın bitti!\n\n"
    "📚 Devam etmek için abone ol:\n"
    "• Günde 70 mesaj hakkı\n"
    "• 1 Aylık → 60 ⭐\n"
    "• 3 Aylık → 150 ⭐\n\n"
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
    isim = update.effective_user.first_name if update.effective_user else "Öğrenci"
    await kullanici_olustur(update.effective_user.id)
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

    hosgeldin = (
        f"👋 Merhaba {isim}!\n\n"
        "🎯 *Sınav Asistanına Hoş Geldin!*\n\n"
        "📚 Yapay zeka destekli asistanın ile:\n"
        "✅ Konu anlatımı al\n"
        "✅ Soru hazırlat ve çöz\n"
        "✅ Çalışma planı oluştur\n"
        "✅ Takıldığın soruyu çözdür\n\n"
        "👇 Hangi sınava hazırlanıyorsun?"
    )
    try:
        await update.message.reply_text(hosgeldin, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(hosgeldin.replace("*", ""), reply_markup=reply_markup)


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

    try:
        await sinav_turu_guncelle(user_id, sinav)
        context.user_data["beklenen_islem"] = None
        await _menu_goster_query(query, sinav)
    except Exception as e:
        print(f"sinav_sec hatası: {type(e).__name__}: {e}")
        try:
            await query.edit_message_text("⚠️ Bir hata oluştu, /start ile tekrar dene.")
        except Exception:
            pass


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
    try:
        durum = await kullanici_durumu(user_id)
    except Exception as e:
        print(f"islem_sec DB hatası: {type(e).__name__}: {e}")
        try:
            await query.edit_message_text("⚠️ Bir hata oluştu, /start ile tekrar dene.")
        except Exception:
            pass
        return
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
    try:
        durum = await kullanici_durumu(query.from_user.id)
    except Exception as e:
        print(f"geri_menu DB hatası: {type(e).__name__}: {e}")
        try:
            await query.edit_message_text("⚠️ Bir hata oluştu, /start ile tekrar dene.")
        except Exception:
            pass
        return
    sinav = durum["sinav_turu"] or "YKS"
    await _menu_goster_query(query, sinav)


# ───────────────────────────────────────────
# DERS SEÇİMİ (callback)
# ───────────────────────────────────────────

async def ders_sec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    ders = query.data.replace("ders_", "")

    # Prompt injection koruması: ders gerçekten bilinen bir ders mi?
    gecerli = any(ders in dersler for dersler in SINAV_DERSLERI.values())
    if not gecerli:
        try:
            await query.edit_message_text("⚠️ Geçersiz ders. Menüden tekrar seç.")
        except Exception:
            pass
        return

    context.user_data["secilen_ders"] = ders
    context.user_data["beklenen_islem"] = "soru"

    keyboard = [[InlineKeyboardButton("🔙 Geri", callback_data="geri_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(
            f"✅ *{ders}* seçildi!\n\n"
            "📝 Hangi konudan soru hazırlayayım?",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
    except Exception:
        await query.edit_message_text(
            f"✅ {ders} seçildi!\n\n📝 Hangi konudan soru hazırlayayım?",
            reply_markup=reply_markup,
        )


# ───────────────────────────────────────────
# MESAJ HANDLER (ana akış)
# ───────────────────────────────────────────

async def mesaj_isle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    metin = update.message.text.lower().strip()[:2000]

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

    # 2) Kullanıcıyı getir (kullanici_durumu içinde otomatik oluşturur)
    durum = await kullanici_durumu(user_id)

    # 3) Sınav türü seçilmiş mi?
    if not durum["sinav_turu"]:
        await update.message.reply_text(
            "⚠️ Önce sınav türünü seç!\n/start yazarak başlayabilirsin."
        )
        return

    # 4) Hak kontrolü
    hak_durumu = await mesaj_hakki_kontrol(user_id, durum["abone_mi"])

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
    sinav = durum["sinav_turu"] or "YKS"

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

    placeholder = None
    try:
        # ── SORU KONUSU GELDİ ──
        if beklenen == "soru" and context.user_data.get("secilen_ders"):
            context.user_data["soru_konusu"] = metin

            keyboard = [[
                InlineKeyboardButton("1", callback_data="sayi_1"),
                InlineKeyboardButton("2", callback_data="sayi_2"),
                InlineKeyboardButton("3", callback_data="sayi_3"),
                InlineKeyboardButton("4", callback_data="sayi_4"),
                InlineKeyboardButton("5", callback_data="sayi_5"),
            ]]
            await update.message.reply_text(
                f"📝 {metin} konusunda kaç soru hazırlayayım?",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        # ── ÇALIŞMA PLANI ──
        if beklenen == "plan":
            try:
                parcalar = metin.replace(" ", "").split(",")
                gun = int(''.join(filter(str.isdigit, parcalar[0])))
                saat = int(''.join(filter(str.isdigit, parcalar[1])))
            except (ValueError, IndexError):
                await update.message.reply_text(
                    "⚠️ Şu formatta yaz:\n*47 gün, 7 saat*",
                    parse_mode="Markdown"
                )
                return

            placeholder = await update.message.reply_text("⏳ Çalışma planın hazırlanıyor...")
            cevap = ""
            son_guncelleme = time.time()
            async with calisma_plani_stream(gun, saat, sinav) as stream:
                async for chunk in stream.text_stream:
                    cevap += chunk
                    simdi = time.time()
                    if simdi - son_guncelleme >= 3.0 and cevap:
                        try:
                            goster = cevap[:3800] + " ..." if len(cevap) > 3800 else cevap + " ▌"
                            await placeholder.edit_text(goster)
                            son_guncelleme = simdi
                        except Exception:
                            pass
            context.user_data["beklenen_islem"] = None

        # ── KONU ANLAT / SORU ÇÖZDÜR ──
        else:
            gecmis = context.user_data.get("sohbet_gecmisi", [])
            placeholder = await update.message.reply_text("⏳ Düşünüyorum...")
            cevap = ""
            son_guncelleme = time.time()
            async with ai_cevap_al_stream(metin, sinav, gecmis) as stream:
                async for chunk in stream.text_stream:
                    cevap += chunk
                    simdi = time.time()
                    if simdi - son_guncelleme >= 3.0 and cevap:
                        try:
                            goster = cevap[:3800] + " ..." if len(cevap) > 3800 else cevap + " ▌"
                            await placeholder.edit_text(goster)
                            son_guncelleme = simdi
                        except Exception:
                            pass
            gecmis.append({"role": "user", "content": metin})
            gecmis.append({"role": "assistant", "content": cevap})
            context.user_data["sohbet_gecmisi"] = gecmis[-10:]

        await placeholder.delete()
        await _gonder_metin(update.message, cevap)
        await _menu_goster(update, sinav)

        try:
            await gunluk_mesaj_artir(user_id)
        except Exception as e:
            print(f"DB güncelleme hatası: {type(e).__name__}: {e}")

    except Exception as e:
        print(f"mesaj_isle hatası: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        if placeholder:
            try:
                await placeholder.edit_text("⚠️ Bir hata oluştu, tekrar dener misin?")
            except Exception:
                await update.message.reply_text("⚠️ Bir hata oluştu, tekrar dener misin?")
        else:
            await update.message.reply_text("⚠️ Bir hata oluştu, tekrar dener misin?")


# ───────────────────────────────────────────
# SORU SAYISI SEÇİMİ (callback)
# ───────────────────────────────────────────

def _json_onar(metin: str) -> str:
    """JSON string değerlerindeki literal newline'ları kaçış dizisiyle değiştirir."""
    sonuc = []
    string_icinde = False
    i = 0
    while i < len(metin):
        kar = metin[i]
        if kar == '\\' and i + 1 < len(metin):
            sonuc.append(kar)
            sonuc.append(metin[i + 1])
            i += 2
            continue
        if kar == '"':
            string_icinde = not string_icinde
        if string_icinde and kar == '\n':
            sonuc.append('\\n')
        elif string_icinde and kar == '\r':
            sonuc.append('\\r')
        else:
            sonuc.append(kar)
        i += 1
    return ''.join(sonuc)


def _json_ayikla(metin: str) -> list:
    """Modelin cevabından JSON array'i bulup parse eder."""
    metin = metin.strip()

    # Kod bloğu temizle
    if '```json' in metin:
        metin = metin.split('```json')[1].split('```')[0].strip()
    elif '```' in metin:
        metin = metin.split('```')[1].split('```')[0].strip()

    # JSON array'i bul
    if not metin.startswith('['):
        bas = metin.find('[')
        son = metin.rfind(']')
        if bas != -1 and son > bas:
            metin = metin[bas:son + 1]

    # Direkt parse dene
    try:
        return json.loads(metin)
    except json.JSONDecodeError:
        pass

    # Literal newline'ları düzelterek tekrar dene
    try:
        return json.loads(_json_onar(metin))
    except json.JSONDecodeError:
        raise


async def soru_sayisi_sec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    sayi = int(query.data.replace("sayi_", ""))
    konu = context.user_data.get("soru_konusu", "")
    ders = context.user_data.get("secilen_ders", "")
    user_id = query.from_user.id
    durum = await kullanici_durumu(user_id)
    sinav = durum["sinav_turu"]

    # Oturum süresi dolmuşsa (bot yeniden başlatıldıysa context temizlenir)
    if not konu or not ders or not sinav:
        await query.edit_message_text(
            "⚠️ Oturum süresi doldu.\nLütfen /start ile yeniden başla."
        )
        return

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
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}]
        )

        if not response.content:
            raise ValueError("Anthropic API boş yanıt döndürdü.")
        cikti = response.content[0].text.strip()
        sorular = _json_ayikla(cikti)

        if not sorular:
            await query.edit_message_text("⚠️ Soru üretilemedi, tekrar dener misin?")
            return

        for i, soru_data in enumerate(sorular):
            if not isinstance(soru_data, dict):
                continue
            context.user_data[f"soru_{i}"] = soru_data.get("soru", "")
            context.user_data[f"cevap_{i}"] = soru_data.get("cevap", "A")
            context.user_data[f"cozum_{i}"] = soru_data.get("cozum", "")
            if soru_data.get("soru"):
                gecmis_sorular.append(soru_data["soru"])

        context.user_data["gecmis_sorular"] = gecmis_sorular[-20:]
        context.user_data["toplam_soru"] = len(sorular)
        context.user_data["beklenen_islem"] = None
        context.user_data["secilen_ders"] = None

        await _soru_gonder(query.message.chat_id, context, 0)
        try:
            await gunluk_mesaj_artir(user_id)
        except Exception as e:
            print(f"DB güncelleme hatası: {type(e).__name__}: {e}")

    except json.JSONDecodeError:
        print(f"JSON parse hatası:\n{traceback.format_exc()}")
        await query.edit_message_text("⚠️ Format hatası, tekrar dener misin?")
    except Exception as e:
        print(f"soru_sayisi_sec hatası: {type(e).__name__}: {e}\n{traceback.format_exc()}")
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

    metin = f"📊 Soru {index+1}/{toplam}\n\n{soru}"
    if len(metin) > 4096:
        metin = metin[:4093] + "..."

    await context.bot.send_message(
        chat_id=chat_id,
        text=metin,
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
    if len(parcalar) < 3:
        await query.edit_message_text("⚠️ Geçersiz işlem. Yeni soru hazırlat!")
        return
    index = int(parcalar[1])
    kullanici_cevabi = parcalar[2]

    dogru_cevap = context.user_data.get(f"cevap_{index}")
    soru = context.user_data.get(f"soru_{index}")
    cozum = context.user_data.get(f"cozum_{index}")
    toplam = context.user_data.get("toplam_soru", 1)

    if dogru_cevap is None:
        await query.edit_message_text("⚠️ Bot yeniden başladı, lütfen yeni soru hazırlat!")
        return

    cozum_metin = cozum or "Çözüm kaydedilmemiş."
    if kullanici_cevabi == dogru_cevap:
        mesaj = f"📊 Soru {index+1}/{toplam}\n\n{soru}\n\n✅ Doğru! Tebrikler 🎉\n\n📝 {cozum_metin}"
    else:
        mesaj = (
            f"📊 Soru {index+1}/{toplam}\n\n{soru}\n\n"
            f"❌ Yanlış! Seçtiğin: {kullanici_cevabi}\n"
            f"✅ Doğru: {dogru_cevap}\n\n"
            f"📝 {cozum_metin}"
        )

    try:
        await query.edit_message_text(mesaj)
    except Exception:
        await query.edit_message_text(mesaj[:4096])

    if index + 1 < toplam:
        await _soru_gonder(query.message.chat_id, context, index + 1)
    else:
        durum = await kullanici_durumu(query.from_user.id)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="🎉 Test bitti! Sonuçlarını yukarıdan inceleyebilirsin."
        )
        await _menu_goster_chat(query.message.chat_id, context, durum["sinav_turu"] or "YKS")


# ───────────────────────────────────────────
# YARDIMCI: menü göster
# ───────────────────────────────────────────

async def _gonder_metin(mesaj_obj, metin: str):
    """4096 karakter sınırını aşan metinleri parçalara bölerek gönderir."""
    MAX = 4000
    parcalar = [metin[i:i+MAX] for i in range(0, len(metin), MAX)]
    for parca in parcalar:
        try:
            await mesaj_obj.reply_text(parca, parse_mode="Markdown")
        except Exception:
            await mesaj_obj.reply_text(parca)


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
    durum = await kullanici_durumu(user_id)

    beklenen = context.user_data.get("beklenen_islem")
    if beklenen != "sor":
        await update.message.reply_text(
            "📸 Fotoğraf göndermek için önce *Soru Çözdür* seçeneğine bas!",
            parse_mode="Markdown"
        )
        return

    hak_durumu = await mesaj_hakki_kontrol(user_id, durum["abone_mi"])
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

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        foto = update.message.photo[-1]
        foto_dosyasi = await context.bot.get_file(foto.file_id)
        foto_bytes = await foto_dosyasi.download_as_bytearray()
        foto_base64 = base64.standard_b64encode(bytes(foto_bytes)).decode("utf-8")

        sinav = durum["sinav_turu"] or "ÖSYM"

        response = await client.messages.create(
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

        if not response.content:
            raise ValueError("Anthropic API boş yanıt döndürdü.")
        cevap = response.content[0].text

        # Başarılı — sayacı şimdi artır
        context.user_data[f"foto_{bugun}"] = foto_kullanimi + 1

        await _gonder_metin(update.message, cevap)
        await _menu_goster(update, sinav)

        try:
            await gunluk_mesaj_artir(user_id)
        except Exception as db_err:
            print(f"DB güncelleme hatası: {type(db_err).__name__}: {db_err}")

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