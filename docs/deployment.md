# Deployment Notes (Production)

## 1) Install dependencies

```bash
pip install -r requirements-prod.txt
```

## 2) Environment

Set at minimum:

- `DJANGO_SETTINGS_MODULE=talentmap.settings.prod`
- `SECRET_KEY=<strong-random-value>`
- `DEBUG=False`
- `ALLOWED_HOSTS=talentmap.example.com`
- `DATABASE_URL=postgres://...`
- `CSRF_TRUSTED_ORIGINS=https://talentmap.example.com`
- `SITE_URL=https://talentmap.example.com`

## 3) Build/runtime steps

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
python manage.py test
```

## 4) Process model

Example with Gunicorn:

```bash
gunicorn talentmap.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

Run behind a reverse proxy (Nginx/ALB/etc.) with HTTPS termination and `X-Forwarded-Proto` passed through.

## 5) Post-deploy smoke checks

- Login works for HR and manager user.
- Invite flow: create invitation, open token URL, register account.
- Team overview page loads and can edit quantitative/qualitative forms.
- 9-box loads and modal actions open expected links.

## 6) Optional periodic tasks

Recompute scores after bulk updates/imports:

```bash
python manage.py recompute_scores
```
