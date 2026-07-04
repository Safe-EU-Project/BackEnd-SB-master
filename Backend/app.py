from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.db.main import init_db
from src.scenario.routes import scenario_router
from src.user.routes import auth_router
from src.assignment.routes import assignment_router
from fastapi.middleware.cors import CORSMiddleware
from src.logger import logger

# from src.auth.routes import auth_router
# from contextlib import asynccontextmanager
# from src.db.main import init_db

"""
- uvicorn app:app --reload
Here is the start point of the application 
"""


# to run:  fastapi dev src/
version = "v1"

description = """
A REST API for a book review web service.

This REST API is able to;
- Create Read Update And delete books
- Add reviews to books
- Add tags to Books e.t.c.
    """
version_prefix = f"/{version}"

"""
here add all the start/end events
for the database
"""


@asynccontextmanager
async def life_span(app: FastAPI):
    # here is the events when start:
    logger.info(" ------- server is running")
    await init_db()
    logger.info(" ------- db connection has been achieved")
    yield
    # here the events when stops:
    logger.info(" ------- server has been stopped")


app = FastAPI(lifespan=life_span, redirect_slashes=False)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ----------------------------------

app.include_router(
    scenario_router, prefix=f"{version_prefix}/scenario", tags=["scenario"]
)
app.include_router(auth_router, prefix=f"{version_prefix}/user", tags=["user"])
app.include_router(
    assignment_router, prefix=f"{version_prefix}/assignment", tags=["assignment"]
)
