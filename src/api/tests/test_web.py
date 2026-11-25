import pytest


@pytest.mark.technical
def test_web_index_serves_html(client):
    response = client.get("/app/")
    assert response.status_code == 200
    assert '<html lang="uk">' in response.text
    assert "app.js" in response.text
    assert "style.css" in response.text


@pytest.mark.technical
def test_web_app_js_served(client):
    response = client.get("/app/app.js")
    assert response.status_code == 200
    assert "window.App" in response.text


@pytest.mark.technical
def test_web_style_css_served(client):
    response = client.get("/app/style.css")
    assert response.status_code == 200
    assert ":root" in response.text


@pytest.mark.technical
def test_web_login_html_served(client):
    response = client.get("/app/login.html")
    assert response.status_code == 200
    assert '<html lang="uk">' in response.text
    assert "app.js" in response.text
    assert "style.css" in response.text


@pytest.mark.technical
def test_web_register_html_served(client):
    response = client.get("/app/register.html")
    assert response.status_code == 200
    assert '<html lang="uk">' in response.text
    assert "app.js" in response.text
    assert "style.css" in response.text


@pytest.mark.technical
def test_web_games_html_served(client):
    response = client.get("/app/games.html")
    assert response.status_code == 200
    assert '<html lang="uk">' in response.text
    assert "app.js" in response.text
    assert "style.css" in response.text


@pytest.mark.technical
def test_web_game_html_served(client):
    response = client.get("/app/game.html")
    assert response.status_code == 200
    assert '<html lang="uk">' in response.text
    assert "app.js" in response.text
    assert "style.css" in response.text


@pytest.mark.technical
def test_web_create_game_html_served(client):
    response = client.get("/app/create-game.html")
    assert response.status_code == 200
    assert '<html lang="uk">' in response.text
    assert "app.js" in response.text
    assert "style.css" in response.text


@pytest.mark.technical
def test_web_calendar_html_served(client):
    response = client.get("/app/calendar.html")
    assert response.status_code == 200
    assert '<html lang="uk">' in response.text
    assert "app.js" in response.text
    assert "style.css" in response.text


@pytest.mark.technical
def test_web_admin_html_served(client):
    response = client.get("/app/admin.html")
    assert response.status_code == 200
    assert '<html lang="uk">' in response.text
    assert "app.js" in response.text
    assert "style.css" in response.text


@pytest.mark.technical
def test_web_notifications_html_served(client):
    response = client.get("/app/notifications.html")
    assert response.status_code == 200
    assert '<html lang="uk">' in response.text


@pytest.mark.technical
def test_web_profile_html_served(client):
    response = client.get("/app/profile.html")
    assert response.status_code == 200
    assert '<html lang="uk">' in response.text


@pytest.mark.requirement("FR-002")
def test_web_create_game_html_edit_mode_markup(client):
    response = client.get("/app/create-game.html")
    assert response.status_code == 200
    html = response.text
    assert 'id="form-title"' in html
    assert 'id="forbidden-block"' in html
    assert 'id="not-found-block"' in html
    assert 'id="create-game-submit-btn"' in html
    assert 'id="cancel-btn"' in html
    assert "isEditMode" in html
    assert "^game_\\d+$" in html
    assert "Зберегти зміни" in html
    assert "Редагувати гру" in html
    assert "toLocalDatetimeInputValue" in html
    assert "ROOM_BUSY" in html
    assert "MASTER_BUSY" in html
    assert "ROOM_BLOCKED" in html
    assert "ROOM_CAPACITY_EXCEEDED" in html
    assert "MAX_PLAYERS_BELOW_ENROLLED" in html
    assert "Немає змін для збереження" in html


@pytest.mark.requirement("FR-002")
def test_web_game_html_edit_button_markup(client):
    response = client.get("/app/game.html")
    assert response.status_code == 200
    html = response.text
    assert 'id="edit-game-btn"' in html
    assert "Редагувати" in html
    assert "create-game.html?id=" in html
    assert "App.getMe" in html
    assert "currentGame.master_id" in html


