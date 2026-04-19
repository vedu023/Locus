def test_root_serves_workbench_shell(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Locus Workbench" in response.text
    assert "/ui/app.js" in response.text


def test_ui_assets_are_served(client):
    stylesheet = client.get("/ui/styles.css")
    script = client.get("/ui/app.js")
    favicon = client.get("/ui/favicon.svg")

    assert stylesheet.status_code == 200
    assert "text/css" in stylesheet.headers["content-type"]
    assert "workspace" in stylesheet.text

    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]
    assert "const state" in script.text
    assert "requestJson" in script.text

    assert favicon.status_code == 200
    assert "image/svg+xml" in favicon.headers["content-type"]
