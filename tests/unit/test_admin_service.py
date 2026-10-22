from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import verify_password
from app.models.user import Role, User
from app.services.admin_service import AdminService


def make_service():
    users = AsyncMock()
    users.add.side_effect = lambda u: u
    return AdminService(users), users


def make_admin():
    admin = User(email="admin@example.com", password_hash="x", name="Admin", role=Role.ADMIN)
    admin.id = uuid4()
    return admin


async def test_create_user_hashes_password_and_sets_role():
    service, users = make_service()
    users.get_by_email.return_value = None

    user = await service.create_user("new@example.com", "Password1", "New", Role.ADMIN)

    assert user.role == Role.ADMIN
    assert verify_password("Password1", user.password_hash)


async def test_create_user_rejects_duplicate_email():
    service, users = make_service()
    users.get_by_email.return_value = User(email="taken@example.com", password_hash="x", name="X")

    with pytest.raises(ConflictError):
        await service.create_user("taken@example.com", "Password1", "New", Role.USER)


async def test_change_role_updates_another_user():
    service, users = make_service()
    target = User(email="user@example.com", password_hash="x", name="User", role=Role.USER)
    users.get_by_id.return_value = target

    updated = await service.change_role(make_admin(), uuid4(), Role.ADMIN)

    assert updated.role == Role.ADMIN


async def test_change_role_refuses_own_account():
    service, users = make_service()
    admin = make_admin()

    with pytest.raises(ConflictError) as exc:
        await service.change_role(admin, admin.id, Role.USER)

    assert exc.value.error_code == "CANNOT_CHANGE_OWN_ROLE"
    users.get_by_id.assert_not_awaited()


async def test_change_role_reports_unknown_user():
    service, users = make_service()
    users.get_by_id.return_value = None

    with pytest.raises(NotFoundError):
        await service.change_role(make_admin(), uuid4(), Role.ADMIN)
