# Excavadora IoT — API FastAPI, Amazon RDS MySQL y WebSocket

Backend para controlar vehículos IoT. La API está construida con FastAPI; los datos persistentes
se almacenan en Amazon RDS MySQL y la comunicación en tiempo real se realiza por WebSocket.
El ESP8266 se conecta como cliente WebSocket y ejecuta los eventos recibidos mediante el firmware
y los registros 74HC595.

## Arquitectura y alcance real

```text
Panel / cliente HTTP
        | POST /vehiculos/{id}/movimientos
        v
FastAPI (EC2) ---- Stored Procedures ---- Amazon RDS MySQL
        |
        | evento WebSocket por vehículo
        v
ESP8266 (cliente WS) ---- 74HC595 ---- motores y salidas
```

- La API utiliza 21 Stored Procedures permitidos explícitamente.
- Los movimientos individuales actualizan estado e historial en una transacción.
- Las DEMO actualizan el último estado, pero no escriben en el historial individual.
- El WebSocket distribuye eventos a los clientes conectados al mismo ID de vehículo.
- El backend no confirma que el movimiento físico haya ocurrido: enviar el evento no equivale
  a recibir confirmación de ejecución del microcontrolador.
- Este ZIP contiene el backend, no el firmware ESP8266 ni el código del panel. Tampoco implementa
  AWS IoT Core/MQTT: la comunicación contemplada aquí es WebSocket directo.

## Estructura

```text
Websocket_IoT/
├── .env.example
├── requirements.txt
├── requirements-dev.txt
├── script/                 # volcados SQL y Stored Procedures
├── legacy/                 # versión anterior archivada; no se usa en la API actual
├── tests/                  # pruebas con RDS simulado en memoria
└── app/
    ├── main.py             # FastAPI, ciclo de vida y /health
    ├── core/               # configuración, pool, seguridad y ejecución de SP
    ├── models/             # validación y esquemas Pydantic
    ├── repositories/       # acceso a Stored Procedures
    ├── services/           # reglas de negocio y ejecución de DEMO
    ├── routers/            # endpoints HTTP
    └── websocket/          # eventos, conexiones y endpoint WS
```

## 1. Base de datos Amazon RDS

La aplicación espera una base MySQL llamada `vehiculo_iot` con las tablas y relaciones usadas por
los procedimientos almacenados. Los archivos `vehiculo_iot_vehiculos.sql`, `vehiculo_iot_comandos.sql`,
`vehiculo_iot_demos.sql`, `vehiculo_iot_demo_movimientos.sql`, `vehiculo_iot_estado_vehiculo.sql` y
`vehiculo_iot_historial_comandos.sql` son volcados de tablas con `DROP TABLE` e inserciones de ejemplo.

**No ejecutes esos volcados sobre una RDS que ya contiene datos:** pueden borrar tablas y reemplazar
registros. Consérvalos como referencia o úsalos únicamente para reconstruir una base de pruebas vacía,
revisando antes el orden de creación y las relaciones.

### Stored Procedures

1. `vehiculo_iot_routines.sql` contiene 19 procedimientos.
2. `vehiculo_iot_routines_faltantes.sql` contiene los otros 2: `sp_actualizar_demo` y
   `sp_agregar_movimiento_demo`.
3. En conjunto deben existir 21 procedimientos.

Los scripts eliminan y recrean las rutinas con esos nombres. Ejecútalos en la base `vehiculo_iot`
con un usuario autorizado para crear y eliminar procedimientos. Los procedimientos se crean con el
usuario que ejecuta el script; no dependen de un `DEFINER=admin@localhost`.

Verifica el total después de instalarlos:

```sql
SELECT COUNT(*)
FROM information_schema.ROUTINES
WHERE ROUTINE_SCHEMA = 'vehiculo_iot'
  AND ROUTINE_TYPE = 'PROCEDURE';
```

El resultado esperado es `21`.

### Red de AWS

- Si FastAPI corre en EC2, permite el puerto TCP `3306` en el Security Group de RDS **solo desde
  el Security Group de esa EC2**.
- No abras MySQL a `0.0.0.0/0`. Si haces una prueba desde tu computadora, permite temporalmente
  tu IP pública y retírala al terminar.
- Mantén las credenciales fuera del repositorio. En EC2 puedes inyectarlas como variables de entorno
  o desde un gestor de secretos; la aplicación también lee un `.env` local.

