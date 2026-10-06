from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app import events, main


def test_production_startup_without_broker_or_table_management(monkeypatch):
    monkeypatch.setattr(main, "ENDPOINT_URL", None)
    monkeypatch.setattr(events, "RABBITMQ_URL", None)

    def unexpected_provisioning():
        raise AssertionError("Production must not manage DynamoDB tables")

    monkeypatch.setattr(main, "create_table_if_missing", unexpected_provisioning)
    broker_connect = AsyncMock()
    monkeypatch.setattr(events.aio_pika, "connect_robust", broker_connect)
    with TestClient(main.app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert main.app.state.rabbit is None
    broker_connect.assert_not_awaited()


def test_local_startup_preserves_provisioning_and_broker_cleanup(monkeypatch):
    from unittest.mock import Mock

    provision = Mock()
    connection = Mock(close=AsyncMock())
    monkeypatch.setattr(main, "ENDPOINT_URL", "http://localhost:8000")
    monkeypatch.setattr(main, "create_table_if_missing", provision)
    monkeypatch.setattr(main, "connect", AsyncMock(return_value=connection))
    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
    provision.assert_called_once_with()
    connection.close.assert_awaited_once_with()


def test_status_update_without_broker_still_persists(client, login_as, published):
    client.app.state.rabbit = None
    job = client.post("/jobs", json={"company": "Example", "role": "Engineer"}).json()
    response = client.put(
        f"/jobs/{job['id']}",
        json={"company": "Example", "role": "Engineer", "status": "interview"},
    )
    assert response.status_code == 200
    assert client.get(f"/jobs/{job['id']}").json()["status"] == "interview"
    assert published == []
