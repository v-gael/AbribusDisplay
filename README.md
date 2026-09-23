# AbribusDisplay

Générateur d'affichage "prochains passages" (type panneau d'arrêt de bus) pour
Raspberry Pi 3B+, affiché sur écran via `fbi` (`/dev/fb1`), avec un mode fichier
pour développer sur Mac/Linux sans matériel.

## Architecture

Deux boucles tournent en parallèle dans le même processus (threads), à des
rythmes différents, autour d'un état partagé thread-safe :

```
                 CALL_RATE (ex: 60s)
   ┌─────────────────────────────────────────┐
   │             Thread fetcher              │
   │ appelle API_URL → parse JSON → AppState │
   └─────────────────────────────────────────┘
                        │
                        ▼
                  AppState (Lock)
                        ▲
                        │
   ┌─────────────────────────────────────────┐
   │              Thread renderer            │
   │  lit AppState → Pillow → PNG → display  │
   └─────────────────────────────────────────┘
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
  tableau des lignes, soit un message centré (cas "vide" / "token invalide" / "données
  indisponibles").
- **`src/display.py`** : abstraction de la sortie finale :
  - `FbiDisplay` (Pi) : lance `fbi` une seule fois en tâche de fond, puis lui
    envoie `SIGUSR1` à chaque nouvelle image pour qu'il recharge le fichier
    sans clignoter/relancer.
  - `FileDisplay` (dev Mac/Linux) : écrit simplement le PNG sur disque.
- **`src/main.py`** : point d'entrée, démarre les deux threads, gère l'arrêt
  propre sur `SIGINT`/`SIGTERM`, fait un premier appel synchrone au démarrage
  pour ne jamais afficher un écran vide au lancement.

## Les cas d'affichage

| Cas | Déclencheur | Rendu |
|---|---|---|
| Classique | Réponse OK avec des `nextPassages` | Tableau comme sur la maquette |
| Vide | `DisplayItem` sans `nextPassages` | Message centré "Pas de passage prévu actuellement" |
| Token invalide | Réponse `401` (et jamais eu de données valides) | Message centré "Token invalide, vérifier la configuration" |
| Erreur API | Autre erreur (réseau, HTTP, JSON) et jamais eu de données valides | Message centré "Données indisponibles" |

En plus de ces cas, un pictogramme (`assets/no_signal.png`) s'affiche à droite
du bandeau des en-têtes de colonnes dès que le **dernier** appel API a échoué
(401 compris), même si des données valides précédentes sont encore affichées.
Il disparaît au premier appel réussi.

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
| `DISPLAY_TIMEZONE` | Fuseau horaire de l'heure affichée (IANA, ex: `Europe/Paris`) — indépendant du fuseau système, souvent UTC dans un conteneur Docker |
| `IMAGE_WIDTH` / `IMAGE_HEIGHT` | Résolution de l'image générée (adapter à l'écran du Pi) |
| `ROWS_PER_SCREEN` | Nombre de lignes de référence pour la taille des polices/pastilles (voir "Les cas d'affichage" ci-dessus) |
| `DISPLAY_MODE` | `fbi` (Pi) ou `file` (dev) |
| `OUTPUT_PATH` | Chemin du PNG généré |
| `FRAMEBUFFER_DEVICE` | Périphérique framebuffer cible (mode `fbi`) |

> Remarque sur `routeColor` / `routeTextColor` : si absents dans le JSON, on
> retombe respectivement sur `HEADER_BACKGROUND_COLOR` et
> `TEXT_DIRECTION_COLOR`.

### Police

La police **Roboto Condensed Bold** est embarquée dans le dépôt sous
`assets/fonts/` (voir `assets/fonts/README.md` pour la licence, SIL Open
Font License 1.1).

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
# ou : make run
```

## Déployer sur le Raspberry Pi

### Préparer le Pi

À faire une seule fois, sur un Raspberry Pi OS neuf, avant le premier
déploiement. `setup-ecran-pi.sh` configure l'écran SPI 3.5" (clone
waveshare35a) et installe Docker :

```bash
scp setup-ecran-pi.sh admin@192.168.1.131:~   # depuis le Mac
ssh admin@192.168.1.131
sudo ./setup-ecran-pi.sh
```

Le script demande la rotation de l'écran (`90` par défaut, valeur validée
pour un écran monté à l'horizontale), sauvegarde `config.txt`
(`config.txt.backup.<date>`), puis :

- active le SPI et désactive `vc4-kms-v3d` (en conflit avec le driver fbtft) ;
- télécharge l'overlay `waveshare35a.dtbo` et ajoute sa configuration dans
  `config.txt` ;
- désactive `getty@tty1`, sans quoi `fbi` ne peut pas prendre la main sur la
  console ;
- installe Docker (Engine + plugin compose) et ajoute l'utilisateur au groupe
  `docker`.

Il peut être relancé sans risque : les réglages déjà présents dans
`config.txt` ne sont pas dupliqués (seul l'overlay est retéléchargé, et une
nouvelle sauvegarde est créée à chaque exécution). Pour changer la rotation
après coup, modifier à la main la ligne `dtoverlay=waveshare35a,rotate=XX`. Un
redémarrage est nécessaire à la fin (le script propose de le faire). Pour
vérifier ensuite que l'écran est bien détecté :

```bash
dmesg | grep -i ili9486    # contrôleur d'affichage
dmesg | grep -i ads7846    # contrôleur tactile
ls /dev/fb1                # framebuffer utilisé par l'app (FRAMEBUFFER_DEVICE)
```

### Déployer l'application

Sur le Pi, ne pas embarquer `docker-compose.override.yml` (ou le
supprimer/renommer), pour que `docker-compose.yml` seul s'applique.