## 2. Configuración local

Desde la raíz del proyecto, en PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edita `.env` con el endpoint, usuario y contraseña de tu RDS y genera dos claves distintas:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Coloca una clave en `API_KEY_ADMIN` y otra en `API_KEY_CONTROL`. No reutilices las claves de ejemplo.

Para ejecutar localmente:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Swagger: `http://localhost:8000/docs`
- Salud: `http://localhost:8000/health`
- WebSocket local: `ws://localhost:8000/ws/vehiculos/1`

En EC2 ejecuta sin `--reload`. La configuración actual de tu dispositivo utiliza `ws://` en el puerto
`8000`; el firmware debe apuntar a la IP pública o DNS vigente de EC2 y al mismo `id_vehiculo`.

## 3. Autorización HTTP

Las consultas GET son públicas y no modifican datos. Las operaciones POST protegidas usan la cabecera
`X-API-Key`:

| Rol | Permisos |
|---|---|
| `control` | Ejecutar movimientos e iniciar/cancelar DEMO |
| `admin` | Todo lo anterior y administrar vehículos, comandos, demos y movimientos de demo |

Sin clave: `401`. Clave control en una operación admin: `403`. Si no hay ninguna clave configurada:
`503`.

**Importante:** el endpoint WebSocket actual no exige API key ni distingue entre el ESP8266 y otros
clientes conectados al mismo vehículo. Cualquier cliente que conozca la ruta puede suscribirse.
La conexión `ws://` tampoco cifra el tráfico. Se conserva ese protocolo porque es el configurado
actualmente en el firmware; este punto debe considerarse al exponer el puerto en AWS.

## 4. Endpoints principales

| Endpoint | Autorización | Función |
|---|---|---|
| `GET /vehiculos` | Pública | Lista vehículos; `incluir_detalle=false` omite comandos, estado y demos |
| `GET /vehiculos/{id}` | Pública | Consulta un vehículo con su detalle |
| `POST /vehiculos` | admin | Crea vehículo |
| `POST /vehiculos/{id}/actualizar` | admin | Actualiza vehículo |
| `POST /vehiculos/{id}/eliminar` | admin | Elimina vehículo y datos dependientes en cascada |
| `GET /vehiculos/{id}/comandos` | Pública | Lista el catálogo del vehículo |
| `POST /vehiculos/{id}/comandos` | admin | Crea un comando; no lo ejecuta |
| `POST /vehiculos/{id}/comandos/{id_comando}/actualizar` | admin | Actualiza comando |
| `POST /vehiculos/{id}/comandos/{id_comando}/eliminar` | admin | Elimina comando si no está usado por una DEMO |
| `GET /vehiculos/{id}/estado` | Pública | Consulta el último estado |
| `POST /vehiculos/{id}/movimientos` | control | Ejecuta un comando ya existente |
| `GET /vehiculos/{id}/historial` | Pública | Devuelve hasta 10 movimientos individuales |
| `GET /vehiculos/{id}/demos` | Pública | Lista DEMO |
| `POST /vehiculos/{id}/demos` | admin | Crea DEMO |
| `POST /vehiculos/{id}/demos/{id_demo}/actualizar` | admin | Actualiza DEMO |
| `POST /vehiculos/{id}/demos/{id_demo}/eliminar` | admin | Elimina DEMO |
| `GET /vehiculos/{id}/demos/{id_demo}/movimientos` | Pública | Consulta la secuencia |
| `POST /vehiculos/{id}/demos/{id_demo}/movimientos` | admin | Agrega paso a la secuencia |
| `POST .../movimientos/{id_mov}/actualizar` | admin | Actualiza paso |
| `POST .../movimientos/{id_mov}/eliminar` | admin | Elimina paso |
| `POST /vehiculos/{id}/demos/{id_demo}/iniciar` | control | Inicia ejecución en segundo plano; responde 202 |
| `POST /vehiculos/{id}/demos/cancelar` | control | Cancela la DEMO activa del vehículo |

## 5. Movimiento individual

Ejemplo de cuerpo:

```json
{
  "id_comando": 12,
  "origen": "API"
}
```

