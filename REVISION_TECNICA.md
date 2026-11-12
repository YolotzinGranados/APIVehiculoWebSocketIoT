# Revisión técnica del proyecto Websocket_IoT

## Cambios aplicados en esta copia

- Corregido el arranque de FastAPI: se retiraron las referencias a `dashboard_router` y `STATIC_DIR`,
  ausentes en el paquete.
- Retirada la autenticación de sesión/cookie del dashboard, que no tenía endpoint de login ni frontend
  dentro del ZIP y requería `DASHBOARD_SESSION_SECRET`. Se conserva la autenticación HTTP por API key.
- Añadido `.env.example` sin credenciales reales.
- Corregida la dependencia de desarrollo `httpx2` a `httpx`.
- Retirados los `DEFINER=admin@localhost` de los 19 Stored Procedures para que la instalación no dependa
  de una cuenta local específica; los otros dos procedimientos ya se creaban sin DEFINER.
- Corregidas las referencias WebSocket de localhost en la documentación de la API.
- Reescrito el README para describir la arquitectura EC2 + RDS + ESP8266, el uso de WS y las limitaciones
  actuales sin afirmar que el envío WebSocket confirma el movimiento físico.
- Aclarado que los IDs del RDS simulado de pruebas no representan los IDs de la base real.
- Limpiada la versión histórica `legacy/main.py`, corregida la ruta de su JSON y retirada una copia vacía
  redundante del archivo de estado.
- Eliminados `app/routers.zip`, `__pycache__`, `.pyc` y metadatos `.git` de la copia distribuible.

## Hallazgos que siguen requiriendo una decisión o integración

1. **Presencia ESP8266 (`conectado`)**: la API no actualiza este campo al abrir/cerrar el WebSocket. El
   endpoint es compartido por todos los clientes y no distingue ESP8266 del panel. No se debe marcar
   `conectado=true` por cualquier conexión, porque también podría ser un navegador. Hace falta identificar
   de forma fiable al dispositivo antes de cambiar esta lógica.
2. **Autenticación WebSocket**: el endpoint no exige token y permite suscribirse conociendo el ID del
   vehículo. La API key solo protege endpoints HTTP.
3. **Escalado**: el gestor WS y el registro de DEMO son locales al proceso. La ejecución requiere una
   instancia y un worker hasta que se implemente pub/sub y bloqueo distribuido.
4. **CORS**: no existe configuración para un panel web en otro dominio. Se necesita conocer el origen
   exacto del panel para configurarlo de forma restrictiva.
5. **Historial**: el SP obtiene todo el historial y `HistorialService` recorta a 10. La respuesta cumple
   el contrato, pero con historiales grandes se transfiere más información desde RDS de la necesaria.
   Puede optimizarse haciendo que el SP devuelva los 10 más recientes y ajustando el contrato de pruebas.
6. **Firmware y `codigo`**: el backend emite `codigo` como entero y `comando` como texto. El firmware
   archivado en el contexto del proyecto intenta leer `codigo` como `const char*`; la conversión de un
   número JSON a texto no es válida. Actualmente puede continuar por el fallback a `comando`, cuyos
   alias (`GIRAR_DERECHA`, `SUBIR_BRAZO`, `BAJAR_BRAZO`, etc.) sí están contemplados. Conviene que el
   firmware use `comando` explícitamente o convierta el código numérico de forma intencional.
7. **Datos de ejemplo**: los volcados SQL y `FakeRDS` tienen vehículos/comandos con IDs distintos.
   No se deben codificar IDs fijos en el firmware ni en ejemplos: se consultan desde la API.
8. **Pruebas de integración**: la suite simula los SP; no ejecuta SQL contra una instancia MySQL real.
   La instalación de las 21 rutinas y sus permisos deben verificarse en RDS.
9. **Conexión a RDS**: el pool es síncrono y su tamaño se multiplica por worker e instancia. Mantener
   un solo worker coincide con la limitación actual del WebSocket; si se escala, recalcular `DB_POOL_SIZE`
   respecto de `max_connections` de RDS.

## Verificación realizada sobre esta copia

- `python -m compileall -q app legacy tests`: correcto.
- `pytest -q`: **31 pruebas aprobadas** contra `FakeRDS` (base simulada en memoria). El entorno de
  revisión no tenía instalado `mysql-connector-python`, por lo que se utilizó un stub únicamente para
  importar la capa de conexión; las pruebas no abrieron conexiones ni modificaron AWS RDS.
- Comparación de nombres: los 21 procedimientos de `ALLOWED_PROCEDURES` coinciden exactamente con
  los 19 de `vehiculo_iot_routines.sql` más los 2 de `vehiculo_iot_routines_faltantes.sql`.
- El ZIP de entrega no incluye `.env`, `.venv`, `.git`, bytecode ni el archivo duplicado `routers.zip`.

## Recomendación de validación tras actualizar EC2/RDS

1. Respaldar la base antes de reemplazar procedimientos.
2. Ejecutar los dos scripts de rutinas en `vehiculo_iot` y comprobar que existen 21 SP.
3. Instalar dependencias y ejecutar `pytest -q`.
4. Arrancar FastAPI con un solo worker y comprobar `/health`.
5. Consultar `GET /vehiculos/1/comandos` y confirmar que los nombres corresponden al firmware.
6. Conectar el ESP8266 por `ws://` y hacer una prueba con el vehículo levantado/asegurado, comenzando
   por un comando de baja consecuencia.
