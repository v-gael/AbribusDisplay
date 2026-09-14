.DEFAULT_GOAL := help
.PHONY: help venv install run render-test dev pi down clean

## —— Environnement ————————————————————————————————————————————————————————
venv: ## Crée le virtualenv et installe les dépendances
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

install: venv ## Alias de venv (vérifie que .env existe — il est versionné, voir README)
	[ -f .env ] || { echo "Erreur: .env manquant (fichier versionné) — voir README, section Configuration."; exit 1; }

## —— Lancer l'app —————————————————————————————————————————————————————————
run: ## Lance l'app en local (sans Docker, nécessite venv + .env)
	.venv/bin/python -m src.main

dev: ## Dev avec Docker (mode fichier, docker-compose.override.yml auto-chargé)
	docker compose up --build

pi: ## Build/déploiement Pi (ignore docker-compose.override.yml)
	docker compose -f docker-compose.yml up -d --build

down: ## Arrête les conteneurs Docker
	docker compose down

## —— Rendu ————————————————————————————————————————————————————————————————
render-test: ## Régénère les aperçus dans output/ depuis les JSON de tests/ (vérif visuelle du rendu, voir tests/README.md)
	.venv/bin/python tests/render_example.py

## —— Nettoyage ————————————————————————————————————————————————————————————
clean: ## Supprime le virtualenv et l'image générée
	rm -rf .venv output/*.png

## —— Aide —————————————————————————————————————————————————————————————————
help: ## Affiche cette aide
	@grep -E '(^[a-zA-Z0-9_-]+:.*?## .*$$)|(^## )' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; /^## / {printf "\n\033[1m%s\033[0m\n", substr($$0, 4)} /^[a-zA-Z0-9_-]+:/ {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
