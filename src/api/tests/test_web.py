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
