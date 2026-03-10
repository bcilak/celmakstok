-- PostgreSQL veritabanını temizle (sadece kullanıcılar kalsın)
-- Production sunucuda şu şekilde çalıştırın:
-- psql -U celmak_user -d celmak_stok -f clean_db.sql

-- Önce foreign key kontrollerini geçici olarak kapat
SET session_replication_role = 'replica';

-- BOM (Bill of Materials) tabloları
TRUNCATE TABLE bom_edges CASCADE;
TRUNCATE TABLE bom_nodes CASCADE;
TRUNCATE TABLE bom_items CASCADE;

-- Üretim tabloları
TRUNCATE TABLE production_records CASCADE;

-- Ürün ve stok tabloları
TRUNCATE TABLE location_stock CASCADE;
TRUNCATE TABLE stock_movements CASCADE;
TRUNCATE TABLE products CASCADE;

-- Kategori ve lokasyon tabloları
TRUNCATE TABLE categories CASCADE;
TRUNCATE TABLE locations CASCADE;

-- Sayım tabloları
TRUNCATE TABLE counting_items CASCADE;
TRUNCATE TABLE counting_sessions CASCADE;

-- Foreign key kontrollerini tekrar aç
SET session_replication_role = 'origin';

-- Sonuç özeti
SELECT 'Veritabanı temizlendi! Sadece kullanıcılar korundu.' as sonuc;
SELECT tablename, n_tup_ins as kayit_sayisi 
FROM pg_stat_user_tables 
WHERE schemaname = 'public' 
ORDER BY tablename;
