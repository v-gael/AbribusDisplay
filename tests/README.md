# Données de test pour le rendu

Ce dossier contient des paires de fichiers `<nom>.json` / `<nom>.png` :

- `example.json` / `example.png`
- `noBus.json` / `noBus.png`

Le `.json` est un exemple de réponse de l'API (`NextPassagesResponse`, voir
`src/models.py`). Le `.png` du même nom est le **rendu de référence** :
l'image que `src/renderer.py` est censé produire à partir de ce JSON.

## Objectif

Quand tu modifies `src/renderer.py`, le but n'est pas de faire passer un
test automatisé (il n'y en a pas, voir `AGENTS.md`) mais de te rapprocher le
plus possible, visuellement, de l'image de référence correspondant au JSON
que tu fais varier.

Démarche :

1. Lance `python tests/render_example.py` (ou `make render-test`) : le
   script régénère, avec le `renderer.py` actuel, un aperçu PNG par fichier
   JSON de ce dossier, écrit dans `output/<nom>.png` (jamais dans `tests/`).
2. Compare chaque aperçu à l'image de référence du même nom dans ce dossier
   (`output/example.png` ↔ `tests/example.png`, `output/noBus.png` ↔
   `tests/noBus.png`...) et ajuste `src/renderer.py` jusqu'à ce que le rendu
   s'en rapproche au maximum.

`render_example.py` boucle automatiquement sur tous les `.json` présents
ici : pas besoin de le modifier pour ajouter un cas, voir ci-dessous.

Pour ajouter un nouveau cas de test, ajoute une nouvelle paire
`<nom>.json` / `<nom>.png` : le JSON décrit les données d'entrée, le PNG est
la cible visuelle à atteindre (maquette validée à la main, pas générée par
le code).

## ⚠️ Attention

Les fichiers `.png` de ce dossier sont des **références**, pas des sorties
générées. Ne fais jamais pointer un script de rendu vers l'un de ces
fichiers en écriture (`save_image(image, "tests/noBus.png")` par exemple) :
ça écraserait la référence avec ta propre sortie. `render_example.py` écrit
toujours dans `output/` précisément pour ça — garde cette convention si tu
écris un autre script de vérification visuelle.
