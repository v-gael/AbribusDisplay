# AbribusDisplay

[![check](https://github.com/v-gael/AbribusDisplay/actions/workflows/check.yml/badge.svg)](https://github.com/v-gael/AbribusDisplay/actions/workflows/check.yml)
[![Licence MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

Générateur d'affichage "prochains passages" (type panneau d'arrêt de bus) pour
Raspberry Pi 3B+, affiché sur écran via `fbi` (`/dev/fb1`), avec un mode fichier
pour développer sur Mac/Linux sans matériel.

<p align="center">
  <img src="docs/demo.gif" alt="Aperçu du panneau : deux arrêts avec leurs prochains passages, puis un arrêt sans passage prévu" width="480">
</p>

<sub>Aperçu généré avec le rendu réel depuis `docs/demo.json` (`make demo-gif`) :
l'écran passe d'un arrêt à l'autre toutes les `REFRESH_RATE` secondes.</sub>

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

Dans tous les cas, la version de l'application (`__version__` dans
`src/__init__.py`, ex. `v1.0.0`) est écrite en tout petit en bas à droite de
l'image, pour savoir d'un coup d'œil quelle version tourne sur le Pi.

La liste `displays` est parcourue en round-robin : toutes les `REFRESH_RATE`
secondes, l'image régénérée passe à l'élément suivant, puis on reboucle au
premier.

Dans le cas "Classique", la taille des polices/pastilles est calculée à
partir de `ROWS_PER_SCREEN` (5 par défaut), pas du nombre réel de passages :
avec moins de passages que `ROWS_PER_SCREEN`, l'espace restant reste vide en
bas plutôt que de faire grossir les lignes affichées ; avec plus, elles
rétrécissent pour toutes tenir.

## Contrat d'API

AbribusDisplay n'embarque pas de source de données : il interroge une API
HTTP (`API_URL`) qui lui renvoie les prochains passages déjà calculés. Le
backend utilisé par l'auteur (API Platform) n'est **pas encore public** —
en attendant, n'importe quelle API qui respecte le contrat ci-dessous
fonctionne (un simple fichier JSON statique servi en HTTP suffit pour
essayer).

### Requête

```http
GET {API_URL}
Accept: application/ld+json
X-Device-Token: {TOKEN}
```

- Le header `X-Device-Token` n'est envoyé que si `TOKEN` est renseigné.
- Appel toutes les `CALL_RATE` secondes, timeout de 10 s.

### Réponses

| Réponse | Comportement |
|---|---|
| `2xx` avec un JSON valide (voir ci-dessous) | Données affichées |
| `401` | Écran "Token invalide" (ou pictogramme seul si des données valides sont déjà affichées) |
| Autre code HTTP, erreur réseau, JSON invalide ou champ obligatoire manquant | Écran "Données indisponibles" (même règle) |

### Format du JSON

```json
{
  "generatedAt": "2026-09-14T15:26:48+00:00",
  "displays": [
    {
      "label": "Torvilliers Parc d'Activités",
      "quayName": "Torvilliers Parc d Activites",
      "nextPassages": [
        {
          "routeShortName": "6A",
          "routeColor": "009036",
          "routeTextColor": "FFFFFF",
          "headsign": "CHAPELLE ST LUC VERS GRANGE L EV. - MESNIL - MACEY",
          "expectedAt": "2026-09-14T15:30:43+00:00"
        }
      ]
    }
  ]
}
```

| Champ | Type | Obligatoire | Rôle |
|---|---|---|---|
| `generatedAt` | date ISO 8601 avec fuseau | oui | Date de génération de la réponse |
| `displays` | tableau | non (défaut `[]`) | Un élément par arrêt, affichés tour à tour (round-robin) ; vide → "Pas de passage prévu actuellement" |
| `displays[].quayName` | chaîne | non | Nom d'arrêt affiché dans le bandeau du haut (mis en majuscules) |
| `displays[].label` | chaîne | non | Libellé lisible de l'arrêt (lu mais pas affiché pour l'instant) |
| `displays[].nextPassages` | tableau | non (défaut `[]`) | Passages, affichés **dans l'ordre reçu** (à trier côté API) ; vide → "Pas de passage prévu actuellement" |
| `nextPassages[].routeShortName` | chaîne | oui | Numéro/nom court de ligne (pastille) |
| `nextPassages[].routeColor` | hex sans `#` | non | Fond de la pastille (défaut : `HEADER_BACKGROUND_COLOR`) |
| `nextPassages[].routeTextColor` | hex sans `#` | non | Texte de la pastille (défaut : `TEXT_DIRECTION_COLOR`) |
| `nextPassages[].headsign` | chaîne | oui | Direction |
| `nextPassages[].expectedAt` | date ISO 8601 avec fuseau | oui | Heure de passage prévue |

Le "Dans X min" est calculé par l'afficheur à chaque rendu (`expectedAt` −
heure courante, arrondi à la minute inférieure, jamais négatif) : l'API n'a
pas besoin d'être rappelée pour que le décompte avance entre deux appels.

