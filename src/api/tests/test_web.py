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
