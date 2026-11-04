import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from app.core.config import BASE_DIR, get_settings
from app.core.database import Database
from app.core.dependencies import get_db
from app.core.exceptions import AppError
from app.core.stored_procedures import StoredProcedureExecutor
from app.dashboard.router import STATIC_DIR, router as dashboard_router
from app.models.common import ErrorValidacionResponse
from app.routers import comandos, demos, estado, historial, vehiculos
from app.services.demo_runner import DemoRunner
from app.websocket import router as websocket_router
from app.websocket.websocket_manager import WebSocketManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        settings = get_settings()
    except ValidationError as exc:
        raise RuntimeError(
            f"Configuración incompleta. Revisa el archivo {BASE_DIR / '.env'} "
            f"(copia .env.example y complétalo):\n{exc}"
        ) from exc

    if not settings.db_user or not settings.db_password.get_secret_value():
        logger.warning("DB_USER o DB_PASSWORD están vacíos en .env: la conexión a RDS fallará")
    if not (settings.api_key_admin or settings.api_key_control):
        logger.warning("API_KEY_ADMIN / API_KEY_CONTROL no configuradas: las operaciones protegidas serán rechazadas")
    if not settings.dashboard_session_secret:
        logger.warning("DASHBOARD_SESSION_SECRET no configurado: el login del dashboard responderá 503")

    db = Database(settings)
    sp = StoredProcedureExecutor(db)
    manager = WebSocketManager()
    app.state.db = db
    app.state.executor = sp
    app.state.ws_manager = manager
    app.state.demo_runner = DemoRunner(db, sp, manager)
    yield
    await app.state.demo_runner.apagar()
    db.close()


app = FastAPI(
    title="API Vehículos IoT",
    description=(
        "Control de vehículos IoT. Datos en Amazon RDS (MySQL) mediante **Stored Procedures**; "
        "eventos en tiempo real por **WebSocket**: `ws://localhost:8000/ws/vehiculos/{id_vehiculo}`.\n\n"
        "Las operaciones de control y las destructivas requieren `X-API-Key` o una sesión válida del dashboard."
    ),
    version="1.1.0",
    lifespan=lifespan,
    responses={422: {"model": ErrorValidacionResponse, "description": "Datos de entrada inválidos"}},
    openapi_tags=[
        {"name": "Vehículos", "description": "Consulta y administración de vehículos"},
        {"name": "Comandos", "description": "Catálogo de comandos por vehículo"},
        {"name": "Estado", "description": "Último estado y movimiento individual (estado + historial)"},
        {"name": "Historial", "description": "Últimos movimientos individuales (máx. 10)"},
        {"name": "DEMO", "description": "Secuencias de N movimientos: administración, ejecución y cancelación"},
        {"name": "Sistema", "description": "Salud del servicio"},
    ],
)

app.include_router(vehiculos.router)
app.include_router(comandos.router)
app.include_router(estado.router)
app.include_router(historial.router)
app.include_router(demos.router)
app.include_router(websocket_router.router)
app.include_router(dashboard_router)
app.mount("/dashboard/assets", StaticFiles(directory=str(STATIC_DIR)), name="dashboard-assets")


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"codigo": exc.codigo, "mensaje": exc.mensaje}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    detalles = [
        {"campo": ".".join(str(p) for p in e["loc"] if p != "body"), "mensaje": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"error": {"codigo": "VALIDACION", "mensaje": "Datos de entrada inválidos",
                           "detalles": detalles}},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception):
    logger.exception("Error no controlado")  # el detalle solo queda en el log del servidor
    return JSONResponse(
        status_code=500,
        content={"error": {"codigo": "ERROR_INTERNO", "mensaje": "Error interno del servidor"}},
    )


@app.get("/health", tags=["Sistema"], summary="Verifica API y conexión a RDS",
         responses={503: {"description": "Base de datos no disponible"}})
def health(db: Database = Depends(get_db)):
    db.ping()
    return {"estado": "ok", "base_datos": "conectada"}
