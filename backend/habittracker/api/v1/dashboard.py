import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from habittracker.api.deps import get_current_user_id
from habittracker.models.repository import dashboard_repository
from habittracker.models.repository.session import get_session
from habittracker.schemas.dashboard import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_summary(
    date: date = Query(default_factory=date.today),
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return dashboard_repository.get_summary(session, user_id, date)
