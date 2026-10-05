from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager

from app.dynamodb import create_table_if_missing
from app.events import connect
from app.routes import jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_table_if_missing()
    app.state.rabbit = await connect()
    try:
        yield
    finally:
        await app.state.rabbit.close()

app = FastAPI(title="JobService", lifespan=lifespan)
app.include_router(jobs.router)



@app.get("/health")
def health():
    return {"status" : "ok"}


