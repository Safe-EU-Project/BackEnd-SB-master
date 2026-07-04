# keycloac client:
from keycloak import KeycloakOpenID

from src.user.config import get_settings

settings = get_settings()

"""
Keycloak Setup
"""

keycloak_openid = KeycloakOpenID(
    server_url=settings.keycloak_internal_url,
    realm_name=settings.keycloak_realm,
    client_id=settings.keycloak_client_id,
    client_secret_key=settings.keycloak_client_secret,
)
