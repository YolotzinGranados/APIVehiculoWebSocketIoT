"""Excepciones de la aplicación. Cada una se traduce a un código HTTP concreto."""


class AppError(Exception):
    status_code = 500
    codigo = "ERROR_INTERNO"

    def __init__(self, mensaje: str = "Error interno del servidor"):
        super().__init__(mensaje)
        self.mensaje = mensaje


class BadRequestError(AppError):
    status_code = 400
    codigo = "SOLICITUD_INVALIDA"


class UnauthorizedError(AppError):
    status_code = 401
    codigo = "NO_AUTENTICADO"


class ForbiddenError(AppError):
    status_code = 403
    codigo = "SIN_PERMISO"


class NotFoundError(AppError):
    status_code = 404
    codigo = "NO_ENCONTRADO"


class ConflictError(AppError):
    status_code = 409
    codigo = "CONFLICTO"


class DatabaseError(AppError):
    status_code = 500
    codigo = "ERROR_BASE_DATOS"


class ServiceUnavailableError(AppError):
    status_code = 503
    codigo = "SERVICIO_NO_DISPONIBLE"
