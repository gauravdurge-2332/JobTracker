from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import os 



engine = create_engine(os.environ["DATABASE_URL"])

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

def get_session():
    with SessionLocal() as session:
        yield session