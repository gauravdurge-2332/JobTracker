from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager

from app.dynamodb import ENDPOINT_URL, create_table_if_missing
from app.events import connect
from app.routes import jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Real AWS tables are provisioned separately; the instance role only has CRUD access.
    if ENDPOINT_URL:
        create_table_if_missing()
    app.state.rabbit = await connect()
    try:
        yield
    finally:
        if app.state.rabbit is not None:
            await app.state.rabbit.close()

app = FastAPI(title="JobService", lifespan=lifespan)
app.include_router(jobs.router)



@app.get("/health")
def health():
    return {"status" : "ok"}


