"""
DTOs de autenticação.
Rotas: POST /auth/register, POST /auth/login
Resposta: jwt + user_id 
"""

from pydantic import BaseModel


class RegisterRequest(BaseModel):
    name: str
    password: str


class LoginRequest(BaseModel):
    name: str
    password: str


class AuthResponse(BaseModel):
    jwt: str
    user_id: str