# M001 — Base de autenticación FastAPI

## Alcance
- Perfiles fijos: `admin`, `user`, `guest`.
- Registro público únicamente para `guest`.
- Login con correo y contraseña.
- Access token Bearer de corta duración (JWT HS256).
- Refresh token aleatorio en cookie HttpOnly/Secure/SameSite=None, persistido como SHA-256.
- Rotación de refresh token y revocación al cerrar sesión.
- CSRF double-submit para refresh/logout.
- `/auth/me` vuelve a leer roles desde MySQL; no confía en roles del token.

## Migración
1. Respaldar RDS y probar restauración en staging.
2. Verificar que no existan tablas `auth_*` con otros propósitos.
3. Ejecutar `script/migrations/001_authentication_up.sql` con un usuario MySQL limitado a CREATE/ALTER/INDEX/INSERT en el esquema de autenticación.
4. Verificar las cuatro tablas y tres roles.
5. No ejecutar DOWN en producción. DOWN es solo para staging/pruebas y elimina únicamente las cuatro tablas nuevas.

## Variables nuevas
- `AUTH_SECRET_KEY`: secreto aleatorio de al menos 32 caracteres.
- `AUTH_ACCESS_TTL_MINUTES`: 10 por defecto.
- `AUTH_REFRESH_TTL_DAYS`: 14 por defecto.

Generar secreto con:
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Endpoints
- `POST /auth/registro-invitado` — crea únicamente rol guest.
- `POST /auth/login` — credenciales y cookies de renovación.
- `POST /auth/refresh` — rota refresh token; requiere X-CSRF-Token.
- `POST /auth/logout` — revoca refresh token.
- `GET /auth/me` — devuelve identidad y roles vigentes.

## Importante: integración pendiente
M001 no habilita todavía el control seguro de vehículos. Los routers IoT existentes aún no están protegidos por propiedad/asignación y el WebSocket del ESP8266 aún no autentica dispositivo. No publicar M001 como solución completa de seguridad ni permitir invitados a operar hasta completar las siguientes etapas de autorización REST/WSS y reservas.

## Restricción de despliegue
El frontend actual en GitHub Pages y API en IP/host diferente operan cross-site. Cookies SameSite=None requieren HTTPS y pueden ser bloqueadas por políticas de cookies de terceros. Para producción se recomienda frontend y API bajo un mismo dominio registrable mediante reverse proxy o subdominios same-site, y CORS con credenciales limitado a orígenes explícitos.

## Variables de entorno (ejemplo)
```dotenv
AUTH_SECRET_KEY=REEMPLAZAR_POR_UN_SECRETO_ALEATORIO_DE_48_BYTES
AUTH_ACCESS_TTL_MINUTES=10
AUTH_REFRESH_TTL_DAYS=14
```

Las cookies se llaman `iot_refresh` y `iot_csrf`; el refresh se marca HttpOnly.

## Alta inicial de administrador
Después de aplicar M001 y configurar las variables, ejecutar desde la raíz del backend:
```bash
python -m scripts.create_admin
```
El script solicita correo, nombre y contraseña de forma interactiva. Solo permite crear el primer administrador; las altas posteriores deberán realizarse mediante el módulo administrativo autenticado que se implementará en una etapa posterior.

## Limitaciones deliberadas de M001
- El registro público crea exclusivamente `guest`; no permite que alguien se autoproclame `admin` o `user`.
- La dirección de correo se valida sintácticamente, pero aún no se verifica por correo electrónico.
- No se incluye todavía recuperación de contraseña ni verificación de correo.
- No se aplican aún permisos por propiedad a las rutas IoT existentes.
- No se protege todavía el canal WSS del ESP8266.
- No se entrega aún la pantalla de login del frontend.
