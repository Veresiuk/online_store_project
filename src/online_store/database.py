import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_FILE = "store.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

# Підключення для SQLAlchemy
engine = create_engine(
    DATABASE_URL,
    echo=False,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db_connection(db_path: str = DATABASE_FILE) -> sqlite3.Connection:
    """Підключення через стандартний модуль sqlite3 (DB-API)."""
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection