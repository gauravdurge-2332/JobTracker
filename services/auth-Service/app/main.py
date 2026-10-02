from fastapi import FastAPI

from app.model import Base
from app.database import engine

app = FastAPI()

Base.metadata.create_all(bind=engine)