"""
Schema do corpo de erro padrão retornado pelo Gateway.
Formato:
    {
        "status": 400,
        "error": "INVALID_ARGUMENT",
        "message": "descrição legível"
    }
"""
from pydantic import BaseModel

class ErrorResponse(BaseModel):
    status: int
    error: str
    message: str