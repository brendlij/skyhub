from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

settings.data_dir.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{settings.database_path.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


def create_db_tables():
    Base.metadata.create_all(bind=engine)


def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from app.models import node, node_camera_settings  # noqa: F401