El `id_comando` es el identificador real que devuelve `GET /vehiculos/{id}/comandos`; no asumas que
será `1`, `2` o `3`. Los IDs de la RDS real, los volcados SQL y el RDS simulado de las pruebas no son
intercambiables. Si el catálogo no contiene el comando que necesitas, créalo primero con la clave admin.

La API valida que el vehículo esté activo y que el comando exista, esté activo y pertenezca a ese
vehículo. Después actualiza estado e historial dentro de una transacción. Solo tras el COMMIT emite
el evento WebSocket. Si la validación falla, no cambia datos ni emite eventos.

El campo `conectado` se conserva al ejecutar movimientos; una petición HTTP no demuestra que el
microcontrolador esté conectado. Actualmente el backend no actualiza ese campo al conectar o desconectar
el ESP8266: requiere una señal de presencia identificada del dispositivo.

## 6. DEMO

`POST /vehiculos/{id}/demos/{id_demo}/iniciar` responde `202`. La secuencia se emite en segundo plano
por `/ws/vehiculos/{id}` y respeta `duracion_ms` y `pausa_ms`. El backend permite una DEMO simultánea
por vehículo **dentro de un único proceso de la API**. Las DEMO no escriben en el historial individual.

Si el catálogo contiene un comando `DETENER`, se utiliza al cancelar o fallar una DEMO. El ESP8266
recibe los eventos `demo_movimiento`, `demo_cancelada` o `demo_error`; la ejecución física depende
del firmware y de que el dispositivo esté conectado.

## 7. WebSocket y despliegue

Ruta: `/ws/vehiculos/{id_vehiculo}`. El servidor envía el estado inicial y después los eventos de ese
vehículo. El ESP8266 actual debe conectarse como cliente a `ws://<HOST_EC2>:8000/ws/vehiculos/1`.

**Límite de escalabilidad actual:** `WebSocketManager` y `DemoRunner` mantienen sus conexiones y ejecuciones
en memoria del proceso. Por eso, la configuración actual debe ejecutarse con **una sola instancia EC2
y un solo worker Uvicorn**. Con varios workers o varias instancias, un POST puede llegar a un proceso
distinto del que mantiene conectado al ESP8266 y el evento no se distribuirá entre procesos. Para
escalar después hará falta coordinación compartida (por ejemplo, un broker/pub-sub) y un bloqueo
distribuido para las DEMO.

Si el panel web está alojado en otro origen, esta versión todavía no configura CORS: habrá que añadir
los orígenes exactos del panel antes de consumir la API desde el navegador.

## 8. Pruebas

```powershell
pip install -r requirements-dev.txt
pytest -q
```

Las pruebas usan `FakeRDS`, un simulador en memoria. Verifican reglas de negocio, respuestas HTTP,
WebSocket y que los 21 nombres de SP estén integrados en la API. **No se conectan a Amazon RDS ni
validan la sintaxis o permisos de las rutinas instaladas en AWS.** Después de desplegar, prueba también
`/health`, las consultas y un movimiento controlado contra la RDS real.

## 9. Prueba desde Thunder Client

1. Consulta `GET http://<HOST_EC2>:8000/vehiculos/1/comandos` y localiza el `id_comando` del movimiento
   que deseas probar.
2. Envía `POST http://<HOST_EC2>:8000/vehiculos/1/movimientos` con `X-API-Key: <CLAVE_CONTROL>` y el
   JSON `{"id_comando": <ID_REAL>, "origen": "API"}`.
3. Conecta un cliente WebSocket a `ws://<HOST_EC2>:8000/ws/vehiculos/1` antes de enviar el POST para
   observar el evento `movimiento`.

No pegues la URL WebSocket dentro de la cabecera HTTP: `X-API-Key` es una cabecera independiente.

## 10. Git

Antes de subir el proyecto, comprueba que `.env` no esté incluido. El archivo `.env.example` sí puede
subirse porque contiene únicamente valores de ejemplo.


---

## Autenticación M001 (incremental)

Se añadió una primera base de identidad con perfiles `admin`, `user` y `guest`.
Consulta `docs/AUTHENTICATION_M001.md` antes de configurar o aplicar la migración.

**Advertencia:** esta entrega incorpora registro de invitado, login, refresh rotatorio,
logout y consulta `/auth/me`; todavía no integra autorización por propietario en
todos los endpoints IoT ni autenticación del ESP8266 en WSS. No desplegar para
operación real de vehículos hasta completar esas etapas.
