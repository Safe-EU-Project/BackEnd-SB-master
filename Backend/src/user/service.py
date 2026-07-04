from uuid import UUID

from jose import jwt, JWTError
from pymongo.errors import DuplicateKeyError
from src.db.models import User
from src.user.config import get_settings
from fastapi import HTTPException, status
from src.user.keycloak_client import keycloak_openid
from src.user.schemas import CreateUserModel
from src.user.logger import logger


class UserService:
    @staticmethod
    def verify_token(token: str) -> dict:
        try:
            settings = get_settings()

            # take the public key (docker-to-docker):
            public_key = (
                "-----BEGIN PUBLIC KEY-----\n"
                f"{keycloak_openid.public_key()}\n"
                "-----END PUBLIC KEY-----"
            )

            # issuer is with public URL:
            issuer = f"{settings.keycloak_public_url}/realms/{settings.keycloak_realm}"
            """
            /*
            --
            In production: SET to TRUE, whatever is needed,
            for dev some keyargs are set to False.
            */
            """
            decoded = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                issuer=issuer,
                options={
                    "verify_signature": True,
                    "verify_aud": False,
                    "verify_iss": False,
                    "verify_exp": True,
                },
            )

            return decoded

        except JWTError as e:
            logger.warning(f"Token validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid authentication credentials: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )

        except Exception as e:
            logger.error(f"Unexpected error during token verification: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not validate credentials",
            )

    async def create_user_if_user_not_exists(self, create_user_data: CreateUserModel):
        # check if the UID from keycloak exist into the database:
        user = await User.find_one(
            User.auth_provider_id == create_user_data.auth_provider_id
        )
        if not user:
            new_user = User(
                auth_provider_id=create_user_data.auth_provider_id,
                email=create_user_data.email,
            )
            try:
                await new_user.insert()
            except DuplicateKeyError:
                # Concurrent first requests: another coroutine inserted the same user.
                user = await User.find_one(
                    User.auth_provider_id == create_user_data.auth_provider_id
                )
                if user:
                    return user
                raise
            return new_user
        return user

    async def ensure_local_user_from_oidc_claims(self, claims: dict) -> None:
        """SPA Keycloak login: sync Mongo User via create_user_if_user_not_exists."""
        sub = claims.get("sub")
        if not sub:
            return
        email = claims.get("email") or claims.get("preferred_username")
        if not email:
            logger.warning(
                "Skipping Mongo user sync: token has no email or preferred_username"
            )
            return
        try:
            auth_provider_id = UUID(sub) if isinstance(sub, str) else sub
        except ValueError:
            logger.warning(
                "Skipping Mongo user sync: sub is not a valid UUID (%s)", sub
            )
            return
        await self.create_user_if_user_not_exists(
            CreateUserModel(auth_provider_id=auth_provider_id, email=email)
        )
