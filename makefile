# --- Config ---
VENV_DIR := .venv
PY := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip

DJANGO_SETTINGS_MODULE ?= talentmap.settings

.PHONY: help install install-prod run migrate makemigrations mmigrate shell test test-unit test-e2e playwright-install check-deploy

help:
	@echo "Targets:"
	@echo "  install            Instala dependencias de desarrollo"
	@echo "  install-prod       Instala dependencias de producción"
	@echo "  run                Arranca Django (localhost:8000)"
	@echo "  migrate            migrate"
	@echo "  makemigrations     makemigrations + migrate"
	@echo "  shell              Django shell"
	@echo "  test-unit          Tests unitarios (Django)"
	@echo "  test-e2e           Tests e2e (pytest + playwright)"
	@echo "  playwright-install Instala navegadores de playwright"
	@echo "  check-deploy       Validaciones de seguridad para producción"

install:
	$(PIP) install -r requirements-dev.txt

install-prod:
	$(PIP) install -r requirements-prod.txt

run:
	@-lsof -ti:8000 | xargs -r kill -9 || true
	$(PY) manage.py runserver 0.0.0.0:8000


migrate:
	$(PY) manage.py migrate

makemigrations:
	$(PY) manage.py makemigrations
	$(PY) manage.py migrate

mmigrate: makemigrations

shell:
	$(PY) manage.py shell

test: test-unit

test-unit:
	$(PY) manage.py test

test-e2e:
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS_MODULE) $(PY) -m pytest -q e2e

playwright-install:
	$(PY) -m playwright install

check-deploy:
	DJANGO_SETTINGS_MODULE=talentmap.settings.prod $(PY) manage.py check --deploy
