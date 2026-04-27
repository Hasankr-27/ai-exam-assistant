import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def baglanti_ac():
    """PostgreSQL bağlantısı açar."""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn


def tablolari_olustur():
    """Uygulama başlarken tabloları oluşturur (yoksa)."""
    conn = baglanti_ac()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kullanicilar (
            user_id             BIGINT PRIMARY KEY,
            sinav_turu          TEXT DEFAULT NULL,
            kalan_hak           INTEGER DEFAULT 7,
            abone_mi            INTEGER DEFAULT 0,
            abone_bitis_tarihi  TEXT DEFAULT NULL,
            gunluk_mesaj_sayisi INTEGER DEFAULT 0,
            son_mesaj_tarihi    TEXT DEFAULT NULL,
            kayit_tarihi        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ PostgreSQL tabloları hazır.")


# ───────────────────────────────────────────
# KULLANICI İŞLEMLERİ
# ───────────────────────────────────────────

def kullanici_getir(user_id: int):
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM kullanicilar WHERE user_id = %s", (user_id,))
    kullanici = cursor.fetchone()
    cursor.close()
    conn.close()
    return kullanici


def kullanici_olustur(user_id: int):
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO kullanicilar (user_id)
        VALUES (%s)
        ON CONFLICT (user_id) DO NOTHING
    """, (user_id,))
    conn.commit()
    cursor.close()
    conn.close()


def sinav_turu_guncelle(user_id: int, sinav_turu: str):
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE kullanicilar SET sinav_turu = %s WHERE user_id = %s
    """, (sinav_turu, user_id))
    conn.commit()
    cursor.close()
    conn.close()


# ───────────────────────────────────────────
# HAK & LİMİT İŞLEMLERİ
# ───────────────────────────────────────────

def kalan_hak_azalt(user_id: int):
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE kullanicilar SET kalan_hak = kalan_hak - 1 WHERE user_id = %s
    """, (user_id,))
    conn.commit()
    cursor.close()
    conn.close()


def mesaj_hakki_kontrol(user_id: int, abone_mi: bool) -> dict:
    """Hem abone hem ücretsiz kullanıcılar için günlük limit kontrolü yapar."""
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT gunluk_mesaj_sayisi, son_mesaj_tarihi FROM kullanicilar WHERE user_id = %s
    """, (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.close()
        conn.close()
        return {"izin_ver": False, "kalan": 0}

    bugun = datetime.now().strftime("%Y-%m-%d")
    son_tarih = row["son_mesaj_tarihi"]
    kullanilan_adet = row["gunluk_mesaj_sayisi"]

    # --- GECE YARISI SIFIRLAMA MANTIĞI ---
    # Eğer son mesaj tarihi bugün değilse, sayaç sıfırlanır
    if son_tarih != bugun:
        _gunluk_sayac_sifirla(user_id, bugun)
        kullanilan_adet = 0

    cursor.close()
    conn.close()

    # --- LİMİT BELİRLEME ---
    # Abone ise 70, değilse 7 hak tanımlıyoruz
    limit = 70 if abone_mi else 7
    kalan_hak = limit - kullanilan_adet

    return {
        "izin_ver": kullanilan_adet < limit,
        "kalan": kalan_hak
    }


def gunluk_mesaj_artir(user_id: int):
    bugun = datetime.now().strftime("%Y-%m-%d")
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE kullanicilar
        SET gunluk_mesaj_sayisi = gunluk_mesaj_sayisi + 1,
            son_mesaj_tarihi = %s
        WHERE user_id = %s
    """, (bugun, user_id))
    conn.commit()
    cursor.close()
    conn.close()


def _gunluk_sayac_sifirla(user_id: int, bugun: str):
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE kullanicilar
        SET gunluk_mesaj_sayisi = 0, son_mesaj_tarihi = %s
        WHERE user_id = %s
    """, (bugun, user_id))
    conn.commit()
    cursor.close()
    conn.close()


# ───────────────────────────────────────────
# ABONELİK İŞLEMLERİ
# ───────────────────────────────────────────

def abone_yap(user_id: int, gun: int = 30):
    bitis = (datetime.now() + timedelta(days=gun)).strftime("%Y-%m-%d")
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE kullanicilar
        SET abone_mi = 1, abone_bitis_tarihi = %s
        WHERE user_id = %s
    """, (bitis, user_id))
    conn.commit()
    cursor.close()
    conn.close()


def abonelik_kontrol(user_id: int) -> bool:
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT abone_mi, abone_bitis_tarihi FROM kullanicilar WHERE user_id = %s
    """, (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row or not row["abone_mi"]:
        return False

    bugun = datetime.now().strftime("%Y-%m-%d")
    if row["abone_bitis_tarihi"] and row["abone_bitis_tarihi"] < bugun:
        _aboneligi_iptal_et(user_id)
        return False

    return True


def _aboneligi_iptal_et(user_id: int):
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE kullanicilar SET abone_mi = 0, abone_bitis_tarihi = NULL WHERE user_id = %s
    """, (user_id,))
    conn.commit()
    cursor.close()
    conn.close()


# ───────────────────────────────────────────
# YARDIMCI
# ───────────────────────────────────────────

def kullanici_durumu(user_id: int) -> dict:
    kullanici_olustur(user_id)
    k = kullanici_getir(user_id)
    abone = abonelik_kontrol(user_id)

    return {
        "user_id":             k["user_id"],
        "sinav_turu":          k["sinav_turu"],
        "kalan_hak":           k["kalan_hak"],
        "abone_mi":            abone,
        "abone_bitis_tarihi":  k["abone_bitis_tarihi"],
        "gunluk_mesaj_sayisi": k["gunluk_mesaj_sayisi"],
    }