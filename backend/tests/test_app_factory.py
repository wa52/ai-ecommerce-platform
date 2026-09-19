from app.main import create_app


def test_create_app_returns_fastapi_instance():
    from fastapi import FastAPI

    app = create_app()
    assert isinstance(app, FastAPI)


def test_health_route_registered():
    app = create_app()
    paths = set(app.openapi()["paths"])
    assert "/api/v1/health" in paths
    assert "/api/v1/health/live" in paths
    assert "/api/v1/tasks" in paths
    assert "/api/v1/tasks/{task_id}" in paths
