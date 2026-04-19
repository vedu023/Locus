from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_crustdata_client, get_db_session
from app.core.auth import UserContext, get_current_user
from app.crustdata.client import CrustdataClient
from app.runs.schemas import CreateRunRequest, CreateRunResponse, SearchRunResponse
from app.runs.service import create_search_run, get_search_run

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=CreateRunResponse)
def create_run(
    request: CreateRunRequest,
    current_user: UserContext = Depends(get_current_user),
    client: CrustdataClient = Depends(get_crustdata_client),
    session: Session = Depends(get_db_session),
) -> CreateRunResponse:
    run = create_search_run(
        session=session,
        client=client,
        current_user=current_user,
        request=request,
    )
    return CreateRunResponse.from_search_run(run)


@router.get("/{run_id}", response_model=SearchRunResponse)
def get_run(
    run_id: str,
    current_user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> SearchRunResponse:
    run = get_search_run(
        session=session,
        current_user=current_user,
        run_id=run_id,
    )
    return SearchRunResponse.from_search_run(run)
