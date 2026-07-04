from datetime import datetime, timezone
from typing import List, Literal
from beanie import Document, Link, before_event, Insert, Replace, Delete
from pydantic import Field
from pymongo import ASCENDING, IndexModel
from src.scenario.schemas import Incident
from uuid import UUID

# from pymongo import ASCENDING, IndexModel


class User(Document):
    email: str
    auth_provider_id: UUID | None = None

    class Settings:
        name = "users"
        # TODO: enable after removing duplicate emails/auth_provider_ids from DB
        # indexes = [
        #     IndexModel([("email", ASCENDING)], unique=True),
        #     IndexModel([("auth_provider_id", ASCENDING)], unique=True),
        # ]


"""
@sos:
these ops trigger events:
await doc.insert()    # Insert events
await doc.save()      # Insert ή Replace events
await doc.replace()   # Replace events
"""


class Scenario(Document):
    scenario_name: str
    instructions: str
    user: Link[User]
    context: List[Incident] = Field(default_factory=list)
    initial_llm_response: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @before_event(Insert)
    async def set_created_timestamp(self):
        now = datetime.now(timezone.utc)
        self.created_at = now

    @before_event(Replace)
    async def set_updated_timestamp(self):
        self.updated_at = datetime.now(timezone.utc)

    @before_event(Delete)
    async def delete_related_assignments(self):
        from src.db.models import Assignment

        await Assignment.find({"scenario.$id": self.id}).delete()

    class Settings:
        name = "scenarios"


class Assignment(Document):
    scenario: Link[Scenario]
    trainee: Link[User]
    grade: float | None = Field(default=None, ge=0, le=100)
    status: Literal["assigned", "completed"] = "assigned"
    context_solution: List[Incident] = Field(default_factory=list)
    grade_per_incident: List[dict] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @before_event(Insert)
    async def set_created_timestamp(self):
        now = datetime.now(timezone.utc)
        self.created_at = now

    @before_event(Replace)
    async def set_updated_timestamp(self):
        self.updated_at = datetime.now(timezone.utc)

    class Settings:
        name = "assignment"
