import os

# Configuración falsa ANTES de importar la app (no se conecta a ningún RDS real).
os.environ.update(DB_HOST="fake", DB_USER="fake", DB_PASSWORD="fake",
                  API_KEY_ADMIN="clave-admin-test", API_KEY_CONTROL="clave-control-test")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.demo_runner import DemoRunner
from tests.fakes import FakeRDS, sembrar

ADMIN = {"X-API-Key": "clave-admin-test"}
CONTROL = {"X-API-Key": "clave-control-test"}


@pytest.fixture
def rds():
    r = FakeRDS()
    sembrar(r)
    return r


@pytest.fixture
def client(rds):
    with TestClient(app) as c:
        # Sustituye RDS real por el simulado (el pool real nunca se llega a usar)
        app.state.db = rds
        app.state.executor = rds
        app.state.demo_runner = DemoRunner(rds, rds, app.state.ws_manager)
        yield c
