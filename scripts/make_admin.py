"""Promote an existing account to admin. The admin API can't hand out the
first admin role (nobody has one yet), so this does it straight in the
database that DATABASE_URL points at.

Usage (register the account first, at /register or POST /auth/register):
    python scripts/make_admin.py you@example.com

Against the Render demo, set DATABASE_URL to the database's External
Database URL from the Render dashboard (skillforge-ai-db > Connect) first.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import async_session_factory, engine  # noqa: E402
from app.models.user import Role  # noqa: E402
from app.repositories.user_repository import UserRepository  # noqa: E402


async def make_admin(email: str) -> bool:
    try:
        async with async_session_factory() as session:
            user = await UserRepository(session).get_by_email(email)
            if user is None:
                return False
            user.role = Role.ADMIN
            await session.commit()
            return True
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("email")
    args = parser.parse_args()
    if not asyncio.run(make_admin(args.email)):
        sys.exit(f"No account with email {args.email}.")
    print(f"{args.email} is now an admin.")


if __name__ == "__main__":
    main()
