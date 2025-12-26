"""
SQLite'dan PostgreSQL'e veri migration scripti
ÇELMAK Stok Takip Sistemi

Kullanım:
1. PostgreSQL veritabanını oluşturun
2. .env dosyasında DATABASE_URL'i PostgreSQL'e ayarlayın
3. python migrate_to_postgres.py komutunu çalıştırın
"""

import sqlite3
import psycopg
from psycopg import sql
import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Konfigürasyon
SQLITE_DB_PATH = 'instance/celmak_stok.db'
POSTGRES_URL = os.environ.get('DATABASE_URL')

def parse_postgres_url(url):
    """PostgreSQL URL'ini parse et"""
    # postgresql+psycopg://user:pass@host:port/dbname
    url = url.replace('postgresql+psycopg://', '').replace('postgresql://', '')
    user_pass, host_port_db = url.split('@')
    user, password = user_pass.split(':')
    host_port, dbname = host_port_db.split('/')
    host, port = host_port.split(':')

    return f"host={host} port={port} dbname={dbname} user={user} password={password}"

def migrate_data():
    """SQLite'dan PostgreSQL'e veri taşı"""

    if not os.path.exists(SQLITE_DB_PATH):
        print(f"❌ SQLite veritabanı bulunamadı: {SQLITE_DB_PATH}")
        return False

    if not POSTGRES_URL:
        print("❌ DATABASE_URL çevre değişkeni bulunamadı!")
        print("   .env dosyasını kontrol edin.")
        return False

    try:
        # PostgreSQL bağlantı bilgilerini al
        pg_conninfo = parse_postgres_url(POSTGRES_URL)

        print("🔍 Bağlantılar kuruluyor...")

        # SQLite bağlantısı
        sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cursor = sqlite_conn.cursor()

        # PostgreSQL bağlantısı
        pg_conn = psycopg.connect(pg_conninfo)
        pg_cursor = pg_conn.cursor()

        print("✅ Bağlantılar başarılı!")

        # Tabloları sırayla migrate et (foreign key sırasına göre)
        tables = [
            'users',
            'categories',
            'products',
            'stock_movements',
            'count_sessions',
            'count_items',
            'recipes',
            'recipe_items',
            'production_records',
            'production_consumptions'
        ]

        for table in tables:
            print(f"\n📦 {table} tablosu migrate ediliyor...")

            try:
                # SQLite'dan verileri al
                sqlite_cursor.execute(f"SELECT * FROM {table}")
                rows = sqlite_cursor.fetchall()

                if not rows:
                    print(f"   ℹ️  {table} tablosu boş, atlanıyor.")
                    continue

                # Kolon isimlerini al
                columns = [description[0] for description in sqlite_cursor.description]

                # PostgreSQL'e verileri ekle
                # Önce tabloyu temizle
                pg_cursor.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")

                # Verileri ekle
                values = [tuple(row) for row in rows]
                columns_str = ', '.join(columns)
                placeholders = ', '.join(['%s'] * len(columns))

                insert_query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"

                # psycopg3 ile batch insert
                with pg_cursor.copy(f"COPY {table} ({columns_str}) FROM STDIN") as copy:
                    for row in values:
                        copy.write_row(row)

                # Sequence'leri güncelle (ID sütunları için)
                if 'id' in columns:
                    pg_cursor.execute(f"""
                        SELECT setval(pg_get_serial_sequence('{table}', 'id'),
                                      COALESCE((SELECT MAX(id) FROM {table}), 1),
                                      true)
                    """)

                pg_conn.commit()
                print(f"   ✅ {len(rows)} kayıt migrate edildi.")

            except Exception as e:
                print(f"   ❌ {table} hatası: {str(e)}")
                pg_conn.rollback()
                continue

        # Bağlantıları kapat
        sqlite_conn.close()
        pg_conn.close()

        print("\n" + "="*50)
        print("✅ Migration tamamlandı!")
        print("="*50)
        return True

    except Exception as e:
        print(f"❌ Kritik hata: {str(e)}")
        return False

if __name__ == '__main__':
    print("="*50)
    print("  CELMAK Stok - SQLite -> PostgreSQL Migration")
    print("="*50)

    confirm = input("\n[!] Bu islem PostgreSQL veritabanindaki mevcut verileri silecek!\n   Devam etmek istiyor musunuz? (evet/hayir): ")

    if confirm.lower() in ['evet', 'e', 'yes', 'y']:
        migrate_data()
    else:
        print("[X] Migration iptal edildi.")
