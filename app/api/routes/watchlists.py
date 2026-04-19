from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_crustdata_client, get_db_session
from app.core.auth import UserContext, get_current_user
from app.core.operations import (
    ACTION_WATCHLIST_REFRESH,
    ensure_operation_allowed,
    record_usage_event,
)
from app.crustdata.client import CrustdataClient
from app.entities.service import enrich_company_entity, enrich_person_entity
from app.watchlists.schemas import (
    WatchlistCreateRequest,
    WatchlistItemCreateRequest,
    WatchlistRefreshResponse,
    WatchlistResponse,
    WatchlistSignalsResponse,
    WatchlistUpdateRequest,
)
from app.watchlists.service import (
    add_watchlist_item,
    create_watchlist,
    delete_watchlist,
    get_watchlist_or_404,
    get_watchlist_signals,
    list_watchlists,
    remove_watchlist_item,
    serialize_watchlist,
    summarize_refresh,
    update_watchlist,
)

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


@router.get("", response_model=list[WatchlistResponse])
def get_watchlists(
    current_user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> list[WatchlistResponse]:
    watchlists = list_watchlists(session=session, current_user=current_user)
    return [serialize_watchlist(session, watchlist) for watchlist in watchlists]


@router.post("", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
def create_watchlist_route(
    request: WatchlistCreateRequest,
    current_user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> WatchlistResponse:
    watchlist = create_watchlist(session=session, current_user=current_user, request=request)
    return serialize_watchlist(session, watchlist)


@router.get("/{watchlist_id}", response_model=WatchlistResponse)
def get_watchlist(
    watchlist_id: str,
    current_user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> WatchlistResponse:
    watchlist = get_watchlist_or_404(
        session=session,
        current_user=current_user,
        watchlist_id=watchlist_id,
    )
    return serialize_watchlist(session, watchlist)


@router.patch("/{watchlist_id}", response_model=WatchlistResponse)
def update_watchlist_route(
    watchlist_id: str,
    request: WatchlistUpdateRequest,
    current_user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> WatchlistResponse:
    watchlist = update_watchlist(
        session=session,
        current_user=current_user,
        watchlist_id=watchlist_id,
        request=request,
    )
    return serialize_watchlist(session, watchlist)


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist_route(
    watchlist_id: str,
    current_user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> Response:
    delete_watchlist(session=session, current_user=current_user, watchlist_id=watchlist_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{watchlist_id}/items",
    response_model=WatchlistResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_watchlist_item_route(
    watchlist_id: str,
    request: WatchlistItemCreateRequest,
    current_user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> WatchlistResponse:
    watchlist = add_watchlist_item(
        session=session,
        current_user=current_user,
        watchlist_id=watchlist_id,
        request=request,
    )
    return serialize_watchlist(session, watchlist)


@router.delete("/{watchlist_id}/items/{item_id}", response_model=WatchlistResponse)
def remove_watchlist_item_route(
    watchlist_id: str,
    item_id: str,
    current_user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> WatchlistResponse:
    watchlist = remove_watchlist_item(
        session=session,
        current_user=current_user,
        watchlist_id=watchlist_id,
        item_id=item_id,
    )
    return serialize_watchlist(session, watchlist)


@router.get("/{watchlist_id}/signals", response_model=WatchlistSignalsResponse)
def get_watchlist_signals_route(
    watchlist_id: str,
    current_user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> WatchlistSignalsResponse:
    return get_watchlist_signals(
        session=session,
        current_user=current_user,
        watchlist_id=watchlist_id,
    )


@router.post("/{watchlist_id}/refresh", response_model=WatchlistRefreshResponse)
def refresh_watchlist_route(
    watchlist_id: str,
    current_user: UserContext = Depends(get_current_user),
    client: CrustdataClient = Depends(get_crustdata_client),
    session: Session = Depends(get_db_session),
) -> WatchlistRefreshResponse:
    ensure_operation_allowed(
        session=session,
        current_user=current_user,
        action=ACTION_WATCHLIST_REFRESH,
    )
    watchlist = get_watchlist_or_404(
        session=session,
        current_user=current_user,
        watchlist_id=watchlist_id,
    )

    refreshed_companies = 0
    refreshed_people = 0
    signals_upserted = 0
    skipped = 0
    for item in watchlist.items:
        if item.entity_type == "company" and item.company_id:
            _company, signal_count = enrich_company_entity(
                session=session,
                client=client,
                company_id=item.company_id,
            )
            refreshed_companies += 1
            signals_upserted += signal_count
        elif item.entity_type == "person" and item.person_id:
            enrich_person_entity(
                session=session,
                client=client,
                person_id=item.person_id,
            )
            refreshed_people += 1
        else:
            skipped += 1

    record_usage_event(
        session=session,
        current_user=current_user,
        action=ACTION_WATCHLIST_REFRESH,
        target_type="watchlist",
        target_id=watchlist.id,
        details={"item_count": len(watchlist.items)},
    )
    session.commit()
    return summarize_refresh(
        watchlist_id=watchlist.id,
        refreshed_companies=refreshed_companies,
        refreshed_people=refreshed_people,
        signals_upserted=signals_upserted,
        skipped=skipped,
    )
