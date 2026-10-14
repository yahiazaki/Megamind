from contextlib import contextmanager

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from .config import get_settings
from . import models  # noqa: F401  (register tables)

_settings = get_settings()
engine = create_engine(f"sqlite:///{_settings.db_path}", connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as s:
        yield s


@contextmanager
def session_scope():
    with Session(engine) as s:
        yield s


def get_setting(key: str, default: str = "") -> str:
    with Session(engine) as s:
        row = s.get(models.Setting, key)
        return row.value if row and row.value != "" else default


def set_setting(key: str, value: str) -> None:
    with Session(engine) as s:
        row = s.get(models.Setting, key) or models.Setting(key=key)
        row.value = value
        s.add(row)
        s.commit()


def all_settings() -> dict:
    with Session(engine) as s:
        return {r.key: r.value for r in s.exec(select(models.Setting))}
