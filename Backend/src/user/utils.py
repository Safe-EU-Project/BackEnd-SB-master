from uuid import UUID
from src.db.models import User


class UserRetrieveProvider:

    FIND_USER_METHOD_KEY = None
    _REGISTRY = None

    @classmethod
    def find_user_by(cls):
        if cls._REGISTRY is None:
            cls._REGISTRY = {
                "auth_provider_email": {
                    "method": cls.find_user_by_auth_provider_email,
                    "payload_key": "email",
                },
                "auth_provider_id": {
                    "method": cls.find_user_by_auth_provider_id,
                    "payload_key": "sub",
                },
            }
        return cls._REGISTRY

    @classmethod
    def set_method_identification(cls, identification_method: str):
        if identification_method not in cls.find_user_by().keys():
            raise KeyError(
                f"Unknown method: '{identification_method}'. "
                f"Choose from: {list(cls.find_user_by().keys())}"
            )
        cls.FIND_USER_METHOD_KEY = identification_method

    @staticmethod
    async def find_user_by_auth_provider_email(user_email: str) -> User | None:
        return await User.find_one(User.email == user_email)

    @staticmethod
    async def find_user_by_auth_provider_id(auth_provider_id: str) -> User | None:
        return await User.find_one(User.auth_provider_id == UUID(auth_provider_id))

    @classmethod
    def retrieve_user_method(cls):
        entry = cls.find_user_by()[cls.FIND_USER_METHOD_KEY]
        return entry["method"], entry["payload_key"]


# """ Provider Setup """

# *** SET UP - EXPORT ***
# .1 Here we define the method (one time definition - this module is a config class)
UserRetrieveProvider.set_method_identification(identification_method="auth_provider_id")
# .2a Here we unpack the user_retrieve method to use it at service layer
# .3a Also we unpack the PAYLOAD KEY, in order at router to receive the correct key fro the bearer JWT
user_retrieve_method, PAYLOAD_KEY = UserRetrieveProvider.retrieve_user_method()
