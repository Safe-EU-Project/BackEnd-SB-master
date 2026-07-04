from src.db.models import User

# Identify users by email (matches existing DB records on this server)
PAYLOAD_KEY = "email"


async def user_retrieve_method(user_email: str) -> User | None:
    return await User.find_one(User.email == user_email)
