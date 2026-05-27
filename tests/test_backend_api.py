"""Smoke tests for the FastAPI backend boundary."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "autosales-engineer-api"}


def test_catalog_stats_endpoint() -> None:
    response = client.get("/api/catalog/stats")
    data = response.json()

    assert response.status_code == 200
    assert data["total_products"] > 0
    assert "networking" in data["categories"]


def test_catalog_products_search_endpoint() -> None:
    response = client.get("/api/catalog/products", params={"category": "networking", "q": "Cisco"})
    data = response.json()

    assert response.status_code == 200
    assert data["count"] >= 1
    assert any(product["brand"] == "Cisco" for product in data["products"])


def test_catalog_product_not_found() -> None:
    response = client.get("/api/catalog/products/missing-product")

    assert response.status_code == 404


def test_budget_fit_endpoint() -> None:
    response = client.post(
        "/api/tools/budget-fit",
        json={
            "product_ids": ["prod_net_004"],
            "quantities": {"prod_net_004": 2},
            "budget_myr": 2000,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["data"]["total_myr"] == 840
    assert data["data"]["within_budget"] is True


def test_pipeline_run_rejects_invalid_image_base64() -> None:
    response = client.post(
        "/api/pipeline/runs",
        json={
            "raw_brief": "Client: Example\nUse case: networking refresh",
            "image_base64": "not-base64",
            "image_media_type": "image/png",
        },
    )

    assert response.status_code == 422
    assert "image_base64" in response.text