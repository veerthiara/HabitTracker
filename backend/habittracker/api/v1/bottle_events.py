import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from habittracker.api.deps import get_current_user_id
from habittracker.models.repository import bottle_event_repository
from habittracker.models.repository.session import get_session
from habittracker.schemas.bottle_event import BottleEventCreate, BottleEventRead

router = APIRouter(prefix="/bottle-events", tags=["bottle-events"])


@router.get("/", response_model=list[BottleEventRead])
def list_events(
    date: date | None = Query(None),
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return bottle_event_repository.get_events(session, user_id, date)


@router.post("/", response_model=BottleEventRead, status_code=status.HTTP_201_CREATED)
def create_event(
    body: BottleEventCreate,
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return bottle_event_repository.create_event(session, user_id, body)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: uuid.UUID,
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    event = bottle_event_repository.get_event(session, event_id, user_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    bottle_event_repository.delete_event(session, event)