**Option recommandée si le Pi est limité en espace disque : build en local,
transfert de l'image déjà construite.** Ça évite d'avoir besoin des outils de
compilation (gcc, headers...) sur le Pi si un wheel précompilé n'est pas
disponible pour Pillow, et ça évite l'accumulation de cache de build à
chaque rebuild :

```bash
cp .env.pi.local.example .env.pi.local   # une seule fois, puis compléter
# DISPLAY_MODE=fbi, TOKEN, API_URL, IMAGE_WIDTH/IMAGE_HEIGHT selon l'écran...

make deploy PI_HOST=192.168.1.131 PI_USER=admin
# build l'image en local (nécessite un Mac/hôte de même archi que le Pi,
# ex. Apple Silicon -> Pi 64-bit, sinon voir docker buildx --platform),
# la transfère par SSH (docker save | ssh ... docker load, sans fichier
# tar intermédiaire), copie docker-compose.yml + .env sur le Pi, pousse
# .env.pi.local en tant que .env.local sur le Pi (surcharges propres à ce
# déploiement — jamais dans .env, versionné), puis `docker compose up -d`
# + prune de l'ancienne image sur le Pi.
```

`.env.pi.local` est non versionné (secrets) : à créer une seule fois sur ton
Mac, `make deploy` se charge de le pousser sur le Pi à chaque déploiement —
pas besoin de s'y connecter en SSH pour ça.

`PI_HOST`/`PI_USER`/`PI_DIR` ont des valeurs par défaut dans le `Makefile` à
adapter à ton installation.

**Option build direct sur le Pi** (plus simple, mais consomme plus d'espace
disque pour le cache de build) :

```bash
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
| `make venv-dev` | `venv` + outils de qualité (`requirements-dev.txt` : ruff, mypy) |
| `make run` | `python -m src.main` (nécessite `venv` + `.env`) |
| `make render-test` | Régénère des aperçus dans `output/` depuis les JSON de `tests/` (vérif visuelle de `renderer.py`, voir `tests/README.md`) |
| `make lint` | `ruff check .` (nécessite `venv-dev`) |
| `make format` | `ruff format .` (reformate, nécessite `venv-dev`) |
| `make format-check` | `ruff format --check .` (vérifie sans modifier, nécessite `venv-dev`) |
| `make typecheck` | `mypy` (nécessite `venv-dev`) |
| `make check` | `lint` + `format-check` + `typecheck` |
| `make dev` | `docker compose up --build` (mode fichier, override auto-chargé) |
| `make pi` | `docker compose -f docker-compose.yml up -d --build` |
| `make down` | `docker compose down` |
| `make ps` | `docker compose ps` (statut des conteneurs) |
| `make logs` | `docker compose logs -f` (suit les logs du conteneur) |
| `make shell` | `docker compose exec abribusdisplay sh` (debug dans le conteneur) |
| `make outdated` | `pip list --outdated` (dépendances de `requirements*.txt` à mettre à jour) |
| `make clean` | Supprime `.venv`, les caches `ruff`/`mypy` et les PNG générés dans `output/` |

## Qualité de code

Deux outils, configurés dans `pyproject.toml`, aucun autre linter/formatter
n'est utilisé :

- **[ruff](https://docs.astral.sh/ruff/)** : lint (`make lint`) et formatage
  (`make format`) en un seul outil, règles pycodestyle/pyflakes/isort +
  pyupgrade (modernisation de syntaxe) + bugbear/simplify.
- **[mypy](https://mypy-lang.org/)** en mode `strict` (`make typecheck`) :
  analyse statique des types sur `src/` et `tests/`.

```bash
make venv-dev    # installe ruff + mypy dans .venv (une fois)
make check       # lint + format-check + typecheck, comme en CI
make format      # reformate le code si besoin
```

Aucune CI n'exécute `make check` pour l'instant (voir "Pistes d'évolution") :
à lancer manuellement avant de committer.

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
│   ├── no_bus.png         # icône du cas "vide" (voir src/renderer.py)
│   └── no_signal.png      # pictogramme de souci d'accès à l'API (voir src/renderer.py)
├── tests/                 # paires <nom>.json / <nom>.png de référence pour le rendu
│   ├── render_example.py  # régénère des aperçus dans output/ (voir tests/README.md)
│   └── README.md
├── output/                # images générées (volume monté), jamais versionné
├── debug.html             # prévisualisation navigateur de output/display.png (mode file)
├── .env                   # versionné, valeurs par défaut (voir Configuration) — ne pas modifier
├── .env.local             # non versionné, surcharges dev/prod (TOKEN, API_URL, etc.)
├── .env.pi.local.example  # modèle de .env.pi.local (poussé sur le Pi en .env.local par `make deploy`)
├── Dockerfile
├── docker-compose.yml            # base, pensé pour le Pi (fbi + /dev/fb1)
├── docker-compose.override.yml   # auto-chargé en dev (mode file, pas de fb)
├── pyproject.toml         # config ruff + mypy (voir Qualité de code)
├── setup-ecran-pi.sh      # installation de l'écran SPI 3.5" (waveshare35a) sur le Pi, à lancer avec sudo
├── requirements.txt
└── requirements-dev.txt   # outils de qualité (ruff, mypy), pas dans l'image Docker
```

## Pistes d'évolution

- Endpoint de healthcheck (petit serveur HTTP minimal) pour supervision.
- Tests unitaires sur `renderer.py` (comparaison de pixels) et `models.py`.
- Rotation/anti-burn-in si l'écran reste allumé 24/7.
- CI (GitHub Actions ou autre) pour lancer `make check` automatiquement.
