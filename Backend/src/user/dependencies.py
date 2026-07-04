from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from keycloak import KeycloakOpenID
from src.user.config import get_settings
from src.user.logger import logger
from src.user.service import UserService

# add the settings:o
settings = get_settings()

_user_service = UserService()

# inject the Bearer token dependency:
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request, credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
):

    if request.method == "OPTIONS":
        return None

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    token = credentials.credentials
    try:
        decoded = UserService.verify_token(token)
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="email is not provided"
        )
    try:
        await _user_service.ensure_local_user_from_oidc_claims(decoded)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to sync local user after valid JWT")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not sync user to database: {e!s}",
        ) from e
    return decoded


def get_user_role(required_role: str):
    async def role_dependency(user_data: dict = Depends(get_current_user)):
        if user_data is None:
            return None
        roles = user_data.get("realm_access", {}).get("roles", [])
        if required_role in roles:
            return required_role
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden. Role '{required_role}' required.",
        )

    return role_dependency


# def role_required(required_role: str):
#     """
#     Factory that creates a dependency to restrict access by Keycloak realm role.
#     """
#     def wrapper(current_user=Depends(get_current_user)):
#         roles = current_user.get("realm_access", {}).get("roles", [])
#         if required_role not in roles:
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail=f"Access forbidden. Role '{required_role}' required.",
#             )
#         return current_user
#     return wrapper
