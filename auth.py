"""
auth.py — Autenticação HTTP Basic Auth para o Dashboard AWR Capital.

Em PRODUÇÃO (Hugging Face):
    - Defina um Secret chamado DASHBOARD_USERS no Space
    - Formato: user1:senha1,user2:senha2
    - Ex: awr:SenhaForte123

Em DESENVOLVIMENTO LOCAL:
    - Crie um .env na pasta do projeto com:
      DASHBOARD_USERS=admin:admin
    - Instale: pip install python-dotenv

Uso no app.py:
    from auth import proteger_servidor
    server = app.server
    proteger_servidor(server)
"""

import os
from pathlib import Path
from flask import request, Response

# Carrega .env local se existir (só em desenvolvimento)
try:
    from dotenv import load_dotenv
    _env = Path(__file__).resolve().parent / ".env"
    if _env.exists():
        load_dotenv(_env)
        print("[Auth] .env carregado.")
except ImportError:
    pass  # Em produção não precisa — HF já expõe Secrets como env vars


def _carregar_usuarios() -> dict:
    raw = os.environ.get("DASHBOARD_USERS", "")
    if not raw:
        print("[Auth][AVISO] DASHBOARD_USERS não definido. Usando admin/admin (só local).")
        return {"admin": "admin"}

    usuarios = {}
    for par in raw.split(","):
        par = par.strip()
        if ":" not in par:
            continue
        user, _, senha = par.partition(":")
        user, senha = user.strip(), senha.strip()
        if user and senha:
            usuarios[user] = senha

    if not usuarios:
        print("[Auth][ERRO] DASHBOARD_USERS inválido. Usando admin/admin.")
        return {"admin": "admin"}

    print(f"[Auth] {len(usuarios)} usuário(s) configurado(s).")
    return usuarios


def _checar(username: str, password: str) -> bool:
    usuarios = _carregar_usuarios()
    return usuarios.get(username) == password


def _pedir_login():
    return Response(
        "Acesso restrito. Faça login para continuar.\n",
        401,
        {"WWW-Authenticate": 'Basic realm="AWR Capital Dashboard"'},
    )


def proteger_servidor(server) -> None:
    """Aplica autenticação a TODAS as rotas do servidor Flask."""

    @server.before_request
    def _verificar():
        auth = request.authorization
        if not auth or not _checar(auth.username, auth.password):
            return _pedir_login()

    print("[Auth] Servidor AWR protegido por HTTP Basic Auth.")
