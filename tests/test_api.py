import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_home_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "IDX" in response.text
    assert "READY TO ACTION" in response.text

def test_screener_endpoint(client):
    response = client.get("/screener")
    assert response.status_code == 200
    assert "Screener Universe" in response.text

def test_backtest_endpoint(client):
    response = client.get("/backtest")
    assert response.status_code == 200
    assert "Strategy Backtesting" in response.text

def test_stock_detail_endpoint(client):
    response = client.get("/stock/BBCA.JK")
    assert response.status_code == 200
    assert "BBCA.JK" in response.text
    assert "tvChart" in response.text

def test_status_endpoint(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
