# AGENTS.md

Contexte pour tout agent de codage (Claude Code, Codex, etc.) travaillant sur
ce projet. Voir `README.md` pour la doc utilisateur complète.

## Le projet en une phrase

Génère une image PNG (panneau "prochains passages" de bus) depuis une API
JSON, et l'affiche sur un Raspberry Pi 3B+ via `fbi` sur `/dev/fb1` (ou
l'écrit simplement sur disque en mode dev).

## Architecture — à connaître avant de toucher au code

Deux threads tournent en parallèle autour d'un état partagé (`src/state.py`,
`AppState`, protégé par un `Lock`) :

- **fetcher** (`src/main.py::_fetch_loop`) : appelle l'API toutes les
  `CALL_RATE` secondes, remplit `AppState`.
- **renderer** (`src/main.py::_render_loop`) : régénère l'image toutes les
  `REFRESH_RATE` secondes à partir d'`AppState`, l'écrit sur disque, puis
  pilote l'affichage (`src/display.py`).

**Règle métier importante** : si un appel API échoue mais qu'on a déjà des
données valides en mémoire, on les garde (`AppState.set_error` ne change pas
le statut si `self.displays` n'est pas vide — il lève seulement
`has_api_error`, qui affiche un pictogramme discret). Ne pas casser cette règle sans le
signaler explicitement — c'est ce qui évite qu'une coupure réseau passagère
fasse clignoter le panneau vers un écran d'erreur.

Round-robin sur `displays` : `AppState.next_display()` avance l'index à
chaque appel — un seul appelant (le renderer) doit l'invoquer par cycle,
sinon les éléments seront sautés.

## Fichiers clés

| Fichier | Rôle |
|---|---|
| `src/config.py` | Charge `.env` (versionné, valeurs par défaut) puis `.env.local` (override, non versionné). Toute nouvelle variable d'env passe par ici, typée. |
| `src/models.py` | Dataclasses du JSON API (`NextPassagesResponse`, `DisplayItem`, `NextPassage`). |
| `src/api_client.py` | Appel HTTP. `InvalidTokenError` pour 401, `ApiError` pour le reste. |
| `src/renderer.py` | Tout le dessin Pillow. Les couleurs/polices viennent de `Settings`, jamais en dur. |
| `src/display.py` | `FbiDisplay` (Pi, signal `SIGUSR1` à `fbi`) vs `FileDisplay` (dev). |
| `src/main.py` | Orchestration, arrêt propre sur `SIGINT`/`SIGTERM`. |

## Conventions

- Version de l'application : `__version__` dans `src/__init__.py`, affichée en
  bas à droite du panneau. La mettre à jour dans la branche `release/X.Y.Z`
  (gitflow), pour qu'elle corresponde au tag `vX.Y.Z`.
- Commentaires et docstrings en français.
- Pas de couleur ni de dimension en dur dans `renderer.py` : tout passe par
  `Settings` (dataclass chargée depuis l'env).
- Écriture de fichier atomique pour l'image (`renderer.save_image` écrit dans
  un `.tmp` puis `replace()`) — ne pas revenir à un `image.save()` direct sur
  le chemin final, sinon `fbi`/le viewer peut lire un fichier tronqué.

## Docker

- `docker-compose.yml` = profil Pi par défaut (accès `/dev/fb1`, `DISPLAY_MODE=fbi`
  attendu — à définir dans `.env.local`, pas dans `.env` qui garde `file` par
  défaut). Avec `make deploy`, ce `.env.local` du Pi est le fichier
  `.env.pi.local` du Mac (non versionné, modèle : `.env.pi.local.example`),
  poussé à chaque déploiement.
- `make deploy` build l'image sur le Mac et la transfère au Pi par SSH (pas
  de build sur le Pi). `setup-ecran-pi.sh` prépare un Pi neuf (écran SPI,
  Docker), une seule fois, voir README "Préparer le Pi".
- `docker-compose.override.yml` est **auto-chargé** par `docker compose up`
  et force le mode dev (`DISPLAY_MODE=file`, pas de device framebuffer). Ne
  pas déployer ce fichier sur le Pi.

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
# ou, recommandé : build sur le Mac puis transfert (voir README)
make deploy

# Aperçus du rendu depuis les JSON de tests/ (écrit dans output/)
make render-test
```

**ruff** (lint + format) et **mypy** (`strict`) sont configurés dans
`pyproject.toml`. Outils installés via `requirements-dev.txt` (pas dans
l'image Docker — `Dockerfile` n'installe que `requirements.txt`) :

```bash
make venv-dev   # une fois, installe ruff + mypy dans .venv
make check      # lint + format-check + typecheck
```

CI : GitHub Actions (`.github/workflows/check.yml`) lance `make check` sous
Python 3.11 à chaque push. Le lancer quand même en local avant de
committer. Si tu ajoutes un autre outil, documente-le ici et dans le
README plutôt que de supposer son existence.

## Comment aborder les tâches sur ce repo

- **Modif du rendu visuel** (`src/renderer.py`) : toujours vérifier le
  résultat en générant une image (voir snippet ci-dessous) avant de
  conclure — les problèmes de mise en page (chevauchement de texte, colonnes
  trop étroites) ne se voient qu'à l'image, pas à la lecture du code.
  Si le changement est visible, relancer `make demo-gif` pour mettre à jour
  l'aperçu animé du README (`docs/demo.gif`).
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
- Il n'y a pas de tests automatisés pour l'instant, et la CI ne fait que
  `make check` — ne pas inventer de commande `pytest` ou d'étape de
  pipeline qui n'existe pas.

## Tester une modification du rendu

Pas de suite de tests automatisés pour l'instant (voir "Pistes d'évolution"
du README). Pour vérifier visuellement un changement dans `renderer.py` :

```python
from src.config import Settings
from src.state import AppState
from src.models import NextPassagesResponse
from src.renderer import render, save_image
import json
from datetime import datetime, timezone

settings = Settings.load()

data = json.load(open("chemin/vers/un_exemple.json"))
state = AppState()
state.set_ok(NextPassagesResponse.from_dict(data).displays, datetime.now(timezone.utc))
save_image(render(state, settings), "output/preview.png2")
```

Penser à tester les 4 cas : réponse normale, `displays` vide,
`AppState().set_error(Status.INVALID_TOKEN)` et
`AppState().set_error(Status.ERROR)` ("Données indisponibles"). Et, pour le
pictogramme réseau, `set_ok(...)` suivi de `set_error(...)` : les données
doivent rester affichées.

## Ne pas faire

- Ne pas coder en dur `API_URL`, `TOKEN` ou toute couleur — tout passe par
  `.env` / `.env.local` via `Settings`.
- Ne pas toucher à `.env` (versionné, valeurs par défaut partagées) pour y
  mettre `TOKEN`, `API_URL` ou toute valeur spécifique à un déploiement —
  ça va dans `.env.local` (non versionné, chargé en override).
- Ne pas ajouter de logique de rendu qui suppose que `displays` a toujours
  au moins un élément : `is_empty`, le cas 401 et le cas "Données
  indisponibles" (`Status.ERROR`) doivent rester gérés.
- Ne pas bloquer le thread renderer sur un appel réseau : le fetch et le
  rendu doivent rester strictement séparés.
