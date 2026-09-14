# AbribusDisplay

Générateur d'affichage "prochains passages" (type panneau d'arrêt de bus) pour
Raspberry Pi 3B+, affiché sur écran via `fbi` (`/dev/fb1`), avec un mode fichier
pour développer sur Mac/Linux sans matériel.

## Architecture

Deux boucles tournent en parallèle dans le même processus (threads), à des
rythmes différents, autour d'un état partagé thread-safe :

```
                 CALL_RATE (ex: 60s)
   ┌────────────────────────────────────────┐
   │             Thread fetcher             │
   │ appelle API_URL → parse JSON → AppState│
   └────────────────────────────────────────┘
                        │
                        ▼
                  AppState (Lock)
                        ▲
                        │
   ┌────────────────────────────────────────┐
   │              Thread renderer           │
   │  lit AppState → Pillow → PNG → display │
   └────────────────────────────────────────┘
                 REFRESH_RATE (ex: 5s)
```

- **`src/api_client.py`** : appelle `API_URL`, distingue `401` (token invalide)
  des autres erreurs (réseau, HTTP, JSON invalide).
- **`src/state.py`** (`AppState`) : état partagé protégé par un `Lock`. Règle
  appliquée : si un appel échoue mais qu'on a déjà des données valides en
  mémoire, on les **garde** (l'erreur est loggée mais n'écrase pas l'affichage).
  Les statuts "token invalide" / "erreur" ne s'affichent que si aucune donnée
  valide n'a jamais été reçue.
- **`src/models.py`** : dataclasses `NextPassagesResponse` / `DisplayItem` /
  `NextPassage`, avec calcul de l'écart en minutes par rapport à maintenant.
- **`src/renderer.py`** : dessine l'image (Pillow) selon la maquette : bandeau
  du haut (arrêt + heure), bandeau des en-têtes de colonnes, puis soit le
  tableau des lignes, soit un message centré (cas "vide" / "token invalide").
- **`src/display.py`** : abstraction de la sortie finale :
  - `FbiDisplay` (Pi) : lance `fbi` une seule fois en tâche de fond, puis lui
    envoie `SIGUSR1` à chaque nouvelle image pour qu'il recharge le fichier
    sans clignoter/relancer.
  - `FileDisplay` (dev Mac/Linux) : écrit simplement le PNG sur disque.
- **`src/main.py`** : point d'entrée, démarre les deux threads, gère l'arrêt
  propre sur `SIGINT`/`SIGTERM`, fait un premier appel synchrone au démarrage
  pour ne jamais afficher un écran vide au lancement.

## Les 3 cas d'affichage

| Cas | Déclencheur | Rendu |
|---|---|---|
| Classique | Réponse OK avec des `nextPassages` | Tableau comme sur la maquette |
| Vide | `DisplayItem` sans `nextPassages` | Message centré "Pas de passage prévu actuellement" |
| Token invalide | Réponse `401` (et jamais eu de données valides) | Message centré "Token invalide, vérifier la configuration" |

La liste `displays` est parcourue en round-robin : toutes les `REFRESH_RATE`
secondes, l'image régénérée passe à l'élément suivant, puis on reboucle au
premier.

Dans le cas "Classique", la taille des polices/pastilles est calculée à
partir de `ROWS_PER_SCREEN` (5 par défaut), pas du nombre réel de passages :
avec moins de passages que `ROWS_PER_SCREEN`, l'espace restant reste vide en
bas plutôt que de faire grossir les lignes affichées ; avec plus, elles
rétrécissent pour toutes tenir.

## Configuration (`.env`)

`.env` est versionné à la racine du dépôt et contient déjà les valeurs par
défaut (voir tableau ci-dessous) — ne pas le modifier pour y mettre des
valeurs propres à votre poste ou votre déploiement. Créer plutôt un fichier
`.env.local` (non versionné) pour y renseigner `TOKEN`, `API_URL` et toute
autre surcharge locale (dev ou prod) ; il est chargé en priorité par
`src/config.py`.

| Variable | Rôle |
|---|---|
| `TEXT_STOP_COLOR` | Couleur du nom d'arrêt (ex: TORVILLIERS PARC D ACTIVITES) |
| `TEXT_HOUR_COLOR` | Couleur de l'heure actuelle |
| `TEXT_HEADER_COLOR` | Couleur du texte des en-têtes de colonnes |
| `TEXT_MINUTES_COLOR` | Couleur du texte "X min" |
| `TEXT_DIRECTION_COLOR` | Couleur du texte de la colonne Direction |
| `BACKGROUND_COLOR` | Fond général de l'image (bandeau du haut + lignes du tableau) |
| `HEADER_BACKGROUND_COLOR` | Fond du bandeau des en-têtes de colonnes, et fallback pour `routeColor` |
| `TOKEN` | Token d'authentification (envoyé dans le header `X-Device-Token`) |
| `API_URL` | URL de l'API à interroger |
| `API_VERIFY_SSL` | Vérification du certificat TLS de `API_URL` (`false` en dev local avec certif auto-signé) |
| `CALL_RATE` | Fréquence (s) d'appel de l'API |
| `REFRESH_RATE` | Fréquence (s) de régénération de l'image |
| `IMAGE_WIDTH` / `IMAGE_HEIGHT` | Résolution de l'image générée (adapter à l'écran du Pi) |
| `FONT_PATH` | Chemin vers la police Roboto Condensed Bold |
| `ROWS_PER_SCREEN` | Nombre de lignes de référence pour la taille des polices/pastilles (voir "Les 3 cas d'affichage" ci-dessus) |
| `DISPLAY_MODE` | `fbi` (Pi) ou `file` (dev) |
| `OUTPUT_PATH` | Chemin du PNG généré |
| `FRAMEBUFFER_DEVICE` | Périphérique framebuffer cible (mode `fbi`) |

