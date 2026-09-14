# Police Roboto Condensed Bold

La police **Roboto Condensed Bold** est embarquée dans ce dépôt :

```
assets/fonts/RobotoCondensed-Bold.ttf
assets/fonts/OFL.txt
```

Elle est distribuée par The Roboto Project Authors sous licence
[SIL Open Font License 1.1](https://openfontlicense.org/) (voir `OFL.txt`),
qui autorise l'usage, la modification et la redistribution, y compris
embarquée dans un dépôt de code.

Source officielle : [google/fonts](https://github.com/google/fonts/tree/main/ofl/robotocondensed),
famille distribuée aujourd'hui sous forme de police variable
(`RobotoCondensed[wght].ttf`, axe `wght` de 100 à 900). Le fichier ici est
une instance statique figée au poids 700 (Bold), générée avec
`fonttools varLib.instancer --update-name-table … wght=700` — nécessaire
car `src/renderer.py` charge la police via `ImageFont.truetype()` sans
piloter les axes de variation ; utiliser directement le fichier variable
rendrait le texte en graisse Regular (400) au lieu de Bold.

`FONT_PATH` (voir le tableau de configuration dans le `README.md` racine)
pointe vers ce fichier par défaut. Si le
fichier venait à manquer, `renderer.py` bascule automatiquement sur la police
par défaut de Pillow (un warning est loggé) — le projet continue donc de
fonctionner sans, mais le rendu ne correspondra pas exactement à la maquette.
