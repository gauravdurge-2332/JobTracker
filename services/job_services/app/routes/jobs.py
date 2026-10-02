import uuid
from typing import Annotated, Any

from boto3.dynamodb.conditions import Key 
from fastapi import APIRouter, Depends, HTTPException, status

from app.dynamodb import get_table
from app.scehma import JobCreate, JobOut

router = APIRouter(prefix="/jobs" , tags=["Jobs_APIS"])

Tabledep = Annotated[Any , Depends(get_table)]
DEMO_USER = "demo" 

#Checks whether the job is present -> dict means return type is dictionary
def _get_job_404(table , job_id : str) -> dict:
    job = table.get_item(
        Key={"user_id": DEMO_USER, "id": job_id}
    ).get("Item")
    if job is None :
        return HTTPException( status_code=404,
            detail="Job not found")
    return job

@router.post("" , response_model=JobOut , status_code=status.HTTP_201_CREATED)
def create_job(payload : JobCreate , tabledep : Tabledep):
   item = {
      "user_id" : DEMO_USER ,
      "id" : str(uuid.uuid4()),
      **payload.model_dump(mode="json"), #this line mean we are separating from the payload
   }
   tabledep.put_item(Item = item)
   return item

@router.get("" , response_model=list[JobOut])
def list__jobs(table : Tabledep):
    result = table.query(KeyConditionExpression=Key("user_id").eq(DEMO_USER))
    return result["Items"]

@router.get("/{job_id}" , response_model=JobOut)
def get_job(job_id : str , table : Tabledep):
    return _get_job_404(table , job_id)


@router.put("/{job_id}", response_model=JobOut)
def update_job(job_id: str, payload: JobCreate, table: Tabledep):
    _get_job_404(table, job_id)          # raises 404 if the job doesn't exist
    item = {"user_id": DEMO_USER, "id": job_id, **payload.model_dump(mode="json")}
    table.put_item(Item=item)               # same key, so it overwrites the old item
    return item


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: str, table: Tabledep):
    _get_job_404(table, job_id)
    table.delete_item(Key={"user_id": DEMO_USER, "id": job_id})

    


