from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Base


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


SQLITE_DOCUMENT_COLUMNS = {
    "page_count": "ALTER TABLE documents ADD COLUMN page_count INTEGER DEFAULT 0",
    "chunk_count": "ALTER TABLE documents ADD COLUMN chunk_count INTEGER DEFAULT 0",
    "retrieval_ready": "ALTER TABLE documents ADD COLUMN retrieval_ready BOOLEAN DEFAULT 0",
    "processing_error": "ALTER TABLE documents ADD COLUMN processing_error TEXT",
}

SQLITE_CHUNK_COLUMNS = {
    "token_count": "ALTER TABLE chunks ADD COLUMN token_count INTEGER DEFAULT 0",
    "keyword_signature": "ALTER TABLE chunks ADD COLUMN keyword_signature VARCHAR(512) DEFAULT ''",
}

SQLITE_CONVERSATION_COLUMNS = {
    "scoped_document_ids_json": "ALTER TABLE conversations ADD COLUMN scoped_document_ids_json TEXT DEFAULT '[]'",
}



def init_db() -> None:
    if not settings.auto_init_db:
        return
    Base.metadata.create_all(bind=engine)
    if settings.database_url.startswith("sqlite"):
        with engine.begin() as connection:
            ensure_sqlite_columns(connection, "documents", SQLITE_DOCUMENT_COLUMNS)
            ensure_sqlite_columns(connection, "chunks", SQLITE_CHUNK_COLUMNS)
            ensure_sqlite_columns(connection, "conversations", SQLITE_CONVERSATION_COLUMNS)



def ensure_sqlite_columns(connection: Connection, table_name: str, column_statements: dict[str, str]) -> None:
    rows = connection.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
    existing_columns = {row[1] for row in rows}
    for column_name, statement in column_statements.items():
        if column_name not in existing_columns:
            connection.exec_driver_sql(statement)



def ping_database() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False



def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
