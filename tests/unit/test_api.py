


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_returns_service_name(self, client):
        resp = client.get("/health")
        assert resp.json()["service"] == "qr-vault"

    def test_metrics_endpoint_reachable(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200


class TestCreateQR:
    def test_create_returns_201(self, client, sample_qr_payload):
        resp = client.post("/qr", json=sample_qr_payload)
        assert resp.status_code == 201

    def test_create_response_has_short_code(self, client, sample_qr_payload):
        resp = client.post("/qr", json=sample_qr_payload)
        data = resp.json()
        assert "short_code" in data
        assert len(data["short_code"]) == 8

    def test_create_response_has_redirect_url(self, client, sample_qr_payload):
        resp = client.post("/qr", json=sample_qr_payload)
        data = resp.json()
        assert "redirect_url" in data
        assert data["short_code"] in data["redirect_url"]

    def test_create_preserves_target_url(self, client, sample_qr_payload):
        resp = client.post("/qr", json=sample_qr_payload)
        assert resp.json()["target_url"] == sample_qr_payload["target_url"]

    def test_create_preserves_label(self, client, sample_qr_payload):
        resp = client.post("/qr", json=sample_qr_payload)
        assert resp.json()["label"] == sample_qr_payload["label"]

    def test_create_status_is_active(self, client, sample_qr_payload):
        resp = client.post("/qr", json=sample_qr_payload)
        assert resp.json()["status"] == "active"

    def test_create_scan_count_zero(self, client, sample_qr_payload):
        resp = client.post("/qr", json=sample_qr_payload)
        assert resp.json()["scan_count"] == 0

    def test_create_without_label(self, client):
        resp = client.post("/qr", json={"target_url": "https://no-label.com"})
        assert resp.status_code == 201

    def test_create_with_utm_params(self, client):
        payload = {
            "target_url": "https://utm.example.com",
            "utm_source": "newsletter",
            "utm_medium": "email",
            "utm_campaign": "spring2026",
        }
        resp = client.post("/qr", json=payload)
        assert resp.status_code == 201

    def test_create_invalid_error_correction(self, client):
        payload = {"target_url": "https://example.com", "error_correction": "X"}
        resp = client.post("/qr", json=payload)
        assert resp.status_code == 422

    def test_create_box_size_too_large(self, client):
        payload = {"target_url": "https://example.com", "box_size": 999}
        resp = client.post("/qr", json=payload)
        assert resp.status_code == 422


class TestGetQR:
    def test_get_existing(self, client, created_qr):
        code = created_qr["short_code"]
        resp = client.get(f"/qr/{code}")
        assert resp.status_code == 200
        assert resp.json()["short_code"] == code

    def test_get_nonexistent_returns_404(self, client):
        resp = client.get("/qr/NOTEXIST")
        assert resp.status_code == 404


class TestListQR:
    def test_list_returns_array(self, client, created_qr):
        resp = client.get("/qr")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_contains_created(self, client, created_qr):
        resp = client.get("/qr")
        codes = [item["short_code"] for item in resp.json()]
        assert created_qr["short_code"] in codes

    def test_list_limit_param(self, client):
      
        for _ in range(5):
            client.post("/qr", json={"target_url": "https://limit.com"})
        resp = client.get("/qr?limit=2")
        assert len(resp.json()) <= 2


class TestUpdateQR:
    def test_patch_label(self, client, created_qr):
        code = created_qr["short_code"]
        resp = client.patch(f"/qr/{code}", json={"label": "Updated Label"})
        assert resp.status_code == 200
        assert resp.json()["label"] == "Updated Label"

    def test_patch_target_url(self, client, created_qr):
        code = created_qr["short_code"]
        resp = client.patch(f"/qr/{code}", json={"target_url": "https://new-target.com"})
        assert resp.status_code == 200
        assert resp.json()["target_url"] == "https://new-target.com"

    def test_patch_nonexistent_returns_404(self, client):
        resp = client.patch("/qr/GHOST", json={"label": "x"})
        assert resp.status_code == 404


class TestDeleteQR:
    def test_delete_returns_204(self, client, sample_qr_payload):
        r = client.post("/qr", json=sample_qr_payload)
        code = r.json()["short_code"]
        resp = client.delete(f"/qr/{code}")
        assert resp.status_code == 204

    def test_delete_then_get_404(self, client, sample_qr_payload):
        r = client.post("/qr", json=sample_qr_payload)
        code = r.json()["short_code"]
        client.delete(f"/qr/{code}")
        assert client.get(f"/qr/{code}").status_code == 404

    def test_delete_nonexistent_returns_404(self, client):
        assert client.delete("/qr/NOTHERE").status_code == 404


class TestRedirect:
    def test_redirect_increments_scan_count(self, client, created_qr):
        code = created_qr["short_code"]
        client.get(f"/qr/{code}/redirect", follow_redirects=False)
        updated = client.get(f"/qr/{code}").json()
        assert updated["scan_count"] == 1

    def test_redirect_nonexistent_404(self, client):
        resp = client.get("/qr/FAKECODE/redirect", follow_redirects=False)
        assert resp.status_code == 404


class TestAnalytics:
    def test_analytics_endpoint_exists(self, client, created_qr):
        code = created_qr["short_code"]
        resp = client.get(f"/qr/{code}/analytics")
        assert resp.status_code == 200

    def test_analytics_returns_scan_count(self, client, created_qr):
        code = created_qr["short_code"]
        data = client.get(f"/qr/{code}/analytics").json()
        assert "scan_count" in data

    def test_analytics_has_daily_scans(self, client, created_qr):
        code = created_qr["short_code"]
        data = client.get(f"/qr/{code}/analytics").json()
        assert "daily_scans" in data
        assert isinstance(data["daily_scans"], dict)