> Remarque sur `routeColor` / `routeTextColor` : si absents dans le JSON, on
> retombe respectivement sur `HEADER_BACKGROUND_COLOR` et
> `TEXT_DIRECTION_COLOR`.

### Police

La police **Roboto Condensed Bold** est embarquée dans le dépôt sous
`assets/fonts/` (voir `assets/fonts/README.md` pour la licence, SIL Open
Font License 1.1). `FONT_PATH` pointe vers ce fichier par défaut. Si le fichier
venait à manquer, le rendu bascule automatiquement sur la police par défaut
de Pillow (avec un warning dans les logs), pour que le projet reste utilisable
même sans la police.

## Lancer en développement (Mac/Linux, sans Pi)

`docker-compose.override.yml` est chargé automatiquement par `docker compose`
et force `DISPLAY_MODE=file` (pas d'accès `/dev/fb1` nécessaire) :

```bash
# ne pas modifier .env (versionné, valeurs par défaut) : créer .env.local
# pour vos surcharges dev (API_URL, TOKEN, API_VERIFY_SSL=false si certif
# auto-signé...), voir tableau ci-dessus
docker compose up --build
# ou : make dev
```

L'image générée apparaît dans `./output/display.png`, régénérée toutes les
`REFRESH_RATE` secondes. Pour la visualiser confortablement sans rouvrir le
fichier à chaque fois, ouvrez `debug.html` directement dans un navigateur
(double-clic, ou `file://.../debug.html`) : la page recharge
`output/display.png` toutes les secondes. Ça suppose `DISPLAY_MODE=file`
(valeur par défaut de `.env`) — en mode `fbi` (Pi), il n'y a pas de PNG à
afficher de cette façon, `fbi` pilote directement le framebuffer.

Sans Docker :

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# créer .env.local si besoin de surcharges (TOKEN, API_URL...), voir tableau
# ci-dessus — ne pas modifier .env
python -m src.main
# ou : make install && make run
```

## Déployer sur le Raspberry Pi

Sur le Pi, ne pas embarquer `docker-compose.override.yml` (ou le
supprimer/renommer), pour que `docker-compose.yml` seul s'applique :

```bash
# ne pas modifier .env : mettre dans .env.local toutes les valeurs propres à
# ce déploiement (DISPLAY_MODE=fbi, IMAGE_WIDTH/HEIGHT adaptés à l'écran,
# API_URL, TOKEN, etc.)
docker compose up -d --build
# ou : make pi
```

Le conteneur a besoin d'accéder à `/dev/fb1` (déclaré dans
`docker-compose.yml` via `devices:`) et lance `fbi` en tâche de fond ; chaque
régénération d'image lui envoie un signal pour recharger sans clignoter.

## Makefile

Raccourcis pour les commandes ci-dessus (`make help` liste les cibles) :

| Cible | Équivalent |
|---|---|
| `make venv` | Crée `.venv` et installe `requirements.txt` |
| `make install` | `venv` + vérifie que `.env` existe (versionné, présent après clone — voir Configuration) |
| `make run` | `python -m src.main` (nécessite `venv` + `.env`) |
| `make render-test` | Régénère des aperçus dans `output/` depuis les JSON de `tests/` (vérif visuelle de `renderer.py`, voir `tests/README.md`) |
| `make dev` | `docker compose up --build` (mode fichier, override auto-chargé) |
| `make pi` | `docker compose -f docker-compose.yml up -d --build` |
| `make down` | `docker compose down` |
| `make clean` | Supprime `.venv` et les PNG générés dans `output/` |

## Arborescence

```
AbribusDisplay/
├── src/
│   ├── main.py          # orchestration des 2 threads
│   ├── config.py        # chargement .env / .env.local
│   ├── models.py        # dataclasses du JSON API
│   ├── api_client.py     # appel HTTP + gestion 401 / erreurs
│   ├── state.py          # état partagé thread-safe
│   ├── renderer.py       # génération de l'image (Pillow)
│   └── display.py        # pilotage fbi / écriture fichier
├── assets/
│   ├── fonts/             # RobotoCondensed-Bold.ttf + licence (OFL 1.1)
│   └── no_bus.png         # icône du cas "vide" (voir src/renderer.py)
├── tests/                 # paires <nom>.json / <nom>.png de référence pour le rendu
│   ├── render_example.py  # régénère des aperçus dans output/ (voir tests/README.md)
│   └── README.md
├── output/                # images générées (volume monté), jamais versionné
├── debug.html             # prévisualisation navigateur de output/display.png (mode file)
├── .env                   # versionné, valeurs par défaut (voir Configuration) — ne pas modifier
├── .env.local             # non versionné, surcharges dev/prod (TOKEN, API_URL, etc.)
├── Dockerfile
├── docker-compose.yml            # base, pensé pour le Pi (fbi + /dev/fb1)
├── docker-compose.override.yml   # auto-chargé en dev (mode file, pas de fb)
└── requirements.txt
```

## Pistes d'évolution

- Endpoint de healthcheck (petit serveur HTTP minimal) pour supervision.
- Tests unitaires sur `renderer.py` (comparaison de pixels) et `models.py`.
- Rotation/anti-burn-in si l'écran reste allumé 24/7.
