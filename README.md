# API Vehículos IoT (FastAPI + Amazon RDS + WebSocket)

API local que controla vehículos IoT. Los datos viven en **Amazon RDS (MySQL, base `vehiculo_iot`)** y se
acceden **solo mediante los 21 Stored Procedures**. Los eventos en tiempo real salen por **WebSocket**.
Práctica 2.5: todo corre en `localhost:8000`; la migración a EC2/dominio es la práctica 2.6.

## Estructura

```
Websocket_IoT/
├── .env                 ← TUS credenciales (no se sube a Git). Se crea desde .env.example
├── .env.example
├── requirements.txt / requirements-dev.txt
├── script/              ← scripts SQL (incluye vehiculo_iot_routines_faltantes.sql)
├── legacy/              ← código de la práctica anterior (referencia; no se ejecuta)
├── tests/               ← pruebas automáticas (RDS simulado)
└── app/
    ├── main.py          ← arranque, rutas, manejo de errores
    ├── core/            ← config, database (pool+transacciones), stored_procedures, security
    ├── models/          ← validación de entradas y formato de salidas (Pydantic)
    ├── repositories/    ← llaman a los SP (sin reglas de negocio)
    ├── services/        ← reglas de negocio, movimiento individual, DemoRunner
    ├── routers/         ← endpoints HTTP (GET/POST) documentados en Swagger
    └── websocket/       ← gestor por vehículo, eventos y endpoint WebSocket
```

## 1. Preparar la base de datos (una sola vez)

Tu `vehiculo_iot_routines.sql` trae **19 de los 21** SP. Ejecuta en tu RDS
`script/vehiculo_iot_routines_faltantes.sql` (crea `sp_actualizar_demo` y `sp_agregar_movimiento_demo`).
Comprueba que hay 21:

```sql
SELECT COUNT(*) FROM information_schema.ROUTINES
 WHERE ROUTINE_SCHEMA='vehiculo_iot' AND ROUTINE_TYPE='PROCEDURE';
```

En el Security Group de RDS, permite el puerto 3306 desde **My IP** (si cambia tu IP, actualízala).

## 2. Instalar y ejecutar (Windows / PowerShell, desde la raíz)

```powershell
python -m venv .venv            # solo si aún no existe
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # y edita .env (ver abajo)
uvicorn app.main:app --reload --port 8000
```

- Swagger: http://localhost:8000/docs  ·  Salud: http://localhost:8000/health

**`.env`** (en la raíz, junto a `app/`; sin espacios alrededor del `=` ni comillas):

| Variable | Qué poner |
|---|---|
| `DB_HOST` | Endpoint de RDS (consola AWS → RDS → tu instancia → *Endpoint*) |
| `DB_USER` / `DB_PASSWORD` | Usuario y contraseña de RDS |
| `API_KEY_ADMIN` / `API_KEY_CONTROL` | Claves que inventes: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |

Si falla: `/health` con **503** → revisa Security Group, endpoint y credenciales (el motivo exacto sale en la
consola de uvicorn). Si `pip` falla con Python 3.14, actualiza pip o usa Python 3.12/3.13.

## 3. Autorización

Las consultas (GET) son públicas y **nunca modifican datos**. Lo demás exige la cabecera `X-API-Key`
(botón **Authorize** en Swagger):

| Clave | Permite |
|---|---|
| `control` | POST de movimiento, iniciar y cancelar DEMO |
| `admin` | Todo lo anterior + crear, actualizar y eliminar vehículos, comandos, demos y sus movimientos |

Sin clave → **401**. Clave `control` en una operación admin → **403**. Si el servidor no tiene claves
configuradas, las operaciones protegidas se rechazan (503).

## 4. Endpoints y Stored Procedures

GET = consultas; POST = escrituras, actualizaciones y acciones.

| Endpoint | Auth | SP |
|---|---|---|
| `GET /vehiculos` · `GET /vehiculos/{id}` | — | `sp_obtener_vehiculos`, `sp_obtener_vehiculo` (+ comandos, estado y demos) |
| `POST /vehiculos` | admin | `sp_crear_vehiculo` |
| `POST /vehiculos/{id}/actualizar` | admin | `sp_actualizar_vehiculo` |
| `POST /vehiculos/{id}/eliminar` | admin | `sp_eliminar_vehiculo` |
| `GET /vehiculos/{id}/comandos` | — | `sp_obtener_comandos_vehiculo` |
| `POST /vehiculos/{id}/comandos` | admin | `sp_crear_comando` |
| `POST /vehiculos/{id}/comandos/{id_comando}/actualizar` | admin | `sp_actualizar_comando` |
| `POST /vehiculos/{id}/comandos/{id_comando}/eliminar` | admin | `sp_eliminar_comando` |
| `GET /vehiculos/{id}/estado` | — | `sp_obtener_estado` |
| **`POST /vehiculos/{id}/movimientos`** | control | `sp_actualizar_estado` + `sp_registrar_historial` (una transacción) |
| `GET /vehiculos/{id}/historial` | — | `sp_obtener_historial` (máx. 10) |
| `GET /vehiculos/{id}/demos` | — | `sp_obtener_demos` |
| `POST /vehiculos/{id}/demos` | admin | `sp_crear_demo` |
| `POST /vehiculos/{id}/demos/{id_demo}/actualizar` | admin | `sp_actualizar_demo` |
| `POST /vehiculos/{id}/demos/{id_demo}/eliminar` | admin | `sp_eliminar_demo` |
| `GET /vehiculos/{id}/demos/{id_demo}/movimientos` | — | `sp_obtener_movimientos_demo` |
| `POST /vehiculos/{id}/demos/{id_demo}/movimientos` | admin | `sp_agregar_movimiento_demo` |
| `POST .../movimientos/{id_mov}/actualizar` | admin | `sp_actualizar_movimiento_demo` |
| `POST .../movimientos/{id_mov}/eliminar` | admin | `sp_eliminar_movimiento_demo` |
| **`POST /vehiculos/{id}/demos/{id_demo}/iniciar`** | control | lectura + `sp_actualizar_estado` por movimiento (nunca historial) |
| `POST /vehiculos/{id}/demos/cancelar` | control | `sp_actualizar_estado` (DETENER, si existe) |

