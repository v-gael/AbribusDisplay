"""Appel de l'API distante et gestion des erreurs."""
from __future__ import annotations

import logging

import requests
import urllib3

from .models import NextPassagesResponse

logger = logging.getLogger(__name__)


class InvalidTokenError(Exception):
    """Levée quand l'API répond 401 (token invalide)."""


class ApiError(Exception):
    """Levée pour toute autre erreur réseau / HTTP / parsing."""


def fetch_next_passages(
    api_url: str, token: str, timeout: float = 10.0, verify_ssl: bool = True
) -> NextPassagesResponse:
    # L'API (API Platform) attend le token dans X-Device-Token, pas dans un
    # Authorization: Bearer classique, et sert du JSON-LD.
    headers = {"Accept": "application/ld+json"}
    if token:
        headers["X-Device-Token"] = token

    if not verify_ssl:
        # Certificat local (ex: CA Caddy/FrankenPHP en dev) : pas de vraie
        # chaîne de confiance à vérifier, on coupe aussi le warning urllib3
        # associé pour ne pas polluer les logs à chaque appel.
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        response = requests.get(api_url, headers=headers, timeout=timeout, verify=verify_ssl)
    except requests.RequestException as exc:
        raise ApiError(f"Erreur réseau lors de l'appel à {api_url}: {exc}") from exc

    if response.status_code == 401:
        raise InvalidTokenError("Token invalide (401)")

    if not response.ok:
        raise ApiError(f"Réponse HTTP {response.status_code} depuis {api_url}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise ApiError(f"Réponse JSON invalide: {exc}") from exc

    try:
        return NextPassagesResponse.from_dict(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError(f"Format de réponse inattendu: {exc}") from exc
