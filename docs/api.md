# Contrat d'API

AbribusDisplay n'embarque pas de source de données : il interroge une API
HTTP (`API_URL`) qui lui renvoie les prochains passages déjà calculés. Le
backend utilisé par l'auteur (API Platform) n'est **pas encore public** —
en attendant, n'importe quelle API qui respecte le contrat ci-dessous
fonctionne (un simple fichier JSON statique servi en HTTP suffit pour
essayer).

## Requête

```http
GET {API_URL}
Accept: application/ld+json
X-Device-Token: {TOKEN}
```

- Le header `X-Device-Token` n'est envoyé que si `TOKEN` est renseigné.
- Appel toutes les `CALL_RATE` secondes, timeout de 10 s.

## Réponses

| Réponse | Comportement |
|---|---|
| `2xx` avec un JSON valide (voir ci-dessous) | Données affichées |
| `401` | Écran "Token invalide" (ou pictogramme seul si des données valides sont déjà affichées) |
| Autre code HTTP, erreur réseau, JSON invalide ou champ obligatoire manquant | Écran "Données indisponibles" (même règle) |

## Format du JSON

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

Des exemples complets sont dans [`tests/`](../tests/) et [`demo.json`](demo.json).
Le parsing est dans [`src/models.py`](../src/models.py). Les couleurs de repli
sont décrites dans la [configuration](guide.md#configuration-env).