@pytest.mark.requirement("FR-002")
def test_edit_game_scenario_flow_and_calendar_update(client, master_headers):
    # Майстер змінює назву та час початку гри
    new_starts_at = "2026-10-10T19:30:00Z"
    patch_resp = client.patch(
        "/api/v1/games/game_1",
        json={"title": "Оновлене Прокляття Страда", "starts_at": new_starts_at},
        headers=master_headers,
    )
    assert patch_resp.status_code == 200
    patched_data = patch_resp.json()
    assert patched_data["title"] == "Оновлене Прокляття Страда"
    assert patched_data["starts_at"].startswith("2026-10-10T19:30:00")

    # Зміна видна в деталях гри
    get_resp = client.get("/api/v1/games/game_1")
    assert get_resp.status_code == 200
    assert get_resp.json()["title"] == "Оновлене Прокляття Страда"

    # Зміна видна в календарі кімнат
    cal_resp = client.get(
        "/api/v1/rooms/calendar",
        params={"starts_at": "2026-10-10T00:00:00Z", "ends_at": "2026-10-11T00:00:00Z"},
    )
    assert cal_resp.status_code == 200
    cal_data = cal_resp.json()
    room_1_data = next((r for r in cal_data["rooms"] if r["room_id"] == "room_1"), None)
    assert room_1_data is not None
    booking = next((b for b in room_1_data["bookings"] if b["game_id"] == "game_1"), None)
    assert booking is not None
    assert booking["title"] == "Оновлене Прокляття Страда"
    assert booking["starts_at"].startswith("2026-10-10T19:30:00")


@pytest.mark.requirement("FR-002")
def test_edit_game_conflict_and_validation_errors(client, master_headers):
    # Спроба поставити гру на зайнятий час (у цей час user_1 веде game_2: 2026-10-11 16:00-20:00)
    conflict_resp = client.patch(
        "/api/v1/games/game_1",
        json={"starts_at": "2026-10-11T17:00:00Z"},
        headers=master_headers,
    )
    assert conflict_resp.status_code == 409
    assert conflict_resp.json()["error"]["code"] == "MASTER_BUSY"

    # Порожнє тіло запиту (коли користувач нічого не змінив)
    empty_resp = client.patch(
        "/api/v1/games/game_1",
        json={},
        headers=master_headers,
    )
    assert empty_resp.status_code == 400
    assert empty_resp.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.requirement("FR-002")
def test_edit_game_access_control(client, player_headers, owner_headers):
    # Звичайний гравець не може редагувати гру
    forbidden_player = client.patch(
        "/api/v1/games/game_1",
        json={"title": "Хакерська гра"},
        headers=player_headers,
    )
    assert forbidden_player.status_code == 403
    assert forbidden_player.json()["error"]["code"] == "FORBIDDEN"

    # Гість без токена
    unauthorized = client.patch(
        "/api/v1/games/game_1",
        json={"title": "Гра без входу"},
    )
    assert unauthorized.status_code == 401

    # Власник клубу може редагувати будь-яку гру
    owner_resp = client.patch(
        "/api/v1/games/game_1",
        json={"title": "Гра відредагована власником"},
        headers=owner_headers,
    )
    assert owner_resp.status_code == 200
    assert owner_resp.json()["title"] == "Гра відредагована власником"


@pytest.mark.technical
def test_web_app_describe_error_and_show_error(client):
    response = client.get("/app/app.js")
    assert response.status_code == 200
    js = response.text
    assert "describeError" in js
    assert "Забагато невдалих спроб входу" in js
    assert "Сервіс тимчасово недоступний" in js
    assert "Сервер не відповів вчасно" in js
    assert "Не вдалося" in js and "сервером" in js


@pytest.mark.technical
def test_web_401_redirect_to_login_with_next(client):
    app_js_resp = client.get("/app/app.js")
    assert app_js_resp.status_code == 200
    assert "login.html?next=" in app_js_resp.text

    login_html_resp = client.get("/app/login.html")
    assert login_html_resp.status_code == 200
    assert "getNextUrl" in login_html_resp.text


@pytest.mark.requirement("PERF-001", "US-001")
def test_web_game_optimistic_seat_counter(client):
    response = client.get("/app/game.html")
    assert response.status_code == 200
    html = response.text
    assert "renderGameCounter" in html
    assert "syncGameDetailsQuietly" in html
    assert "(currentGame.current_players || 0) + 1" in html
    assert "(currentGame.current_players || 0) - 1" in html


@pytest.mark.requirement("US-007", "SEC-002")
def test_web_game_player_list_role_access(client, player_headers):
    # Перевірка розмітки: спільна функція перевірки прав та відсутність запиту для player
    response = client.get("/app/game.html")
    assert response.status_code == 200
    html = response.text
    assert "canManageCurrentGame" in html
    assert "session.role === 'player'" in html

    # Перевірка контракту бекенду (B7): звичайний гравець отримує 403 при спробі списку гравців
    players_resp = client.get("/api/v1/games/game_1/players", headers=player_headers)
    assert players_resp.status_code == 403
    assert players_resp.json()["error"]["code"] == "FORBIDDEN"
