def test_validation_error_is_reported_with_field_paths(client, master_headers, game_payload):
    game_payload["max_players"] = 9
    response = client.post("/api/v1/games", json=game_payload, headers=master_headers)
    body = response.json()
    assert response.status_code == 400
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "body.max_players"


def test_real_app_unknown_route_uses_not_found_envelope(client):
    response = client.get("/api/v1/nothing-here")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_real_app_wrong_method_uses_method_not_allowed_envelope(client):
    response = client.put("/api/v1/rooms")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
