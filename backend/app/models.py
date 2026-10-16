import datetime as dt
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now()


class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    subject: str = ""
    kind: str = "note"                 # note | supplement | upload
    source_path: str                   # original file inside data/
    pdf_path: str = ""                 # per-document PDF inside data/pdf
    sort_order: float = 0
    page_count: int = 0
    book_start_page: Optional[int] = None
    translate: bool = True
    polish: bool = False               # restructure into book style with the local model before ingesting
    status: str = "pending"            # pending | processing | ready | error
    error: str = ""
    created_at: datetime = Field(default_factory=now)


class Chunk(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(index=True, foreign_key="document.id")
    page: int                          # 1-based page inside the document PDF
    section: str = ""
    text: str
    rects: str = "[]"                  # JSON [[x0,y0,x1,y1], ...] for highlighting
    embedding: Optional[bytes] = None  # float32 vector


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str
    document_id: Optional[int] = None
    status: str = "queued"             # queued | running | done | error
    progress: float = 0
    message: str = ""
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class ChatSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = "New session"
    mode: str = "study"                # study | public
    created_at: datetime = Field(default_factory=now)
    ended_at: Optional[datetime] = None
    summary: str = ""                  # JSON summary produced by /end


class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(index=True, foreign_key="chatsession.id")
    role: str                          # user | assistant | system
    content: str
    kind: str = "text"                 # text | quiz | quiz_result | summary | reminder
    payload: str = ""                  # JSON (sources, quiz ids, ...)
    created_at: datetime = Field(default_factory=now)


class QuizItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(index=True, foreign_key="chatsession.id")
    topic: str = ""
    qtype: str = "mcq"                 # mcq | short
    question: str
    options: str = "[]"                # JSON list for mcq
    answer: str = ""                   # correct option index (mcq) or model answer (short)
    explanation: str = ""
    source: str = "{}"                 # JSON citation
    user_answer: Optional[str] = None
    score: Optional[float] = None      # 0..1
    feedback: str = ""


class WorkTask(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: str = ""
    company: str = ""
    project: str = ""
    tags: str = ""                     # comma separated
    impact: str = ""
    date: Optional[dt.date] = None
    public: bool = True
    created_at: datetime = Field(default_factory=now)


class Profile(SQLModel, table=True):
    id: int = Field(default=1, primary_key=True)
    data: str = "{}"                   # JSON profile (see data/profile.example.json)


class Reminder(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    notes: str = ""
    start: datetime
    end: Optional[datetime] = None
    all_day: bool = False
    google_event_id: str = ""
    created_at: datetime = Field(default_factory=now)


class Outbox(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    channel: str = "whatsapp"
    recipient: str = ""
    subject: str = ""
    body: str
    status: str = "pending"            # pending | sent | failed | skipped
    error: str = ""
    created_at: datetime = Field(default_factory=now)


class Note(SQLModel, table=True):
    """A page in the notes workspace. HTML is the editor's source of truth; markdown is derived for RAG/export."""
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = "Untitled"
    html: str = ""
    markdown: str = ""
    document_id: Optional[int] = None  # library document created when the note is added to the book
    book_part: str = ""                # part of the book it was added to
    published_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str = ""
