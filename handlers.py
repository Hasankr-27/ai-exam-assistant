import asyncio
import random
from collections import defaultdict
from datetime import datetime
import time
import base64
import json
import traceback

from anthropic import AsyncAnthropic, RateLimitError, APIStatusError
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    kullanici_olustur,
    kullanici_durumu,
    sinav_turu_guncelle,
    gunluk_mesaj_artir,
    mesaj_hakkini_kullan,
)
from ai import ai_cevap_al_stream, calisma_plani_stream, SINAV_DERSLERI, calisma_plani_olustur, temizle_latex
import os
from dotenv import load_dotenv

load_dotenv()
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ───────────────────────────────────────────
# RATE LİMİTİNG
# ───────────────────────────────────────────

son_mesaj_zamani = defaultdict(float)
BEKLEME_SURESI = 3
_user_locks: dict[int, asyncio.Lock] = {}

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

    # Konu gerektirmeyen dersler direkt soru sayısına geçer
    KONU_GEREKMEZ = {"Genel Kültür"}
    if ders in KONU_GEREKMEZ:
        context.user_data["soru_konusu"] = "karışık genel kültür"
        sayi_keyboard = [[
            InlineKeyboardButton("1", callback_data="sayi_1"),
            InlineKeyboardButton("2", callback_data="sayi_2"),
            InlineKeyboardButton("3", callback_data="sayi_3"),
            InlineKeyboardButton("4", callback_data="sayi_4"),
            InlineKeyboardButton("5", callback_data="sayi_5"),
        ]]
        try:
            await query.edit_message_text(
                f"✅ *{ders}* seçildi!\n\nKaç soru hazırlayayım?",
                reply_markup=InlineKeyboardMarkup(sayi_keyboard),
                parse_mode="Markdown",
            )
        except Exception:
            await query.edit_message_text(
                f"✅ {ders} seçildi!\n\nKaç soru hazırlayayım?",
                reply_markup=InlineKeyboardMarkup(sayi_keyboard),
            )
        return

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
    metin_original = update.message.text.strip()[:2000]
    metin = metin_original.lower()

    # 0) Rate limit — write before any await to avoid race condition
    simdi = time.time()
    son = son_mesaj_zamani[user_id]
    son_mesaj_zamani[user_id] = simdi
    if simdi - son < BEKLEME_SURESI:
        son_mesaj_zamani[user_id] = son  # restore so next try still counts
        await update.message.reply_text("⏳ Çok hızlı! Lütfen 3 saniye bekle.")
        return

    # 1) Hazır cevap var mı?
    if metin in HAZIR_CEVAPLAR:
        await update.message.reply_text(HAZIR_CEVAPLAR[metin])
        return

    # 2) Kullanıcıyı getir
    durum = await kullanici_durumu(user_id)

    # 3) Sınav türü seçilmiş mi?
    if not durum["sinav_turu"]:
        await update.message.reply_text(
            "⚠️ Önce sınav türünü seç!\n/start yazarak başlayabilirsin."
        )
        return

    # 4) beklenen ve sinav
    beklenen = context.user_data.get("beklenen_islem", None)
    sinav = durum["sinav_turu"] or "YKS"

    # 5) Menüden seçim yapılmamışsa engelle
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
        await update.message.reply_text(
            MENU_SEC_MESAJI,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # 6) Soru konusu — AI yok, hak tüketme
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

    # 7) Per-user lock: streaming sırasında ikinci mesajı engelle
    lock = _user_locks.setdefault(user_id, asyncio.Lock())
    if lock.locked():
        await update.message.reply_text("⏳ Önceki isteğin hâlâ işleniyor, lütfen bekle.")
        return

    async with lock:
        # 8) Atomik hak kontrolü + tüketim
        hak_durumu = await mesaj_hakkini_kullan(user_id, durum["abone_mi"])
        if not hak_durumu["izin_ver"]:
            if durum["abone_mi"]:
                await update.message.reply_text(LIMIT_MESAJI)
            else:
                await update.message.reply_text(
                    "⏰ Bugünlük 7 ücretsiz hakkını doldurdun!\n\n"
                    "Gece 00:00'da hakların yenilenecek. Devam için /abone yazabilirsin! 🚀"
                )
            return

        placeholder = None
        try:
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
                # konu anlatımı uzun olabilir, soru çözümü daha kısa
                _max_tok = 2500 if beklenen == "konu" else 1500
                async with ai_cevap_al_stream(metin, sinav, gecmis, max_tokens=_max_tok) as stream:
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

            cevap = temizle_latex(cevap)
            if not cevap:
                await placeholder.edit_text("⚠️ Boş yanıt alındı, tekrar dener misin?")
                return

            try:
                await placeholder.delete()
            except Exception:
                pass

            # Soru çözdür modunda sorumluluk reddi ekle + soruyu sakla
            if beklenen == "sor":
                context.user_data["son_soru"] = metin_original  # orijinal harf korunsun
                context.user_data["son_ai_cevap"] = cevap
                context.user_data["son_sinav"] = sinav
                context.user_data["yanlis_sayac"] = 0  # yeni soru → sayacı sıfırla
                context.user_data["tekrar_anlat_sayac"] = 0
                cevap += "\n\n⚠️ *Not:* Ben yapay zekayım ve hatalı cevap verebilirim. Lütfen kontrol et!"
            await _gonder_metin(update.message, cevap)
            if beklenen == "sor":
                await _menu_goster_sor(update, sinav)
            else:
                await _menu_goster(update, sinav)

        except (RateLimitError, APIStatusError) as e:
            print(f"Anthropic API yük hatası: {type(e).__name__}: {e}")
            context.user_data["beklenen_islem"] = beklenen  # state koru, tekrar deneyebilsin
            mesaj = "⚠️ Sunucu şu an yoğun, 30 saniye sonra tekrar dene."
            if placeholder:
                try:
                    await placeholder.edit_text(mesaj)
                except Exception:
                    await update.message.reply_text(mesaj)
            else:
                await update.message.reply_text(mesaj)

        except Exception as e:
            print(f"mesaj_isle hatası: {type(e).__name__}: {e}\n{traceback.format_exc()}")
            context.user_data["beklenen_islem"] = None
            mesaj = "⚠️ Bir hata oluştu, tekrar dener misin?"
            if placeholder:
                try:
                    await placeholder.edit_text(mesaj)
                except Exception:
                    await update.message.reply_text(mesaj)
            else:
                await update.message.reply_text(mesaj)


# ───────────────────────────────────────────
# SORU SAYISI SEÇİMİ (callback)
# ───────────────────────────────────────────

def _sikları_karistir(soru_data: dict) -> dict:
    """Şık içeriklerini karıştırır ve cevap harfini buna göre günceller."""
    soru_metni = soru_data.get("soru", "")
    dogru_harf = soru_data.get("cevap", "A").strip().upper()

    satirlar = soru_metni.split("\n")
    soru_bolum = []
    siklar = []  # [(harf, icerik), ...]

    for satir in satirlar:
        temiz = satir.strip()
        if len(temiz) >= 2 and temiz[0] in "ABCDE" and temiz[1] == ")":
            siklar.append((temiz[0], temiz[2:].strip()))
        else:
            if not siklar:
                soru_bolum.append(satir)

    if len(siklar) < 2 or dogru_harf not in dict(siklar):
        return soru_data

    dogru_icerik = dict(siklar)[dogru_harf]
    harfler = [h for h, _ in siklar]
    icerikler = [ic for _, ic in siklar]

    random.shuffle(icerikler)

    yeni_dogru = None
    yeni_satirlar = [s for s in soru_bolum if s or not siklar]
    for i, harf in enumerate(harfler):
        yeni_satirlar.append(f"{harf}) {icerikler[i]}")
        if icerikler[i] == dogru_icerik:
            yeni_dogru = harf

    if yeni_dogru is None:
        return soru_data

    return {
        "soru": "\n".join(yeni_satirlar),
        "cevap": yeni_dogru,
        "cozum": soru_data.get("cozum", ""),
    }


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

    try:
        durum = await kullanici_durumu(user_id)
        sinav = durum["sinav_turu"]
    except Exception as e:
        print(f"soru_sayisi_sec DB hatası: {type(e).__name__}: {e}")
        await query.edit_message_text("⚠️ Bir hata oluştu, /start ile tekrar dene.")
        return

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
- Her soruyu hazırlamadan önce cevabını kendin hesapla/doğrula
- Doğru cevap şıklarda MUTLAKA bulunmalı
- Yanlış şıklar makul ama kesinlikle yanlış olmalı
- Gerçek {sinav} sınav zorluk seviyesinde olsun
- Sorular birbirinden farklı alt konuları kapsasın
- DOĞRU CEVAP KONUMU: Her soruda doğru cevabı farklı bir şıkta konumlandır.
  Tüm sorularda aynı şık (örn. hep A) doğru olmamalı; A, B, C, D, E arasında dağıt.

Sadece geçerli bir JSON array formatında çıktı ver. Başka hiçbir şey yazma.
[
  {{
    "soru": "Soru metni...\\nA) ...\\nB) ...\\nC) ...\\nD) ...\\nE) ...",
    "cevap": "C",
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

        # Eski soru keylerini temizle
        for i in range(context.user_data.get("toplam_soru", 0)):
            context.user_data.pop(f"soru_{i}", None)
            context.user_data.pop(f"cevap_{i}", None)
            context.user_data.pop(f"cozum_{i}", None)

        for i, soru_data in enumerate(sorular):
            if not isinstance(soru_data, dict):
                continue
            soru_data = _sikları_karistir(soru_data)  # şıkları karıştır
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
        try:
            durum = await kullanici_durumu(query.from_user.id)
            sinav_adi = durum["sinav_turu"] or "YKS"
        except Exception:
            sinav_adi = "YKS"
        # Son soruyu tekrar_anlat için sakla
        context.user_data["son_soru"] = f"{soru}\n\nÇözüm: {cozum_metin}"
        context.user_data["son_sinav"] = sinav_adi
        context.user_data["tekrar_anlat_sayac"] = 0
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="🎉 Test bitti! Sonuçlarını yukarıdan inceleyebilirsin."
        )
        await _menu_goster_chat(query.message.chat_id, context, sinav_adi)


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
            try:
                await mesaj_obj.reply_text(parca)
            except Exception as e:
                print(f"Mesaj gönderilemedi: {e}")


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


async def _menu_goster_sor(update: Update, sinav: str):
    keyboard = [
        [
            InlineKeyboardButton("⚠️ Yanlış Cevap", callback_data="yanlis_cevap"),
            InlineKeyboardButton("🤔 Anlamadım", callback_data="tekrar_anlat"),
        ],
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


YANLIS_LIMIT = 3

async def yanlis_cevap_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    son_soru = context.user_data.get("son_soru")
    sinav = context.user_data.get("son_sinav", "YKS")
    yanlis_sayac = context.user_data.get("yanlis_sayac", 0)
    user_id = query.from_user.id

    # Limit kontrolü
    if yanlis_sayac >= YANLIS_LIMIT:
        try:
            await query.edit_message_text(
                f"🛑 Bu soruyu {YANLIS_LIMIT} kez yeniden çözdüm.\n\n"
                "Farklı bir soru sor veya öğretmeninden yardım al. 📚"
            )
        except Exception:
            pass
        return

    if not son_soru:
        try:
            await query.edit_message_text("⚠️ Soru bulunamadı, lütfen soruyu tekrar yaz.")
        except Exception:
            pass
        return

    if son_soru == "__foto__":
        try:
            await query.edit_message_text(
                "📸 Fotoğraf sorusu için yeniden çözüm yapabilmem için "
                "fotoğrafı tekrar gönder."
            )
        except Exception:
            pass
        return

    # Hak kontrolü
    try:
        durum = await kullanici_durumu(user_id)
        hak_durumu = await mesaj_hakkini_kullan(user_id, durum["abone_mi"])
    except Exception as e:
        print(f"yanlis_cevap hak hatası: {e}")
        try:
            await query.edit_message_text("⚠️ Bir hata oluştu, tekrar dene.")
        except Exception:
            pass
        return

    if not hak_durumu["izin_ver"]:
        try:
            await query.edit_message_text(
                "⏰ Mesaj hakkın bitti!\nYarın sıfırlanacak veya /abone yazarak devam edebilirsin."
            )
        except Exception:
            pass
        return

    # Butonu kapat
    try:
        await query.edit_message_text("🔄 Soruyu dikkatlice yeniden çözüyorum...")
    except Exception:
        pass

    # Yeni placeholder gönder
    placeholder = await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="⏳ Düşünüyorum..."
    )

    yeniden_prompt = (
        "Bir öğrenci bu soruyu sana sordu ve verdiğin cevabın yanlış olduğunu bildirdi. "
        "Soruyu baştan, çok dikkatli şekilde adım adım yeniden çöz. "
        "Her işlemi tek tek kontrol et ve kesin olarak doğru cevabı bul:\n\n" + son_soru
    )

    cevap = ""
    son_guncelleme = time.time()

    try:
        async with ai_cevap_al_stream(yeniden_prompt, sinav, []) as stream:
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

        cevap = temizle_latex(cevap)
        if not cevap:
            await placeholder.edit_text("⚠️ Boş yanıt alındı, tekrar dener misin?")
            return

        try:
            await placeholder.delete()
        except Exception:
            pass

        context.user_data["yanlis_sayac"] = yanlis_sayac + 1
        kalan = YANLIS_LIMIT - (yanlis_sayac + 1)
        not_metni = "\n\n⚠️ *Not:* Ben yapay zekayım ve yine de hatalı olabilirim. Önemli sorularda kaynaktan kontrol et!"
        if kalan > 0:
            not_metni += f"\n_(Bu soru için {kalan} yeniden çözüm hakkın kaldı.)_"
        cevap += not_metni
        # Yanıtı parçalara bölerek gönder
        MAX = 4000
        for parca in [cevap[i:i+MAX] for i in range(0, len(cevap), MAX)]:
            try:
                await context.bot.send_message(
                    chat_id=query.message.chat_id, text=parca, parse_mode="Markdown"
                )
            except Exception:
                await context.bot.send_message(chat_id=query.message.chat_id, text=parca)

        # Menü
        keyboard = [
            [
                InlineKeyboardButton("⚠️ Yanlış Cevap", callback_data="yanlis_cevap"),
                InlineKeyboardButton("🤔 Anlamadım", callback_data="tekrar_anlat"),
            ],
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
                InlineKeyboardButton("🔙 Geri", callback_data="geri_baslat"),
            ],
        ]
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"📚 {sinav} — Başka ne yapmak istersin?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    except (RateLimitError, APIStatusError) as e:
        print(f"yanlis_cevap API hatası: {e}")
        try:
            await placeholder.edit_text("⚠️ Sunucu şu an yoğun, 30 saniye sonra tekrar dene.")
        except Exception:
            pass
    except Exception as e:
        print(f"yanlis_cevap hatası: {e}\n{traceback.format_exc()}")
        try:
            await placeholder.edit_text("⚠️ Bir hata oluştu, tekrar dener misin?")
        except Exception:
            pass


# ───────────────────────────────────────────
# TEKRAR ANLAT (callback)
# ───────────────────────────────────────────

TEKRAR_ANLAT_LIMIT = 3

async def tekrar_anlat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    son_soru = context.user_data.get("son_soru")
    son_ai_cevap = context.user_data.get("son_ai_cevap", "")
    sinav = context.user_data.get("son_sinav", "YKS")
    sayac = context.user_data.get("tekrar_anlat_sayac", 0)
    user_id = query.from_user.id

    if sayac >= TEKRAR_ANLAT_LIMIT:
        try:
            await query.edit_message_text(
                f"🛑 Bu soruyu {TEKRAR_ANLAT_LIMIT} kez farklı şekilde anlattım.\n\n"
                "Farklı bir soru sor ya da öğretmeninden destek al. 📚"
            )
        except Exception:
            pass
        return

    if not son_soru or son_soru == "__foto__":
        try:
            await query.edit_message_text(
                "⚠️ Hangi soruyu tekrar anlatacağımı bilemedim. Soruyu tekrar gönderir misin?"
            )
        except Exception:
            pass
        return

    try:
        durum = await kullanici_durumu(user_id)
        hak_durumu = await mesaj_hakkini_kullan(user_id, durum["abone_mi"])
    except Exception as e:
        print(f"tekrar_anlat hak hatası: {e}")
        try:
            await query.edit_message_text("⚠️ Bir hata oluştu, tekrar dene.")
        except Exception:
            pass
        return

    if not hak_durumu["izin_ver"]:
        try:
            await query.edit_message_text(
                "⏰ Mesaj hakkın bitti!\nYarın sıfırlanacak veya /abone yazarak devam edebilirsin."
            )
        except Exception:
            pass
        return

    try:
        await query.edit_message_text("🤔 Farklı bir yaklaşımla yeniden anlatıyorum...")
    except Exception:
        pass

    placeholder = await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="⏳ Hazırlıyorum..."
    )

    onceki_bilgi = f"\n\nÖnceki açıklaman:\n{son_ai_cevap[:800]}" if son_ai_cevap else ""
    prompt = (
        "Bir öğrenci aşağıdaki soruyu/konuyu anlamadığını belirtti. "
        "Tamamen farklı bir yaklaşımla, daha sade ve anlaşılır bir dille, "
        "somut örnekler ve benzetmeler kullanarak adım adım yeniden açıkla."
        f"{onceki_bilgi}\n\n"
        f"Soru/Konu:\n{son_soru}"
    )

    cevap = ""
    son_guncelleme = time.time()

    try:
        async with ai_cevap_al_stream(prompt, sinav, []) as stream:
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

        cevap = temizle_latex(cevap)
        if not cevap:
            await placeholder.edit_text("⚠️ Boş yanıt alındı, tekrar dener misin?")
            return

        try:
            await placeholder.delete()
        except Exception:
            pass

        context.user_data["tekrar_anlat_sayac"] = sayac + 1
        context.user_data["son_ai_cevap"] = cevap
        kalan = TEKRAR_ANLAT_LIMIT - (sayac + 1)
        not_metni = "\n\n💡 *Not:* Hâlâ anlamadıysan öğretmeninden destek alabilirsin."
        if kalan > 0:
            not_metni += f"\n_(Bu soru için {kalan} tekrar hakkın kaldı.)_"
        cevap += not_metni

        MAX = 4000
        for parca in [cevap[i:i+MAX] for i in range(0, len(cevap), MAX)]:
            try:
                await context.bot.send_message(
                    chat_id=query.message.chat_id, text=parca, parse_mode="Markdown"
                )
            except Exception:
                await context.bot.send_message(chat_id=query.message.chat_id, text=parca)

        keyboard = [
            [
                InlineKeyboardButton("⚠️ Yanlış Cevap", callback_data="yanlis_cevap"),
                InlineKeyboardButton("🤔 Anlamadım", callback_data="tekrar_anlat"),
            ],
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
                InlineKeyboardButton("🔙 Geri", callback_data="geri_baslat"),
            ],
        ]
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"📚 {sinav} — Başka ne yapmak istersin?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    except (RateLimitError, APIStatusError) as e:
        print(f"tekrar_anlat API hatası: {e}")
        try:
            await placeholder.edit_text("⚠️ Sunucu şu an yoğun, 30 saniye sonra tekrar dene.")
        except Exception:
            pass
    except Exception as e:
        print(f"tekrar_anlat hatası: {e}\n{traceback.format_exc()}")
        try:
            await placeholder.edit_text("⚠️ Bir hata oluştu, tekrar dener misin?")
        except Exception:
            pass


