from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import UserContext
from app.db.models import User


def get_or_create_user(session: Session, current_user: UserContext) -> User:
    user = session.scalar(select(User).where(User.auth_provider_id == current_user.user_id))
    if user is not None:
        if user.email != current_user.email:
            user.email = current_user.email
        return user

    user = User(auth_provider_id=current_user.user_id, email=current_user.email)
    session.add(user)
    session.flush()
    return user
