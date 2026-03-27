import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from habittracker.api.deps import get_current_user_id
from habittracker.models.repository import habit_repository
from habittracker.models.repository.session import get_session
from habittracker.schemas.habit import HabitCreate, HabitRead, HabitUpdate

router = APIRouter(prefix="/habits", tags=["habits"])


@router.get("/", response_model=list[HabitRead])
def list_habits(
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return habit_repository.get_habits(session, user_id)


@router.post("/", response_model=HabitRead, status_code=status.HTTP_201_CREATED)
def create_habit(
    body: HabitCreate,
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return habit_repository.create_habit(session, user_id, body)


@router.get("/{habit_id}", response_model=HabitRead)
def get_habit(
    habit_id: uuid.UUID,
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    habit = habit_repository.get_habit(session, habit_id, user_id)
    if not habit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found")
    return habit


@router.patch("/{habit_id}", response_model=HabitRead)
def update_habit(
    habit_id: uuid.UUID,
    body: HabitUpdate,
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    habit = habit_repository.get_habit(session, habit_id, user_id)
    if not habit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found")
    return habit_repository.update_habit(session, habit, body)


@router.delete("/{habit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_habit(
    habit_id: uuid.UUID,
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    habit = habit_repository.get_habit(session, habit_id, user_id)
    if not habit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found")
    habit_repository.delete_habit(session, habit)
