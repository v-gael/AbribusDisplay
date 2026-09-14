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
données valides en mémoire, on les garde (`AppState.set_error` ne fait rien
si `self.displays` n'est pas vide). Ne pas casser cette règle sans le
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

- Commentaires et docstrings en français (cohérence avec le reste du projet
  et l'auteur).
- Pas de couleur ni de dimension en dur dans `renderer.py` : tout passe par
  `Settings` (dataclass chargée depuis l'env).
- Écriture de fichier atomique pour l'image (`renderer.save_image` écrit dans
  un `.tmp` puis `replace()`) — ne pas revenir à un `image.save()` direct sur
  le chemin final, sinon `fbi`/le viewer peut lire un fichier tronqué.
- La police (`FONT_PATH`) peut être absente sur une machine de dev : le
  fallback vers `ImageFont.load_default()` doit rester silencieux côté
  fonctionnement (juste un `logger.warning`), jamais une exception qui
  casse le rendu.

## Docker

- `docker-compose.yml` = profil Pi par défaut (accès `/dev/fb1`, `DISPLAY_MODE=fbi`
  attendu — à définir dans `.env.local`, pas dans `.env` qui garde `file` par
  défaut).
- `docker-compose.override.yml` est **auto-chargé** par `docker compose up`
  et force le mode dev (`DISPLAY_MODE=file`, pas de device framebuffer). Ne
  pas déployer ce fichier sur le Pi.

## Tester une modification du rendu

Pas de suite de tests automatisés pour l'instant (voir "Pistes d'évolution"
du README). Pour vérifier visuellement un changement dans `renderer.py` :

```python
from src.config import Settings
from src.state import AppState
from src.models import NextPassagesResponse
from src.renderer import render, save_image
import json, dataclasses
from datetime import datetime, timezone

settings = Settings.load()
# si pas de police installée localement, pointer vers une TTF de test :
# settings = dataclasses.replace(settings, font_path="/chemin/vers/une.ttf")

data = json.load(open("chemin/vers/un_exemple.json"))
state = AppState()
state.set_ok(NextPassagesResponse.from_dict(data).displays, datetime.now(timezone.utc))
save_image(render(state, settings), "output/preview.png")
```

Penser à tester les 3 cas : réponse normale, `displays` vide, et
`AppState().set_error(Status.INVALID_TOKEN)`.

## Ne pas faire

- Ne pas coder en dur `API_URL`, `TOKEN` ou toute couleur — tout passe par
  `.env` / `.env.local` via `Settings`.
- Ne pas toucher à `.env` (versionné, valeurs par défaut partagées) pour y
  mettre `TOKEN`, `API_URL` ou toute valeur spécifique à un déploiement —
  ça va dans `.env.local` (non versionné, chargé en override).
- Ne pas ajouter de logique de rendu qui suppose que `displays` a toujours
  au moins un élément : `is_empty` et le cas 401 doivent rester gérés.
- Ne pas bloquer le thread renderer sur un appel réseau : le fetch et le
  rendu doivent rester strictement séparés.
