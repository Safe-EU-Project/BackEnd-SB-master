from fastapi import APIRouter, Depends, HTTPException, status
from src.user.dependencies import get_current_user as get_oidc_user_from_token
from src.user.config import get_settings
from src.user.schemas import (
    CreateUserModel,
    LoginRequest,
    TokenResponse,
    RefreshRequest,
)
from src.user.service import UserService
from jose import jwt
from src.user.keycloak_client import keycloak_openid
from src.user.logger import logger

# user service for create new login user and validations:
user_service = UserService()

# --------------------------
# Router setup
# --------------------------
auth_router = APIRouter()

settings = get_settings()

# --------------------------
# Auth endpoints
# --------------------------
@auth_router.post("/login", response_model=TokenResponse)
async def login_user(data: LoginRequest):
    """
    Log in a user via Keycloak (password grant).
    Returns access + refresh tokens.
    """
    try:
        token = keycloak_openid.token(
            username=data.username,
            password=data.password,
            grant_type="password",
            # scope="openid profile email"
            # scope="profile email scenariobuilder-audience"
        )
        # check if it is the users with the specific sub exist in the database
        # if not exists create him to Sync Keycloak with the MongoDB
        token_from_keycloak_decoded = jwt.get_unverified_claims(token["access_token"])
        create_user_data = CreateUserModel(
            auth_provider_id=token_from_keycloak_decoded["sub"],
            email=token_from_keycloak_decoded["email"],
        )
        await user_service.create_user_if_user_not_exists(create_user_data)

        return token
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        )


@auth_router.post("/refresh", response_model=TokenResponse)
def refresh_token(data: RefreshRequest):
    """
    Use a refresh token to get a new access token.
    """
    try:
        token = keycloak_openid.refresh_token(refresh_token=data.refresh_token)
        return token
    except Exception as e:
        logger.error(f"Refresh token failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not refresh token",
        )


@auth_router.post("/logout")
def logout_user(data: RefreshRequest):
    """
    Logout the user — revoke refresh token in Keycloak.
    """
    try:
        keycloak_openid.logout(refresh_token=data.refresh_token)
        return {"detail": "User logged out successfully"}
    except Exception as e:
        logger.error(f"Logout failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logout failed",
        )


@auth_router.get("/me")
async def read_me(user_token=Depends(get_oidc_user_from_token)):
    """Verified JWT; same dependency as protected routes (runs Mongo user sync)."""
    return user_token
