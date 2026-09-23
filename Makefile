.DEFAULT_GOAL := help
.PHONY: help venv venv-dev run render-test demo-gif dev pi deploy down ps logs shell \
        clean lint format format-check typecheck check outdated

# Connexion au Pi pour `make deploy`. PI_HOST n'a pas de valeur par défaut
# (propre à chaque installation) : le passer en ligne de commande
# (`make deploy PI_HOST=<IP_DU_PI>`) ou le définir une fois pour toutes dans
# deploy.local.mk (non versionné, modèle : deploy.local.mk.example).
-include deploy.local.mk
PI_USER ?= admin
PI_HOST ?=
PI_DIR  ?= ~/abribusdisplay
PI := $(PI_USER)@$(PI_HOST)

## —— Environnement ————————————————————————————————————————————————————————
# Cibles fichiers (stamps) : contrairement aux cibles .PHONY ci-dessous,
# celles-ci ne réinstallent rien si requirements*.txt n'a pas changé depuis
# le dernier `make venv`/`venv-dev` — évite un `pip install` à chaque `make run`.
.venv/bin/python:
	python3 -m venv .venv

.venv/.deps: requirements.txt .venv/bin/python
	.venv/bin/pip install -r requirements.txt
	touch .venv/.deps

.venv/.dev-deps: requirements-dev.txt .venv/.deps
	.venv/bin/pip install -r requirements-dev.txt
	touch .venv/.dev-deps

venv: .venv/.deps ## Crée le virtualenv et installe les dépendances

venv-dev: .venv/.dev-deps ## venv + outils de qualité (ruff, mypy — voir requirements-dev.txt)

## —— Lancer l'app —————————————————————————————————————————————————————————
run: venv ## Lance l'app en local (sans Docker, nécessite venv + .env)
	.venv/bin/python -m src.main

dev: ## Dev avec Docker (mode fichier, docker-compose.override.yml auto-chargé)
	docker compose up --build

pi: ## Build/déploiement Pi (ignore docker-compose.override.yml) — build directement sur le Pi, coûteux en espace disque
	docker compose -f docker-compose.yml up -d --build

deploy: ## Build l'image en local (Mac arm64) et la déploie sur le Pi sans jamais builder là-bas (voir README)
	[ -n "$(PI_HOST)" ] || { echo "Erreur: PI_HOST non défini — lancer \`make deploy PI_HOST=<IP_DU_PI>\` ou le définir dans deploy.local.mk (voir deploy.local.mk.example)."; exit 1; }
	[ -f .env.pi.local ] || { echo "Erreur: .env.pi.local manquant (non versionné) — créer ce fichier avec les surcharges du déploiement Pi (DISPLAY_MODE=fbi, TOKEN, API_URL...), voir README."; exit 1; }
	docker build -t abribusdisplay:latest .
	ssh $(PI) 'mkdir -p $(PI_DIR)'
	rsync -a docker-compose.yml .env $(PI):$(PI_DIR)/
	rsync -a .env.pi.local $(PI):$(PI_DIR)/.env.local
	docker save abribusdisplay:latest | ssh $(PI) docker load
	ssh $(PI) 'cd $(PI_DIR) && docker compose up -d && docker image prune -f'

down: ## Arrête les conteneurs Docker
	docker compose down

ps: ## Liste les conteneurs Docker du projet et leur statut
	docker compose ps

logs: ## Suit les logs du conteneur (Ctrl+C pour quitter)
	docker compose logs -f

shell: ## Ouvre un shell dans le conteneur en cours d'exécution (debug)
	docker compose exec abribusdisplay sh

## —— Rendu ————————————————————————————————————————————————————————————————
render-test: venv ## Régénère les aperçus dans output/ depuis les JSON de tests/ (vérif visuelle du rendu, voir tests/README.md)
	.venv/bin/python tests/render_example.py

demo-gif: venv ## Régénère docs/demo.gif (aperçu animé du README) depuis docs/demo.json
	.venv/bin/python docs/make_demo_gif.py

## —— Qualité de code —————————————————————————————————————————————————————
lint: venv-dev ## Vérifie le style/les erreurs courantes (ruff check)
	.venv/bin/ruff check .

format: venv-dev ## Reformate le code (ruff format)
	.venv/bin/ruff format .

format-check: venv-dev ## Vérifie le formatage sans modifier les fichiers (ruff format --check)
	.venv/bin/ruff format --check .

typecheck: venv-dev ## Analyse statique des types (mypy)
	.venv/bin/mypy

check: lint format-check typecheck ## Lance lint + format-check + typecheck (équivalent d'une vérif CI)

outdated: venv ## Liste les dépendances (requirements*.txt) ayant une version plus récente disponible
	.venv/bin/pip list --outdated

## —— Nettoyage ————————————————————————————————————————————————————————————
clean: ## Supprime le virtualenv, les caches d'outils et l'image générée
	rm -rf .venv output/*.png .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

## —— Aide —————————————————————————————————————————————————————————————————
help: ## Affiche cette aide
	@grep -E '(^[a-zA-Z0-9_-]+:.*?## .*$$)|(^## )' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; /^## / {printf "\n\033[1m%s\033[0m\n", substr($$0, 4)} /^[a-zA-Z0-9_-]+:/ {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
