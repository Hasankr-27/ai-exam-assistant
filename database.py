import sqlite3
from datetime import datetime, timedelta

DB_NAME = "sinav_botu.db"


def baglanti_ac():
    """Veritabanı bağlantısı açar."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Sütun adıyla erişim için
    return conn


def tablolari_olustur():
    """Uygulama başlarken tabloları oluşturur (yoksa)."""
    conn = baglanti_ac()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kullanicilar (
            user_id             INTEGER PRIMARY KEY,
            sinav_turu          TEXT DEFAULT NULL,
            kalan_hak           INTEGER DEFAULT 3,
            abone_mi            INTEGER DEFAULT 0,
            abone_bitis_tarihi  TEXT DEFAULT NULL,
            gunluk_mesaj_sayisi INTEGER DEFAULT 0,
            son_mesaj_tarihi    TEXT DEFAULT NULL,
            kayit_tarihi        TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Veritabanı tabloları hazır.")


# ───────────────────────────────────────────
# KULLANICI İŞLEMLERİ
# ───────────────────────────────────────────

def kullanici_getir(user_id: int):
    """Kullanıcıyı getirir. Yoksa None döner."""
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM kullanicilar WHERE user_id = ?", (user_id,))
    kullanici = cursor.fetchone()
    conn.close()
    return kullanici


def kullanici_olustur(user_id: int):
    """Yeni kullanıcı kaydeder (zaten varsa dokunmaz)."""
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO kullanicilar (user_id)
        VALUES (?)
    """, (user_id,))
    conn.commit()
    conn.close()


def sinav_turu_guncelle(user_id: int, sinav_turu: str):
    """Kullanıcının seçtiği sınav türünü günceller."""
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE kullanicilar SET sinav_turu = ? WHERE user_id = ?
    """, (sinav_turu, user_id))
    conn.commit()
    conn.close()


# ───────────────────────────────────────────
# HAK & LİMİT İŞLEMLERİ
# ───────────────────────────────────────────

def kalan_hak_azalt(user_id: int):
    """Ücretsiz kullanıcının hakkını 1 azaltır."""
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE kullanicilar SET kalan_hak = kalan_hak - 1 WHERE user_id = ?
    """, (user_id,))
    conn.commit()
    conn.close()


def gunluk_mesaj_kontrol(user_id: int) -> bool:
    """
    Günlük 50 mesaj limitini kontrol eder.
    True  → mesaj gönderilebilir
    False → limit doldu
    """
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT gunluk_mesaj_sayisi, son_mesaj_tarihi FROM kullanicilar WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return False

    bugun = datetime.now().strftime("%Y-%m-%d")
    son_tarih = row["son_mesaj_tarihi"]

    # Yeni gün → sayacı sıfırla
    if son_tarih != bugun:
        _gunluk_sayac_sifirla(user_id, bugun)
        return True

    return row["gunluk_mesaj_sayisi"] < 50


def gunluk_mesaj_artir(user_id: int):
    """Günlük mesaj sayacını 1 artırır."""
    bugun = datetime.now().strftime("%Y-%m-%d")
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE kullanicilar
        SET gunluk_mesaj_sayisi = gunluk_mesaj_sayisi + 1,
            son_mesaj_tarihi = ?
        WHERE user_id = ?
    """, (bugun, user_id))
    conn.commit()
    conn.close()


def _gunluk_sayac_sifirla(user_id: int, bugun: str):
    """İç kullanım: yeni günde sayacı sıfırlar."""
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE kullanicilar
        SET gunluk_mesaj_sayisi = 0, son_mesaj_tarihi = ?
        WHERE user_id = ?
    """, (bugun, user_id))
    conn.commit()
    conn.close()


# ───────────────────────────────────────────
# ABONELİK İŞLEMLERİ
# ───────────────────────────────────────────

def abone_yap(user_id: int, gun: int = 30):
    """Kullanıcıyı abone yapar, bitiş tarihini ayarlar."""
    bitis = (datetime.now() + timedelta(days=gun)).strftime("%Y-%m-%d")
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE kullanicilar
        SET abone_mi = 1, abone_bitis_tarihi = ?
        WHERE user_id = ?
    """, (bitis, user_id))
    conn.commit()
    conn.close()


def abonelik_kontrol(user_id: int) -> bool:
    """
    Aboneliğin aktif olup olmadığını kontrol eder.
    Süresi dolmuşsa otomatik iptal eder.
    """
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT abone_mi, abone_bitis_tarihi FROM kullanicilar WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row["abone_mi"]:
        return False

    bugun = datetime.now().strftime("%Y-%m-%d")
    if row["abone_bitis_tarihi"] and row["abone_bitis_tarihi"] < bugun:
        _aboneligi_iptal_et(user_id)
        return False

    return True


def _aboneligi_iptal_et(user_id: int):
    """İç kullanım: süresi dolan aboneliği iptal eder."""
    conn = baglanti_ac()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE kullanicilar SET abone_mi = 0, abone_bitis_tarihi = NULL WHERE user_id = ?
    """, (user_id,))
    conn.commit()
    conn.close()


# ───────────────────────────────────────────
# YARDIMCI
# ───────────────────────────────────────────

def kullanici_durumu(user_id: int) -> dict:
    """
    Kullanıcının tüm durumunu tek sözlük olarak döner.
    handlers.py içinde kolayca kullanmak için.
    """
    kullanici_olustur(user_id)  # yoksa oluştur
    k = kullanici_getir(user_id)

    abone = abonelik_kontrol(user_id)

    return {
        "user_id":              k["user_id"],
        "sinav_turu":           k["sinav_turu"],
        "kalan_hak":            k["kalan_hak"],
        "abone_mi":             abone,
        "abone_bitis_tarihi":   k["abone_bitis_tarihi"],
        "gunluk_mesaj_sayisi":  k["gunluk_mesaj_sayisi"],
    }


# ───────────────────────────────────────────
# TEST
# ───────────────────────────────────────────

if __name__ == "__main__":
    tablolari_olustur()

    # Test kullanıcısı
    TEST_ID = 123456789
    kullanici_olustur(TEST_ID)
    sinav_turu_guncelle(TEST_ID, "YKS")

    durum = kullanici_durumu(TEST_ID)
    print("\n📋 Kullanıcı Durumu:")
    for k, v in durum.items():
        print(f"  {k}: {v}")

    # Hak azalt
    kalan_hak_azalt(TEST_ID)
    print(f"\n✅ Hak azaltıldı → kalan: {kullanici_getir(TEST_ID)['kalan_hak']}")

    # Abone yap
    abone_yap(TEST_ID)
    print(f"✅ Abone yapıldı → aktif mi: {abonelik_kontrol(TEST_ID)}")

    # Günlük mesaj
    gunluk_mesaj_artir(TEST_ID)
    print(f"✅ Mesaj artırıldı → günlük: {kullanici_getir(TEST_ID)['gunluk_mesaj_sayisi']}")
    print(f"✅ Mesaj gönderilebilir mi: {gunluk_mesaj_kontrol(TEST_ID)}")