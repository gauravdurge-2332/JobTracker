from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager 
from app.routes import jobs
from app.auth import UserDep
from app.dynamodb import create_table_if_missing

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_table_if_missing()
    yield

app = FastAPI(title="JobService", lifespan=lifespan)
app.include_router(jobs.router)



@app.get("/health")
def health():
    return {"status" : "ok"}


