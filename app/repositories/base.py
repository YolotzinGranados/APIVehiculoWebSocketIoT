from app.core.stored_procedures import StoredProcedureExecutor


class BaseRepository:
    """Los repositorios solo llaman SP; no contienen reglas de negocio."""

    def __init__(self, executor: StoredProcedureExecutor):
        self._sp = executor
