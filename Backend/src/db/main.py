from beanie import init_beanie
import motor
import os

from pymongo.errors import OperationFailure

from src.db.models import Assignment, Scenario, User


async def init_db():
    mongodb_uri = os.environ.get(
        "MONGODB_URI", "mongodb://root:password@mongodb:27017/?authSource=admin"
    )
    client = motor.motor_asyncio.AsyncIOMotorClient(mongodb_uri)

    await init_beanie(
        database=client.ScenarioBuilderDB, document_models=[User, Scenario, Assignment]
    )
