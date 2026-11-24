# Plan incremental de perfiles

## M001 — entregado en este paquete
- Tablas nuevas de identidad, roles y sesiones refresh.
- Registro exclusivamente de invitado.
- Login, access token corto, refresh rotatorio, logout y `/auth/me`.
- Alta inicial de administrador por script interactivo.
- No modifica las seis tablas IoT existentes.

## M002 — siguiente etapa
- Integrar autenticación Bearer en las rutas REST actuales.
- Aplicar autorización por recurso y asignación.
- Provisionar cuentas `user` desde Administración.
- Sustituir dependencias heredadas de API key.
- Pruebas cruzadas User A / User B y Admin sin autorización de soporte.

## M003
- Autenticación de ESP8266 por credencial individual de dispositivo.
- Autorización WSS por unidad, revocación y aislamiento de eventos.
- `event_id`, ACK de dispositivo y estados solicitados/aceptados/reportados.

## M004
- Login/registro visual del frontend, navegación por perfil y catálogo público.

## M005+
- Modelos, unidades, clientes, asignaciones, soporte consentido, editor de DEMOS,
  sesiones invitado/reserva exclusiva, auditoría y regresión completa.

No desplegar M001 como solución completa de seguridad: las rutas IoT heredadas
aún requieren autorización por propietario y el WebSocket aún requiere autenticación.
