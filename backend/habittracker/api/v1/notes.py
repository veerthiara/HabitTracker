import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from habittracker.api.deps import get_current_user_id
from habittracker.models.repository import note_repository
from habittracker.models.repository.session import get_session
from habittracker.schemas.note import NoteCreate, NoteRead

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("/", response_model=list[NoteRead])
def list_notes(
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return note_repository.get_notes(session, user_id)


@router.post("/", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def create_note(
    body: NoteCreate,
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return note_repository.create_note(session, user_id, body)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: uuid.UUID,
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    note = note_repository.get_note(session, note_id, user_id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    note_repository.delete_note(session, note)
