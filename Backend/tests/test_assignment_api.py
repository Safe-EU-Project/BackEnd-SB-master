# tests/test_assignment_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from fastapi import status

from app import app
from src.user.dependencies import get_current_user, get_user_role

TRAINEE_EMAIL = "trainee@test.com"
MOCK_TRAINEE_USER = {"email": TRAINEE_EMAIL, "role": "trainee"}
MOCK_TRAINER_USER = {"email": "trainer@test.com", "role": "trainer"}
BASE = "/v1/assignment"


def make_auth_header(token: str = "fake-jwt-token") -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ─── Helpers για dependency overrides ───────────────────────


def override_current_user(mock_user: dict):
    """Επιστρέφει dependency function που κάνει return τον mock user."""

    async def _override():
        return mock_user

    return _override


def override_user_role_ok():
    """Role check που πάντα περνάει — no-op."""

    async def _override():
        return None

    return _override


def override_user_role_forbidden():
    """Role check που πάντα ρίχνει 403."""
    from fastapi import HTTPException

    async def _override():
        raise HTTPException(status_code=403, detail="Forbidden")

    return _override


# ─── Tests ──────────────────────────────────────────────────


class TestCountDistinctScenarios:

    @pytest.mark.anyio
    async def test_returns_solved_and_total_count(self, client):
        mock_result = {"solved_by_current_user": 3, "total_scenarios": 10}

        app.dependency_overrides[get_current_user] = override_current_user(
            MOCK_TRAINEE_USER
        )
        app.dependency_overrides[get_user_role] = lambda role: override_user_role_ok()

        with patch(
            "src.assignment.service.AssignmentService.count_distinct_scenarios_for_user",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            response = await client.get(
                f"{BASE}/user/scenario/solved", headers=make_auth_header()
            )

        app.dependency_overrides.clear()

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["solved_by_current_user"] == 3
        assert response.json()["total_scenarios"] == 10

    @pytest.mark.anyio
    async def test_returns_zero_when_no_solved_assignments(self, client):
        mock_result = {"solved_by_current_user": 0, "total_scenarios": 5}

        app.dependency_overrides[get_current_user] = override_current_user(
            MOCK_TRAINEE_USER
        )
        app.dependency_overrides[get_user_role] = lambda role: override_user_role_ok()

        with patch(
            "src.assignment.service.AssignmentService.count_distinct_scenarios_for_user",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            response = await client.get(
                f"{BASE}/user/scenario/solved", headers=make_auth_header()
            )

        app.dependency_overrides.clear()

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["solved_by_current_user"] == 0

    @pytest.mark.anyio
    async def test_unauthenticated_request_is_rejected(self, client):
        # Εδώ ΔΕΝ βάζουμε overrides — θέλουμε το real auth να τρέξει
        response = await client.get(f"{BASE}/user/scenario/solved")
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    @pytest.mark.anyio
    async def test_trainer_cannot_access_trainee_route(self, client):
        app.dependency_overrides[get_current_user] = override_current_user(
            MOCK_TRAINER_USER
        )
        app.dependency_overrides[get_user_role] = (
            lambda role: override_user_role_forbidden()
        )

        response = await client.get(
            f"{BASE}/user/scenario/solved", headers=make_auth_header()
        )

        app.dependency_overrides.clear()

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.anyio
    async def test_returns_404_when_user_not_found(self, client):
        from fastapi import HTTPException

        app.dependency_overrides[get_current_user] = override_current_user(
            MOCK_TRAINEE_USER
        )
        app.dependency_overrides[get_user_role] = lambda role: override_user_role_ok()

        with patch(
            "src.assignment.service.AssignmentService.count_distinct_scenarios_for_user",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=404, detail="User not found"),
        ):
            response = await client.get(
                f"{BASE}/user/scenario/solved", headers=make_auth_header()
            )

        app.dependency_overrides.clear()

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "User not found"
