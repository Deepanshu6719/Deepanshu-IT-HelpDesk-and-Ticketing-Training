def success_data(response):
    assert 200 <= response.status_code < 300

    body = response.json()

    assert body["success"] is True
    assert "data" in body

    return body["data"]
