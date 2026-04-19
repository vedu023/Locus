from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.auth import UserContext
from app.core.errors import AppError
from app.core.users import get_or_create_user
from app.db.models import Company, Person, Signal, Watchlist, WatchlistItem
from app.watchlists.schemas import (
    WatchlistCreateRequest,
    WatchlistEntitySummary,
    WatchlistItemCreateRequest,
    WatchlistItemResponse,
    WatchlistRefreshResponse,
    WatchlistResponse,
    WatchlistSignalEntry,
    WatchlistSignalsResponse,
    WatchlistUpdateRequest,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _sorted_watchlist_items(watchlist: Watchlist) -> list[WatchlistItem]:
    return sorted(
        watchlist.items,
        key=lambda item: (item.created_at, item.id),
    )


def _entity_summary(item: WatchlistItem) -> WatchlistEntitySummary:
    if item.entity_type == "company" and item.company is not None:
        return WatchlistEntitySummary(
            entity_id=item.company.id,
            entity_type="company",
            name=item.company.name,
            subtitle=item.company.industry,
            location_label=item.company.hq_location.raw_label if item.company.hq_location else None,
        )
    if item.entity_type == "person" and item.person is not None:
        return WatchlistEntitySummary(
            entity_id=item.person.id,
            entity_type="person",
            name=item.person.name,
            subtitle=item.person.current_title,
            location_label=item.person.location.raw_label if item.person.location else None,
        )
    raise AppError(
        code="BAD_STATE",
        message="Watchlist item is missing its linked entity.",
        status_code=500,
        details={"item_id": item.id},
    )


def _signal_count_for_item(session: Session, item: WatchlistItem) -> int:
    if item.entity_type == "company" and item.company_id is not None:
        return len(
            session.scalars(select(Signal.id).where(Signal.company_id == item.company_id)).all()
        )
    if item.entity_type == "person" and item.person_id is not None:
        return len(
            session.scalars(select(Signal.id).where(Signal.person_id == item.person_id)).all()
        )
    return 0


def serialize_watchlist(session: Session, watchlist: Watchlist) -> WatchlistResponse:
    items = [
        WatchlistItemResponse(
            item_id=item.id,
            entity=_entity_summary(item),
            notes=item.notes,
            signal_count=_signal_count_for_item(session, item),
            created_at=item.created_at,
        )
        for item in _sorted_watchlist_items(watchlist)
    ]
    return WatchlistResponse(
        watchlist_id=watchlist.id,
        name=watchlist.name,
        lens=watchlist.lens,
        description=watchlist.description,
        item_count=len(items),
        items=items,
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
    )


def _load_watchlist_query():
    return select(Watchlist).options(
        joinedload(Watchlist.items).joinedload(WatchlistItem.company).joinedload(Company.hq_location),
        joinedload(Watchlist.items).joinedload(WatchlistItem.person).joinedload(Person.location),
    )


def get_watchlist_or_404(
    *,
    session: Session,
    current_user: UserContext,
    watchlist_id: str,
) -> Watchlist:
    user = get_or_create_user(session, current_user)
    result = session.execute(
        _load_watchlist_query()
        .execution_options(populate_existing=True)
        .where(Watchlist.id == watchlist_id, Watchlist.user_id == user.id)
    )
    watchlist = result.unique().scalar_one_or_none()
    if watchlist is None:
        raise AppError(
            code="NOT_FOUND",
            message="Watchlist not found.",
            status_code=404,
            details={"watchlist_id": watchlist_id},
        )
    return watchlist


def list_watchlists(*, session: Session, current_user: UserContext) -> list[Watchlist]:
    user = get_or_create_user(session, current_user)
    result = session.execute(
        _load_watchlist_query()
        .execution_options(populate_existing=True)
        .where(Watchlist.user_id == user.id)
        .order_by(Watchlist.updated_at.desc(), Watchlist.created_at.desc())
    )
    return list(result.unique().scalars().all())


def create_watchlist(
    *,
    session: Session,
    current_user: UserContext,
    request: WatchlistCreateRequest,
) -> Watchlist:
    user = get_or_create_user(session, current_user)
    watchlist = Watchlist(
        user_id=user.id,
        name=request.name,
        lens=request.lens,
        description=request.description,
    )
    session.add(watchlist)
    session.commit()
    return get_watchlist_or_404(
        session=session,
        current_user=current_user,
        watchlist_id=watchlist.id,
    )


def update_watchlist(
    *,
    session: Session,
    current_user: UserContext,
    watchlist_id: str,
    request: WatchlistUpdateRequest,
) -> Watchlist:
    watchlist = get_watchlist_or_404(
        session=session,
        current_user=current_user,
        watchlist_id=watchlist_id,
    )
    if request.name is not None:
        watchlist.name = request.name
    if request.lens is not None:
        watchlist.lens = request.lens
    if request.description is not None:
        watchlist.description = request.description
    session.commit()
    return get_watchlist_or_404(
        session=session,
        current_user=current_user,
        watchlist_id=watchlist.id,
    )


def delete_watchlist(*, session: Session, current_user: UserContext, watchlist_id: str) -> None:
    watchlist = get_watchlist_or_404(
        session=session,
        current_user=current_user,
        watchlist_id=watchlist_id,
    )
    session.delete(watchlist)
    session.commit()


def add_watchlist_item(
    *,
    session: Session,
    current_user: UserContext,
    watchlist_id: str,
    request: WatchlistItemCreateRequest,
) -> Watchlist:
    watchlist = get_watchlist_or_404(
        session=session,
        current_user=current_user,
        watchlist_id=watchlist_id,
    )

    company = None
    person = None
    duplicate = None
    if request.entity_type == "company":
        company = session.scalar(select(Company).where(Company.id == request.company_id))
        if company is None:
            raise AppError(
                code="NOT_FOUND",
                message="Company not found.",
                status_code=404,
                details={"company_id": request.company_id},
            )
        duplicate = session.scalar(
            select(WatchlistItem).where(
                WatchlistItem.watchlist_id == watchlist.id,
                WatchlistItem.entity_type == "company",
                WatchlistItem.company_id == company.id,
            )
        )
    else:
        person = session.scalar(select(Person).where(Person.id == request.person_id))
        if person is None:
            raise AppError(
                code="NOT_FOUND",
                message="Person not found.",
                status_code=404,
                details={"person_id": request.person_id},
            )
        duplicate = session.scalar(
            select(WatchlistItem).where(
                WatchlistItem.watchlist_id == watchlist.id,
                WatchlistItem.entity_type == "person",
                WatchlistItem.person_id == person.id,
            )
        )

    if duplicate is not None:
        raise AppError(
            code="CONFLICT",
            message="Entity is already on this watchlist.",
            status_code=409,
        )

    item = WatchlistItem(
        watchlist_id=watchlist.id,
        entity_type=request.entity_type,
        company_id=company.id if company is not None else None,
        person_id=person.id if person is not None else None,
        notes=request.notes,
    )
    session.add(item)
    watchlist.updated_at = _utcnow()
    session.commit()
    return get_watchlist_or_404(
        session=session,
        current_user=current_user,
        watchlist_id=watchlist.id,
    )


def remove_watchlist_item(
    *,
    session: Session,
    current_user: UserContext,
    watchlist_id: str,
    item_id: str,
) -> Watchlist:
    watchlist = get_watchlist_or_404(
        session=session,
        current_user=current_user,
        watchlist_id=watchlist_id,
    )
    item = session.scalar(
        select(WatchlistItem).where(
            WatchlistItem.id == item_id,
            WatchlistItem.watchlist_id == watchlist.id,
        )
    )
    if item is None:
        raise AppError(
            code="NOT_FOUND",
            message="Watchlist item not found.",
            status_code=404,
            details={"item_id": item_id},
    )
    session.delete(item)
    watchlist.updated_at = _utcnow()
    session.commit()
    return get_watchlist_or_404(
        session=session,
        current_user=current_user,
        watchlist_id=watchlist.id,
    )


def get_watchlist_signals(
    *,
    session: Session,
    current_user: UserContext,
    watchlist_id: str,
) -> WatchlistSignalsResponse:
    watchlist = get_watchlist_or_404(
        session=session,
        current_user=current_user,
        watchlist_id=watchlist_id,
    )
    company_ids = [item.company_id for item in watchlist.items if item.company_id]
    person_ids = [item.person_id for item in watchlist.items if item.person_id]
    if not company_ids and not person_ids:
        return WatchlistSignalsResponse(watchlist_id=watchlist.id, signals=[])

    predicates = []
    if company_ids:
        predicates.append(Signal.company_id.in_(company_ids))
    if person_ids:
        predicates.append(Signal.person_id.in_(person_ids))

    signals = session.scalars(
        select(Signal)
        .where(or_(*predicates))
        .order_by(Signal.occurred_at.desc().nullslast(), Signal.created_at.desc())
    ).all()

    company_map = {
        item.company_id: item.company for item in watchlist.items if item.company is not None
    }
    person_map = {
        item.person_id: item.person for item in watchlist.items if item.person is not None
    }
    entries = []
    for signal in signals:
        entity_name = None
        entity_id = None
        if signal.company_id is not None:
            entity_id = signal.company_id
            company = company_map.get(signal.company_id)
            entity_name = company.name if company is not None else None
        elif signal.person_id is not None:
            entity_id = signal.person_id
            person = person_map.get(signal.person_id)
            entity_name = person.name if person is not None else None
        entries.append(
            WatchlistSignalEntry(
                signal_id=signal.id,
                entity_type=signal.entity_type,
                entity_id=entity_id,
                entity_name=entity_name,
                signal_type=signal.signal_type,
                title=signal.title,
                description=signal.description,
                confidence=signal.confidence,
                occurred_at=signal.occurred_at,
                created_at=signal.created_at,
            )
        )
    return WatchlistSignalsResponse(watchlist_id=watchlist.id, signals=entries)


def summarize_refresh(
    *,
    watchlist_id: str,
    refreshed_companies: int,
    refreshed_people: int,
    signals_upserted: int,
    skipped: int,
) -> WatchlistRefreshResponse:
    return WatchlistRefreshResponse(
        watchlist_id=watchlist_id,
        refreshed_companies=refreshed_companies,
        refreshed_people=refreshed_people,
        signals_upserted=signals_upserted,
        skipped=skipped,
    )
