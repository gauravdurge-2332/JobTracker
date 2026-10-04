import uuid
from typing import Annotated, Any
from fastapi import BackgroundTasks, Request
from app.events import publish_status_change
from boto3.dynamodb.conditions import Key 
from fastapi import APIRouter, Depends, HTTPException, status

from app.dynamodb import get_table
from app.scehma import JobCreate, JobOut
from app.auth import UserDep , CurrentUserDep

router = APIRouter(prefix="/jobs" , tags=["Jobs_APIS"])

Tabledep = Annotated[Any , Depends(get_table)]


#Checks whether the job is present -> dict means return type is dictionary
def _get_job_404(table ,user_id : str,job_id : str) -> dict:
    job = table.get_item(
        Key={"user_id": user_id, "id": job_id}
    ).get("Item")
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
  

@router.post("" , response_model=JobOut , status_code=status.HTTP_201_CREATED)
def create_job(payload : JobCreate , tabledep : Tabledep , user_id : UserDep):
   item = {
      "user_id" : user_id ,
      "id" : str(uuid.uuid4()),
      **payload.model_dump(mode="json"), #this line mean we are separating from the payload
   }
   tabledep.put_item(Item = item)
   return item

@router.get("" , response_model=list[JobOut])
def list__jobs(table : Tabledep , user_id : UserDep):
    result = table.query(KeyConditionExpression=Key("user_id").eq(user_id))
    return result["Items"]

@router.get("/{job_id}" , response_model=JobOut)
def get_job(job_id : str , table : Tabledep , user_id:UserDep):
    return _get_job_404(table ,user_id, job_id)


@router.put("/{job_id}", response_model=JobOut)
def update_job(job_id: str, payload: JobCreate, table: Tabledep , user_id : UserDep,
               user : CurrentUserDep,
               request : Request,backgroud_task : BackgroundTasks):
    
    old = _get_job_404(table,user_id, job_id)          # raises 404 if the job doesn't exist
    item = {"user_id": user_id, "id": job_id, **payload.model_dump(mode="json")}
    table.put_item(Item=item) 
    
    
    if old["status"] != item["status"]:
        #publish the event in the RabbitMQ
        event = {
            "user_id": user_id,
            "job_id": job_id,
            "company":old["company"],
            "email" : user.email,
            "role":old["role"],
            "old_status": old["status"],
            "new_status": item["status"],
        }
        backgroud_task.add_task(
            publish_status_change , 
            request.app.state.rabbit , 
            event
        )
               
    return item


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: str, table: Tabledep , user_id : UserDep):
    _get_job_404(table,user_id, job_id)
    table.delete_item(Key={"user_id": user_id, "id": job_id})

    


