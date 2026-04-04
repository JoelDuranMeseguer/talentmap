# TalentMap

TalentMap is a Django app for employee talent mapping with:
- invitation-based onboarding,
- manager/HR evaluation permissions,
- quantitative weighted goals,
- qualitative competency progression,
- 9-box talent categorization.

## Quickstart (development)

1. Create environment and install deps:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```
2. Configure env vars:
   ```bash
   cp .env.example .env
   ```
3. Run migrations and create admin:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```
4. Run server:
   ```bash
   python manage.py runserver
   ```

## Tests

```bash
pytest
```

E2E tests are marked with `e2e` and skipped by default. Run with:

```bash
pytest -m e2e
```

## Settings structure

- `talentmap/settings/base.py`: shared config.
- `talentmap/settings/dev.py`: local development defaults.
- `talentmap/settings/prod.py`: hardened production defaults.

Default module is `talentmap.settings` (loads dev settings). For production:

```bash
export DJANGO_SETTINGS_MODULE=talentmap.settings.prod
```

## Production notes

- Use PostgreSQL by setting `DATABASE_URL`.
- Set a strong `SECRET_KEY`.
- Set `DEBUG=False` and valid `ALLOWED_HOSTS`.
- Configure `CSRF_TRUSTED_ORIGINS` and HTTPS headers behind reverse proxy.
- Run `collectstatic` in deploy pipeline.

## Management helpers

Recompute scores manually:

```bash
python manage.py recompute_scores
```
