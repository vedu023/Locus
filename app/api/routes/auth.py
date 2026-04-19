from fastapi import APIRouter, Depends

from app.core.auth import UserContext, get_current_user

router = APIRouter(tags=["auth"])


@router.get("/auth/me", response_model=UserContext)
def whoami(current_user: UserContext = Depends(get_current_user)) -> UserContext:
    return current_user
