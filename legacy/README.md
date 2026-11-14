# Código histórico

Esta carpeta conserva la versión anterior basada en `/status` y un WebSocket global.
No es utilizada por `app.main` ni por la arquitectura actual con vehículos, RDS y
procedimientos almacenados. No mezcles sus endpoints con los de la API vigente.

Si necesitas ejecutarla para consultar la práctica anterior, usa:

```bash
uvicorn legacy.main:app --port 8001
```
