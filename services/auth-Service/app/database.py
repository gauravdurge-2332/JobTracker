from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import os 


DATABASE_URL = "postgresql+psycopg://postgres:240906@localhost:5432/authentication"

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

def get_session():
    with SessionLocal() as session:
        yield session