import pytest
import requests

BASE = "http://127.0.0.1:8000"
STORE = "STORE_BLR_002"

def test_health():
    r = requests.get(f"{BASE}/health")
    assert r.status_code == 200

def test_metrics():
    r = requests.get(f"{BASE}/stores/{STORE}/metrics")
    assert r.status_code == 200

def test_funnel():
    r = requests.get(f"{BASE}/stores/{STORE}/funnel")
    assert r.status_code == 200

def test_anomalies():
    r = requests.get(f"{BASE}/stores/{STORE}/anomalies")
    assert r.status_code == 200

def test_heatmap():
    r = requests.get(f"{BASE}/stores/{STORE}/heatmap")
    assert r.status_code == 200