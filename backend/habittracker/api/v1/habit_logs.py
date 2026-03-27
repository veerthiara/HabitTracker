import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from habittracker.api.deps import get_current_user_id
from habittracker.models.repository import habit_log_repository
from habittracker.models.repository.session import get_session
from habittracker.schemas.habit_log import HabitLogCreate, HabitLogRead

router = APIRouter(prefix="/habit-logs", tags=["habit-logs"])


@router.get("/", response_model=list[HabitLogRead])
def list_logs(
    habit_id: uuid.UUID | None = Query(None),
    logged_date: date | None = Query(None),
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return habit_log_repository.get_logs(session, user_id, habit_id, logged_date)


@router.post("/", response_model=HabitLogRead, status_code=status.HTTP_201_CREATED)
def create_log(
    body: HabitLogCreate,
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    if habit_log_repository.log_exists(session, body.habit_id, user_id, body.logged_date):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Habit already logged for this date",
        )
    return habit_log_repository.create_log(session, user_id, body)


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_log(
    log_id: uuid.UUID,
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    log = habit_log_repository.get_log(session, log_id, user_id)
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log not found")
    habit_log_repository.delete_log(session, log)
