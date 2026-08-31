-- PostgreSQL tuning for SEC bulk loading.
--
-- Applies bulk-load-friendly settings:
--   * Database-level (per-session, safe) via ALTER DATABASE ... SET
--   * Cluster-level via ALTER SYSTEM ... (requires pg_reload_conf())
--
-- These do NOT disable WAL or change crash-recovery guarantees; they only
-- reduce checkpoint frequency and give maintenance/sort operations more memory.

-- Database-level settings (context = user).
ALTER DATABASE financial_database SET maintenance_work_mem = '512MB';
ALTER DATABASE financial_database SET work_mem = '64MB';
ALTER DATABASE financial_database SET synchronous_commit = off;

-- Cluster-level settings (context = sighup, applied on reload).
ALTER SYSTEM SET max_wal_size = '4GB';
ALTER SYSTEM SET checkpoint_timeout = '15min';
SELECT pg_reload_conf();
