from sqlalchemy import URL, create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings

DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=settings.DB_USER,
    password=settings.DB_PASSWORD,
    host=settings.DB_HOST,
    port=settings.DB_PORT,
    database=settings.DB_NAME,
)  # the db url and also the db driver is present here

engine = create_engine(
    DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 3},
)  # creating the engine and its object in "engine"

SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False
)  # its a session factory
