from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager

from app.database import engine
from app.model import Base
from app.routes import authRoutes


@asynccontextmanager
async def lifeSpan(app : FastAPI):
    Base.metadata.create_all(bind=engine)
    yield 

app = FastAPI(title = "Authentication" , lifespan=lifeSpan)
app.include_router(authRoutes.router)