Des exemples complets sont dans `tests/*.json` et `docs/demo.json`. Le
parsing est dans `src/models.py`.

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

### Police, icônes et données

La police **Roboto Condensed Bold** est embarquée dans le dépôt sous
`assets/fonts/` (voir `assets/fonts/README.md` pour la licence, SIL Open
Font License 1.1).

Les icônes ont été générées par IA pour ce projet : `assets/no_bus.png` avec
ChatGPT (OpenAI), `assets/no_signal.png` avec Claude (Anthropic). Les
conditions d'utilisation des deux services cèdent à l'utilisateur les droits
sur les contenus générés : elles sont distribuées sous la même licence que le
code (MIT).

Les noms d'arrêts, lignes et couleurs utilisés dans les exemples
(`tests/*.json`, `docs/demo.json`, images associées) proviennent des
données ouvertes du réseau TCAT (Troyes Champagne Métropole), publiées sur
[transport.data.gouv.fr](https://transport.data.gouv.fr/datasets/donnees-tcat-troyes-champagne-metropole-1)
sous licence [ODbL](https://opendatacommons.org/licenses/odbl/1.0/).

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
scp setup-ecran-pi.sh admin@<IP_DU_PI>:~   # depuis le Mac
ssh admin@<IP_DU_PI>
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

cp deploy.local.mk.example deploy.local.mk   # une seule fois, puis y mettre PI_HOST=<IP_DU_PI>

make deploy
# (ou, sans deploy.local.mk : make deploy PI_HOST=<IP_DU_PI> PI_USER=admin)
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

`PI_HOST` n'a pas de valeur par défaut : le définir dans `deploy.local.mk`
(non versionné, inclus automatiquement par le `Makefile`) ou le passer en
ligne de commande. `PI_USER` (`admin`) et `PI_DIR` (`~/abribusdisplay`) ont
des valeurs par défaut, surchargeables de la même façon.

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
| `make demo-gif` | Régénère `docs/demo.gif` (aperçu animé en haut de ce README) depuis `docs/demo.json` |
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
make check       # lint + format-check + typecheck
make format      # reformate le code si besoin
```

La CI GitHub Actions (`.github/workflows/check.yml`) lance `make check` sous
Python 3.11 (version de l'image Docker) à chaque push et sur les pull
requests vers `develop`/`main`. Le lancer quand même en local avant de
committer évite un aller-retour.

## Arborescence

```
AbribusDisplay/
├── .github/workflows/check.yml  # CI : `make check` sous Python 3.11
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
├── docs/
│   ├── demo.json          # données de l'aperçu animé du README
│   ├── demo.gif           # aperçu animé (généré, voir `make demo-gif`)
│   └── make_demo_gif.py   # génère demo.gif avec le rendu réel
├── output/                # images générées (volume monté), jamais versionné
├── debug.html             # prévisualisation navigateur de output/display.png (mode file)
├── .env                   # versionné, valeurs par défaut (voir Configuration) — ne pas modifier
├── .env.local             # non versionné, surcharges dev/prod (TOKEN, API_URL, etc.)
├── .env.pi.local.example  # modèle de .env.pi.local (poussé sur le Pi en .env.local par `make deploy`)
├── deploy.local.mk.example  # modèle de deploy.local.mk (non versionné, PI_HOST pour `make deploy`)
├── Dockerfile
├── docker-compose.yml            # base, pensé pour le Pi (fbi + /dev/fb1)
├── docker-compose.override.yml   # auto-chargé en dev (mode file, pas de fb)
├── pyproject.toml         # config ruff + mypy (voir Qualité de code)
├── setup-ecran-pi.sh      # installation de l'écran SPI 3.5" (waveshare35a) sur le Pi, à lancer avec sudo
├── LICENSE                # licence MIT
├── SECURITY.md            # signalement de vulnérabilités
├── requirements.txt
└── requirements-dev.txt   # outils de qualité (ruff, mypy), pas dans l'image Docker
```

## Pistes d'évolution

- Endpoint de healthcheck (petit serveur HTTP minimal) pour supervision.
- Tests unitaires sur `renderer.py` (comparaison de pixels) et `models.py`.
- Rotation/anti-burn-in si l'écran reste allumé 24/7.

## Sécurité

Pour signaler une vulnérabilité, voir [SECURITY.md](SECURITY.md) (signalement
privé, pas d'issue publique).

## Licence

Code sous licence [MIT](LICENSE). La police Roboto Condensed garde sa propre
licence (SIL Open Font License 1.1, voir `assets/fonts/`) et les données
d'exemple TCAT la leur (ODbL, voir "Police, icônes et données").