async def _menu_goster_chat(chat_id, context, sinav: str):
    keyboard = [
        [
            InlineKeyboardButton("🤔 Anlamadım, Tekrar Anlat", callback_data="tekrar_anlat"),
        ],
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
    # Albüm/çoklu fotoğraf gönderimi engelle
    if update.message.media_group_id:
        await update.message.reply_text(
            "📸 Lütfen tek seferde sadece *1 fotoğraf* gönder.",
            parse_mode="Markdown"
        )
        return

    user_id = update.effective_user.id
    durum = await kullanici_durumu(user_id)

    beklenen = context.user_data.get("beklenen_islem")
    if beklenen != "sor":
        await update.message.reply_text(
            "📸 Fotoğraf göndermek için önce *Soru Çözdür* seçeneğine bas!",
            parse_mode="Markdown"
        )
        return

    bugun = datetime.now().strftime("%Y-%m-%d")

    # Eski foto keylerini temizle
    for key in list(context.user_data.keys()):
        if key.startswith("foto_") and key != f"foto_{bugun}":
            del context.user_data[key]

    foto_kullanimi = context.user_data.get(f"foto_{bugun}", 0)
    foto_limiti = 15 if durum["abone_mi"] else 3

    if foto_kullanimi >= foto_limiti:
        await update.message.reply_text(
            f"📸 Bugünlük {foto_limiti} fotoğraf hakkını doldurdun!\n"
            "Yarın tekrar deneyebilirsin."
        )
        return

    # Dosya boyutu kontrolü
    foto_meta = update.message.photo[-1]
    if foto_meta.file_size and foto_meta.file_size > 5_000_000:
        await update.message.reply_text("⚠️ Fotoğraf 5 MB'dan büyük olamaz.")
        return

    # Atomik mesaj hakkı kontrolü + tüketim
    hak_durumu = await mesaj_hakkini_kullan(user_id, durum["abone_mi"])
    if not hak_durumu["izin_ver"]:
        if durum["abone_mi"]:
            await update.message.reply_text(LIMIT_MESAJI)
        else:
            await update.message.reply_text(
                "⏰ Bugünlük 7 ücretsiz hakkını doldurdun!\n\n"
                "Gece 00:00'da hakların yenilenecek. Devam için /abone olabilirsin."
            )
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        foto_dosyasi = await context.bot.get_file(foto_meta.file_id)
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

        # Başarılı — foto sayacını artır (mesaj hakkı zaten mesaj_hakkini_kullan'da tüketildi)
        context.user_data[f"foto_{bugun}"] = foto_kullanimi + 1
        context.user_data["son_soru"] = "__foto__"  # fotoğraf sorusunu yeniden çözmek için foto tekrar gönderilmeli
        context.user_data["son_sinav"] = sinav

        cevap += "\n\n⚠️ *Not:* Ben yapay zekayım ve hatalı cevap verebilirim. Lütfen kontrol et!"
        await _gonder_metin(update.message, cevap)
        await _menu_goster_sor(update, sinav)

    except (RateLimitError, APIStatusError) as e:
        print(f"Anthropic API yük hatası (foto): {type(e).__name__}: {e}")
        await update.message.reply_text("⚠️ Sunucu şu an yoğun, 30 saniye sonra tekrar dene.")
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