import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from habittracker.models.orm.habittracker.note import Note
from habittracker.schemas.note import NoteCreate


def get_notes(session: Session, user_id: uuid.UUID, limit: int = 50) -> list[Note]:
    return list(
        session.scalars(
            select(Note)
            .where(Note.user_id == user_id)
            .order_by(Note.created_at.desc())
            .limit(limit)
        )
    )


def create_note(session: Session, user_id: uuid.UUID, data: NoteCreate) -> Note:
    note = Note(user_id=user_id, **data.model_dump())
    session.add(note)
    session.commit()
    session.refresh(note)
    return note


def get_note(session: Session, note_id: uuid.UUID, user_id: uuid.UUID) -> Note | None:
    return session.scalar(
        select(Note).where(Note.id == note_id, Note.user_id == user_id)
    )


def delete_note(session: Session, note: Note) -> None:
    session.delete(note)
    session.commit()
