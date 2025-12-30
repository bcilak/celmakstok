"""
Yerel PostgreSQL veritabanından sunucu PostgreSQL'e veri aktarma scripti
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Yerel ve sunucu veritabanı bağlantıları
LOCAL_DB = "postgresql+psycopg://celmak_user:CelmakStok2024!@localhost:5432/celmak_stok"
SERVER_DB = "postgresql+psycopg://celmak_user:CelmakStok2024!@152.53.241.81:5432/celmak_stok"

print("=" * 80)
print("VERİ AKTARMA BAŞLIYOR")
print("=" * 80)

# Veritabanı bağlantıları
local_engine = create_engine(LOCAL_DB)
server_engine = create_engine(SERVER_DB)

LocalSession = sessionmaker(bind=local_engine)
ServerSession = sessionmaker(bind=server_engine)

local_session = LocalSession()
server_session = ServerSession()

# Aktarılacak tablolar (sıralama önemli - foreign key'ler için)
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
    'production_consumptions',
    'stock_current'
]

try:
    for table in tables:
        print(f"\n>> {table} tablosu aktariliyor...")

        # Yerel veritabanından veriyi çek
        result = local_session.execute(text(f"SELECT * FROM {table}"))
        rows = result.fetchall()
        columns = result.keys()

        if not rows:
            print(f"   [!] {table} tablosu bos, atlandi.")
            continue

        print(f"   [i] {len(rows)} kayit bulundu")

        # Sunucuda mevcut verileri temizle (opsiyonel)
        # server_session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))

        # Verileri sunucuya aktar
        inserted = 0
        for row in rows:
            # Sütun isimlerini ve değerlerini hazırla
            cols = ', '.join(columns)
            placeholders = ', '.join([f":{col}" for col in columns])

            # Değerleri dict'e çevir
            values = dict(zip(columns, row))

            try:
                server_session.execute(
                    text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"),
                    values
                )
                inserted += 1
            except Exception as e:
                # Duplicate key hatası muhtemelen
                if 'duplicate' in str(e).lower() or 'unique' in str(e).lower():
                    print(f"   [!] Kayit zaten mevcut, atlandi: {values.get('id', 'N/A')}")
                else:
                    print(f"   [X] Hata: {e}")

        server_session.commit()
        print(f"   [OK] {inserted} kayit aktarildi")

        # Sequence'leri güncelle (ID sıralaması için)
        try:
            max_id_result = server_session.execute(text(f"SELECT MAX(id) FROM {table}"))
            max_id = max_id_result.scalar()
            if max_id:
                server_session.execute(
                    text(f"SELECT setval('{table}_id_seq', {max_id}, true)")
                )
                server_session.commit()
                print(f"   [~] Sequence guncellendi (max_id: {max_id})")
        except Exception as e:
            print(f"   [!] Sequence guncellenemedi: {e}")

    print("\n" + "=" * 80)
    print("[OK] TUM VERILER BASARIYLA AKTARILDI!")
    print("=" * 80)

except Exception as e:
    print(f"\n[HATA] {e}")
    server_session.rollback()
    raise

finally:
    local_session.close()
    server_session.close()

print("\n[*] Islem tamamlandi. Sunucudaki veritabanini kontrol edebilirsiniz.")
