import httpx

JOB = {"company": "Google", "role": "Backend Engineer", "status": "Applied", "note": "x"}


def create(client, **overrides):
    return client.post("/jobs", json={**JOB, **overrides}).json()


# ---------- CRUD ----------

def test_create_and_list(client, login_as):
    resp = client.post("/jobs", json=JOB)
    assert resp.status_code == 201
    assert resp.json()["company"] == "Google"
    assert "user_id" not in resp.json()
    assert len(client.get("/jobs").json()) == 1


def test_get_job(client, login_as):
    job = create(client)
    resp = client.get(f"/jobs/{job['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == job["id"]


def test_get_missing_job_returns_404(client, login_as):
    assert client.get("/jobs/does-not-exist").status_code == 404


def test_update_missing_job_returns_404(client, login_as):
    assert client.put("/jobs/does-not-exist", json=JOB).status_code == 404


def test_delete_job(client, login_as):
    job = create(client)
    assert client.delete(f"/jobs/{job['id']}").status_code == 204
    assert client.get(f"/jobs/{job['id']}").status_code == 404


def test_delete_missing_job_returns_404(client, login_as):
    assert client.delete("/jobs/does-not-exist").status_code == 404


# ---------- per-user isolation ----------

def test_users_cannot_see_or_delete_each_others_jobs(client, login_as):
    login_as("1")
    job = create(client)

    login_as("2")
    assert client.get("/jobs").json() == []
    assert client.get(f"/jobs/{job['id']}").status_code == 404
    assert client.delete(f"/jobs/{job['id']}").status_code == 404

    login_as("1")
    assert client.get(f"/jobs/{job['id']}").status_code == 200


# ---------- events ----------

def test_status_change_publishes_event(client, login_as, published):
    job = create(client)
    resp = client.put(
        f"/jobs/{job['id']}", json={**JOB, "status": "interview"}
    )
    assert resp.status_code == 200
    assert len(published) == 1
    assert published[0]["old_status"] == "Applied"
    assert published[0]["new_status"] == "interview"
    assert published[0]["email"] == "user@example.com"
    assert published[0]["company"] == "Google"


def test_edit_without_status_change_publishes_nothing(client, login_as, published):
    job = create(client)
    client.put(f"/jobs/{job['id']}", json={**JOB, "note": "changed"})
    assert published == []


# ---------- real auth path (auth-service call faked) ----------

class FakeResponse:
    def __init__(self, status_code, data=None):
        self.status_code = status_code
        self._data = data or {}

    def json(self):
        return self._data


def fake_httpx(monkeypatch, *, response=None, error=None):
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url, headers=None):
            if error:
                raise error
            return response

    monkeypatch.setattr("app.auth.httpx.AsyncClient", FakeClient)


BEARER = {"Authorization": "Bearer whatever"}


def test_no_token_is_rejected(client):
    assert client.get("/jobs").status_code in (401, 403)


def test_auth_service_401_becomes_401(client, monkeypatch):
    fake_httpx(monkeypatch, response=FakeResponse(401))
    assert client.get("/jobs", headers=BEARER).status_code == 401


def test_auth_service_down_becomes_503(client, monkeypatch):
    fake_httpx(monkeypatch, error=httpx.ConnectError("boom"))
    assert client.get("/jobs", headers=BEARER).status_code == 503


def test_valid_token_uses_string_user_id(client, monkeypatch):
    # auth-service returns an int id; jobs-service must turn it into "5"
    fake_httpx(
        monkeypatch, response=FakeResponse(200, {"id": 5, "email": "e@example.com"})
    )
    resp = client.get("/jobs", headers=BEARER)
    assert resp.status_code == 200
    assert resp.json() == []
