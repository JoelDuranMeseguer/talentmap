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
   or:
   ```bash
   make run
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

- Install production dependencies with `pip install -r requirements-prod.txt`.
- Use PostgreSQL by setting `DATABASE_URL`.
- Set a strong `SECRET_KEY`.
- Set `DEBUG=False` and valid `ALLOWED_HOSTS`.
- Configure `CSRF_TRUSTED_ORIGINS` and HTTPS headers behind reverse proxy.
- Run `collectstatic` in deploy pipeline.
- Use `DJANGO_SETTINGS_MODULE=talentmap.settings.prod`.

Full deployment guide: [`docs/deployment.md`](docs/deployment.md)

## Production checklist

- [ ] `DJANGO_SETTINGS_MODULE=talentmap.settings.prod`
- [ ] `SECRET_KEY` is set and not default
- [ ] `DEBUG=False`
- [ ] `ALLOWED_HOSTS` configured
- [ ] `DATABASE_URL` points to PostgreSQL
- [ ] `CSRF_TRUSTED_ORIGINS` configured for public domain(s)
- [ ] `python manage.py migrate`
- [ ] `python manage.py collectstatic --noinput`
- [ ] `python manage.py check --deploy`
- [ ] Gunicorn/process manager configured
- [ ] SMTP provider configured and tested (`EMAIL_*`)
- [ ] Daily DB backups + restore test defined
- [ ] Application logging/monitoring configured (Sentry/APM + metrics)
- [ ] CI/CD pipeline runs tests and `check --deploy`

## Management helpers

Recompute scores manually:

```bash
python manage.py recompute_scores
```

## What is still intentionally out of scope

This repository is now implementation-ready for an internal MVP, but still expects company-specific ops setup:

- Infrastructure provisioning (DB, secrets manager, TLS certs, reverse proxy).
- Centralized observability (error tracking, logs retention, alerts).
- Disaster recovery procedures (backup retention and restore drills).
