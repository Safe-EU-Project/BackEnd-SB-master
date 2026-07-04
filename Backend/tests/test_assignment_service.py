# import pytest
# from types import SimpleNamespace
# from unittest.mock import AsyncMock, Mock, patch

# from src.assignment.service import AssignmentService


# # @pytest.mark.asyncio  # Marks it as async test due do the original function is async
# # async def test_count_distinct_scenarios_for_user_correct_return_result():
# #     service = AssignmentService()  # Keep it real, this object is being tested

# #     fake_user = SimpleNamespace(
# #         id="user123",
# #         email="test@example.com",
# #     )  # Just create a simple object with fields using SimpleNameSpace

# #     fake_cursor = Mock()
# #     fake_cursor.to_list = AsyncMock(return_value=[{"distinct_scenarios": 3}])

# #     # Mock the dependencies:
# #     with patch(
# #         "src.assignment.service.User.find_one",
# #         new=AsyncMock(return_value=fake_user),
# #     ), patch(
# #         "src.assignment.service.Assignment.aggregate",
# #         return_value=fake_cursor,
# #     ), patch(
# #         "src.assignment.service.Scenario.count",
# #         new=AsyncMock(return_value=10),
# #     ):

# #         result = await service.count_distinct_scenarios_for_user("test@example.com")

# #     assert result == {
# #         "solved_by_current_user": 3,
# #         "total_scenarios": 10,
# #     }

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from src.assignment.service import AssignmentService


@pytest.mark.asyncio
async def test_count_distinct_scenarios_for_user_correct_return_result():
    service = AssignmentService()

    fake_user = SimpleNamespace(
        id="user123",
        email="test@example.com",
    )

    fake_user_model = SimpleNamespace(
        email="email_field",
        find_one=AsyncMock(return_value=fake_user),
    )

    fake_cursor = Mock()
    fake_cursor.to_list = AsyncMock(return_value=[{"distinct_scenarios": 3}])

    with patch(
        "src.assignment.service.User",
        new=fake_user_model,
    ), patch(
        "src.assignment.service.Assignment.aggregate",
        return_value=fake_cursor,
    ), patch(
        "src.assignment.service.Scenario.count",
        new=AsyncMock(return_value=10),
    ):

        result = await service.count_distinct_scenarios_for_user("test@example.com")

    assert result == {
        "solved_by_current_user": 3,
        "total_scenarios": 10,
    }

    import pytest


from fastapi import HTTPException, status
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.assignment.service import AssignmentService


@pytest.mark.asyncio
async def test_count_distinct_scenarios_for_user_raises_404_when_user_not_found():
    service = AssignmentService()

    fake_user_model = SimpleNamespace(
        email="email_field",
        find_one=AsyncMock(return_value=""),
    )

    mock_count = AsyncMock(return_value=10)

    with patch(
        "src.assignment.service.User",
        new=fake_user_model,
    ), patch(
        "src.assignment.service.Assignment.aggregate",
    ) as mock_aggregate, patch(
        "src.assignment.service.Scenario.count",
        new=mock_count,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await service.count_distinct_scenarios_for_user("test@example.com")

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "User not found"
    mock_aggregate.assert_not_called()
    mock_count.assert_not_awaited()


# import pytest
# from unittest.mock import AsyncMock, Mock, patch

# from src.assignment.service import AssignmentService
