def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {"status": "ok"},
        "error": None,
    }


def test_v1_health_check(client):
    response = client.get("/v1/health")

    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ok"}