### Movimiento individual

`POST /vehiculos/1/movimientos` con `{"id_comando": 3, "origen": "API"}`. Valida que el vehículo exista y esté
activo y que el comando exista, esté activo y **sea de ese vehículo**. Actualiza estado e historial en **una
transacción**, y solo después del COMMIT notifica por WebSocket. Si se rechaza, no cambia nada ni se emite
evento. `conectado` se conserva (nunca se asume `true`). Ejecutar un movimiento ≠ crear un comando.

### Historial

Devuelve como máximo los 10 movimientos individuales más recientes (más reciente primero). Si hay menos, solo
esos. RDS conserva todo. Vehículo inexistente → 404; existente sin movimientos → 200 con lista vacía.

### DEMO

`iniciar` responde **202** y la secuencia se emite en segundo plano: N movimientos leídos de RDS, respetando
`duracion_ms` y `pausa_ms`. Una sola DEMO por vehículo (si no, 409). `cancelar` corta de inmediato; si el
catálogo tiene un comando `DETENER`, queda como último comando. Las DEMO **no escriben en el historial**.
Emitir un mensaje no confirma ejecución física (el microcontrolador se integra en otra práctica).

## 5. WebSocket

`ws://localhost:8000/ws/vehiculos/{id_vehiculo}` — varios clientes por vehículo; cada uno recibe solo los
eventos de su vehículo. Al conectar llega el último estado. Enviar el texto `ping` responde `pong`. Vehículo
inexistente → mensaje `error` y cierre con código 4404.

Todos los mensajes llevan `tipo`, `id_vehiculo`, `comando`, `codigo` y `marca_temporal` (UTC ISO-8601):

| `tipo` | Cuándo | Campos extra |
|---|---|---|
| `estado_inicial` | al conectar | `conectado`, `fecha_actualizacion` |
| `movimiento` | tras un POST de movimiento confirmado | `id_comando`, `origen` |
| `demo_inicio` | arranca la DEMO | `id_demo`, `demo`, `total_movimientos` |
| `demo_movimiento` | uno por cada movimiento | `orden`, `duracion_ms`, `pausa_ms` (+ campos de demo) |
| `demo_fin` | termina normalmente | |
| `demo_cancelada` | se canceló | `accion` (`"DETENER"` o `null`) |
| `demo_error` | falló RDS u otro error | `mensaje`, `accion` |
| `error`, `pong` | errores de conexión / respuesta a ping | |

## 6. Las 3 pruebas de Thunder Client

Agrega en cada petición protegida la cabecera `Xws://44.196.22.143:8000/ws/vehiculos/1-API-Key: <tu clave control>`.

1. **POST** `http://localhost:8000/vehiculos/1/movimientos` · `{"id_comando": 3}` → 201. Luego `GET .../estado`
   y `GET .../historial` muestran el cambio.
2. **GET** `http://localhost:8000/vehiculos/1/historial` → máximo 10, del más reciente al más antiguo.
3. **WebSocket** `ws://localhost:8000/ws/vehiculos/1` → conectar; en otra pestaña
   `POST /vehiculos/1/demos/1/iniciar`. Verás `demo_inicio`, los N `demo_movimiento` y `demo_fin`. Compara
   `GET .../historial` antes y después: no cambia. (Para tener movimientos, agrégalos antes con
   `POST /vehiculos/1/demos/1/movimientos` usando la clave admin.)

## 7. Pruebas automáticas

```powershell
pip install -r requirements-dev.txt
pytest -q
```
Usan un RDS simulado en memoria (no tocan tu base) y verifican, entre otras cosas, que los 21 SP están integrados.

## 8. GitHub

```powershell
git init
git add .
git status        # comprueba que .env y .venv NO aparecen
git commit -m "API vehículos IoT: FastAPI, RDS (21 SP) y WebSocket"
git branch -M main
git remote add origin https://github.com/<usuario>/<repositorio>.git
git push -u origin main
```

## 9. Para la práctica 2.6 (nube)

El código no cambia: solo el `.env` del servidor, el Security Group de RDS (permitir el de EC2 en vez de tu
IP), HTTPS/WSS y, si hay un frontend en otro dominio, CORS.
