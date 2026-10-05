import os

# Config is read at import time, so set it BEFORE importing the app
os.environ["AUTH_SERVICE_URL"] = "http://auth-service:8002"
os.environ["DYNAMODB_ENDPOINT"] = "http://localhost:8000"
os.environ["RABBITMQ_URL"] = "amqp://guest:guest@localhost:5672/"
os.environ["AWS_REGION"] = "ap-south-1"
os.environ["AWS_DEFAULT_REGION"] = "ap-south-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app.auth import CurrentUser, get_current_user
from app.dynamodb import get_table
from app.main import app


@pytest.fixture
def table():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="ap-south-1")
        yield ddb.create_table(
            TableName="jobs",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )


@pytest.fixture
def client(table):
    app.dependency_overrides[get_table] = lambda: table
    app.state.rabbit = object()  # lifespan doesn't run in tests
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def login_as(client):
    """Skip auth-service: pretend the caller is this user."""

    def _login(user_id: str, email: str = "user@example.com"):
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            id=user_id, email=email
        )

    _login("1")
    return _login


@pytest.fixture
def published(monkeypatch):
    """Capture events instead of talking to RabbitMQ."""
    events = []

    async def fake_publish(connection, event):
        events.append(event)

    monkeypatch.setattr("app.routes.jobs.publish_status_change", fake_publish)
    return events
