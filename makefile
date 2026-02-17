# --- Config ---
VENV_DIR := .venv
PY := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip

DJANGO_SETTINGS_MODULE ?= talentmap.settings

.PHONY: help install run migrate mmigrate shell test test-unit test-e2e playwright-install

help:
	@echo "Targets:"
	@echo "  install            Instala dependencias"
	@echo "  run                Arranca Django (localhost:8000)"
	@echo "  migrate            migrate"
	@echo "  mmigrate           makemigrations + migrate"
	@echo "  shell              Django shell"
	@echo "  test-unit          Tests unitarios (Django)"
	@echo "  test-e2e           Tests e2e (pytest + playwright)"
	@echo "  playwright-install Instala navegadores de playwright"

install:
	$(PIP) install -r requirements.txt
	# deps de testing (si no las tienes en requirements.txt)
	$(PIP) install -U pytest pytest-django playwright

run:
	@-lsof -ti:8000 | xargs -r kill -9 || true
	.venv/bin/python manage.py runserver 0.0.0.0:8000


migrate:
	$(PY) manage.py migrate

mmigrate:
	$(PY) manage.py makemigrations
	$(PY) manage.py migrate

shell:
	$(PY) manage.py shell

test: test-unit

test-unit:
	$(PY) manage.py test

test-e2e:
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS_MODULE) $(PY) -m pytest -q e2e

playwright-install:
	$(PY) -m playwright install
