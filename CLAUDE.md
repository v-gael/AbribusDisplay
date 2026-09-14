# CLAUDE.md

Ce fichier guide Claude Code sur ce projet. Le contexte détaillé
(architecture, conventions, fichiers clés) est dans `AGENTS.md` — Claude doit
le lire en premier, ce qui suit ne fait que le compléter côté workflow.

@AGENTS.md

## Commandes utiles

```bash
# Dev local sans Docker
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# .env est versionné (valeurs par défaut), ne pas y toucher : créer .env.local
# pour renseigner TOKEN, API_URL, etc. (surcharges), voir README
python -m src.main

# Dev avec Docker (mode fichier, override auto-chargé)
docker compose up --build

# Build/déploiement Pi (ne pas utiliser docker-compose.override.yml sur le Pi)
docker compose -f docker-compose.yml up -d --build
```

Aucun linter/formatter n'est configuré pour l'instant. Si tu en ajoutes un
(`ruff`, `black`...), documente-le ici et dans le README plutôt que de
supposer son existence.

## Comment aborder les tâches sur ce repo

- **Modif du rendu visuel** (`src/renderer.py`) : toujours vérifier le
  résultat en générant une image (voir snippet dans `AGENTS.md`) avant de
  conclure — les problèmes de mise en page (chevauchement de texte, colonnes
  trop étroites) ne se voient qu'à l'image, pas à la lecture du code.
- **Nouvelle variable de config** : l'ajouter dans `Settings` (`src/config.py`),
  dans le tableau du `README.md`, et dans `.env` avec sa valeur par défaut
  (`.env` est versionné, c'est lui l'exemple à maintenir). Ne pas mettre de
  secret dedans (`TOKEN`, `API_URL`, ...) : ça reste réservé à `.env.local`
  (non versionné, jamais modifié dans `.env`).
- **Modif touchant les 2 threads** (`src/main.py`, `src/state.py`) : bien
  vérifier qu'on ne réintroduit pas de blocage croisé entre fetch et render,
  et que la règle "on garde les dernières données valides en cas d'erreur"
  reste respectée.
- **Docker** : si tu changes `docker-compose.yml`, vérifie l'effet combiné
  avec `docker-compose.override.yml` (il est chargé automatiquement en local).

## Ce que Claude ne doit pas supposer

- La police **Roboto Condensed Bold** est embarquée dans le repo sous
  `assets/fonts/` (`.ttf` + licence SIL Open Font License 1.1, voir son
  `README.md`). C'est une instance statique Bold générée depuis la police
  variable officielle — ne pas la remplacer par le fichier variable brut
  (`RobotoCondensed[wght].ttf`), le renderer ne pilote pas les axes de
  variation. Ne pas la retélécharger ni la modifier sans raison.
- Il n'y a pas de tests automatisés ni de CI pour l'instant — ne pas
  inventer de commande `pytest` ou de pipeline qui n'existe pas.
