from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_crustdata_client, get_db_session, get_geocoder
from app.core.auth import UserContext, get_current_user
from app.crustdata.client import CrustdataClient
from app.db.session import get_session_factory
from app.geo.geocode import CachedGeocoder
from app.geo.jobs import geocode_run_locations
from app.runs.schemas import CreateRunRequest, CreateRunResponse, SearchRunResponse
from app.runs.service import create_search_run, get_search_run

router = APIRouter(prefix="/runs", tags=["runs"])


def schedule_run_geocoding(run_id: str, geocoder: CachedGeocoder) -> None:
    geocode_run_locations(
        session_factory=get_session_factory(),
        geocoder=geocoder,
        run_id=run_id,
    )


@router.post("", response_model=CreateRunResponse)
def create_run(
    request: CreateRunRequest,
    background_tasks: BackgroundTasks,
    current_user: UserContext = Depends(get_current_user),
    client: CrustdataClient = Depends(get_crustdata_client),
    geocoder: CachedGeocoder = Depends(get_geocoder),
    session: Session = Depends(get_db_session),
) -> CreateRunResponse:
    run = create_search_run(
        session=session,
        client=client,
        current_user=current_user,
        request=request,
    )
    background_tasks.add_task(schedule_run_geocoding, run.id, geocoder)
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
