import os

import boto3

TABLE_NAME = os.getenv("JOBS_TABLE", "jobs")
ENDPOINT_URL = os.getenv("DYNAMODB_ENDPOINT")   # set locally, leave unset on AWS
REGION = os.getenv("AWS_REGION", "ap-south-1")


def _resource():
    return boto3.resource("dynamodb", region_name=REGION, endpoint_url=ENDPOINT_URL)


def create_table_if_missing():
    dynamodb = _resource()
    if TABLE_NAME in [t.name for t in dynamodb.tables.all()]:
        return
    table = dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},   # partition key
            {"AttributeName": "id", "KeyType": "RANGE"},       # sort key
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()


def get_table():
    return _resource().Table(TABLE_NAME)