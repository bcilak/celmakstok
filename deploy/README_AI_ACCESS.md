AI integration setup - steps to enable secure read-only access

1) Create read-only DB user (Postgres)
   - Run the SQL in `deploy/ai_readonly_setup.sql` as a DB superuser. Replace database name and password.

2) Set environment variables on the app server
   - `AI_API_KEY` (strong secret)
   - `AI_ALLOWED_IPS` (optional, comma-separated)
   - `DATABASE_URL` should remain the same; do NOT put superuser credentials in env for AI.

3) Ensure dependencies
   - `python-dateutil` is required (already in `requirements.txt`).
   - Install requirements in the virtualenv:

```bash
pip install -r requirements.txt
```

4) Apply DB performance migration (indexes)
   - Create a migration file with Alembic if not already, or use the provided `migrations/versions/add_indexes_for_ai_access.py` and run:

```bash
flask db upgrade
```

5) Restart the app (gunicorn/systemd) to pick up new blueprint and config.

6) Test endpoint
```bash
curl -H "X-API-Key: ${AI_API_KEY}" "https://yourdomain/internal/ai/user_activity/12?limit=50"
```

7) Monitor and tune
   - Watch logs for 401/403 or DB timeouts.
   - Add more indexes if queries are slow.

Security notes:
 - Prefer HTTP-level protections via nginx (allow only AI IPs) in addition to API key.
 - Rotate `AI_API_KEY` periodically.
