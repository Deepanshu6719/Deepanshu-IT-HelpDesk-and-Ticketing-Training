import os
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    database=os.getenv("DB_NAME"),
)# the db url and also the db driver is present here

engine = create_engine(DATABASE_URL)#creating the engine and its object in "engine"

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)#its a session factory
