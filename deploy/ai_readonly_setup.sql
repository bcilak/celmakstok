-- SQL snippet to create a read-only DB user for AI integrations (Postgres)
-- Run as a superuser on the database server (adjust names/passwords)

-- 1) Create the role
CREATE ROLE ai_user LOGIN PASSWORD 'replace_with_strong_password';

-- 2) Grant connection and usage
GRANT CONNECT ON DATABASE your_database_name TO ai_user;
GRANT USAGE ON SCHEMA public TO ai_user;

-- 3) Grant read-only on existing tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO ai_user;

-- 4) Ensure future tables are also selectable
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ai_user;

-- 5) Optional: limit connection resources via pg_hba.conf / pg_user settings

-- Note: replace 'your_database_name' and password with secure values.
