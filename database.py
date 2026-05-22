import os
import asyncpg
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL ortam değişkeni ayarlanmamış!")
# Railway postgres:// → asyncpg'nin beklediği postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_pool: asyncpg.Pool | None = None


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DATABASE_URL, min_size=2, max_size=25, command_timeout=30.0
        )
    return _pool


async def tablolari_olustur():
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
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
    print("✅ PostgreSQL tabloları hazır.")


# ───────────────────────────────────────────
# KULLANICI İŞLEMLERİ
# ───────────────────────────────────────────

async def kullanici_getir(user_id: int):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM kullanicilar WHERE user_id = $1", user_id
        )


async def kullanici_olustur(user_id: int):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO kullanicilar (user_id)
            VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING
        """, user_id)


async def sinav_turu_guncelle(user_id: int, sinav_turu: str):
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE kullanicilar SET sinav_turu = $1 WHERE user_id = $2",
            sinav_turu, user_id
        )


# ───────────────────────────────────────────
# HAK & LİMİT İŞLEMLERİ
# ───────────────────────────────────────────

async def mesaj_hakkini_kullan(user_id: int, abone_mi: bool) -> dict:
    """Atomik hak kontrolü: izin varsa sayacı artırır ve izin_ver=True döner."""
    bugun = datetime.now().strftime("%Y-%m-%d")
    limit = 70 if abone_mi else 7
    pool = await _get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT gunluk_mesaj_sayisi, son_mesaj_tarihi FROM kullanicilar "
                "WHERE user_id = $1 FOR UPDATE",
                user_id
            )
            if not row:
                return {"izin_ver": False, "kalan": 0}

            kullanilan = 0 if row["son_mesaj_tarihi"] != bugun else row["gunluk_mesaj_sayisi"]

            if kullanilan >= limit:
                return {"izin_ver": False, "kalan": 0}

            await conn.execute("""
                UPDATE kullanicilar
                SET gunluk_mesaj_sayisi = $1, son_mesaj_tarihi = $2
                WHERE user_id = $3
            """, kullanilan + 1, bugun, user_id)

            return {"izin_ver": True, "kalan": limit - kullanilan - 1}


async def gunluk_mesaj_artir(user_id: int):
    bugun = datetime.now().strftime("%Y-%m-%d")
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE kullanicilar
            SET gunluk_mesaj_sayisi = gunluk_mesaj_sayisi + 1,
                son_mesaj_tarihi = $1
            WHERE user_id = $2
        """, bugun, user_id)


# ───────────────────────────────────────────
# ABONELİK İŞLEMLERİ
# ───────────────────────────────────────────

async def abone_yap(user_id: int, gun: int = 30):
    """Mevcut abonelik varsa üzerine ekler, yoksa bugünden başlatır."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT abone_bitis_tarihi FROM kullanicilar WHERE user_id = $1",
            user_id
        )
        baslangic = datetime.now()
        if row and row["abone_bitis_tarihi"]:
            try:
                mevcut_bitis = datetime.strptime(row["abone_bitis_tarihi"], "%Y-%m-%d")
                if mevcut_bitis > baslangic:
                    baslangic = mevcut_bitis
            except (ValueError, TypeError):
                pass
        bitis = (baslangic + timedelta(days=gun)).strftime("%Y-%m-%d")
        await conn.execute("""
            UPDATE kullanicilar
            SET abone_mi = 1, abone_bitis_tarihi = $1
            WHERE user_id = $2
        """, bitis, user_id)


# ───────────────────────────────────────────
# YARDIMCI
# ───────────────────────────────────────────

async def kullanici_durumu(user_id: int) -> dict:
    """Tek transaction'da: kayıt oluştur, veri getir, abonelik kontrol et."""
    bugun = datetime.now().strftime("%Y-%m-%d")
    pool = await _get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("""
                INSERT INTO kullanicilar (user_id)
                VALUES ($1)
                ON CONFLICT (user_id) DO NOTHING
            """, user_id)

            k = await conn.fetchrow(
                "SELECT * FROM kullanicilar WHERE user_id = $1", user_id
            )

            if k is None:
                return {
                    "user_id":             user_id,
                    "sinav_turu":          None,
                    "kalan_hak":           7,
                    "abone_mi":            False,
                    "abone_bitis_tarihi":  None,
                    "gunluk_mesaj_sayisi": 0,
                }

            abone = False
            if k["abone_mi"]:
                if k["abone_bitis_tarihi"] and k["abone_bitis_tarihi"] >= bugun:
                    abone = True
                else:
                    await conn.execute(
                        "UPDATE kullanicilar SET abone_mi = 0, abone_bitis_tarihi = NULL "
                        "WHERE user_id = $1",
                        user_id
                    )

    return {
        "user_id":             k["user_id"],
        "sinav_turu":          k["sinav_turu"],
        "kalan_hak":           k["kalan_hak"],
        "abone_mi":            abone,
        "abone_bitis_tarihi":  k["abone_bitis_tarihi"],
        "gunluk_mesaj_sayisi": k["gunluk_mesaj_sayisi"],
    }
