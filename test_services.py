"""
Script de teste de integração — TriviaArena
Valida todos os endpoints REST do API Gateway.
O START GAME é testado via REST (retorna imediatamente).
O fluxo WebSocket (perguntas, respostas, placar) só é validável pelo Frontend.
"""

import json
import os
import time
import uuid

import requests

BASE_URL = "http://localhost:8000"
OUTPUT_DIR = "response_test"
os.makedirs(OUTPUT_DIR, exist_ok=True)

username = f"alice_{uuid.uuid4().hex[:6]}"
print(f"{'='*55}")
print(f"Usuário de teste: {username}")
print(f"{'='*55}\n")

passed = 0
failed = 0


def save(filename, data):
    with open(os.path.join(OUTPUT_DIR, filename), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def check(label, resp, expected_status):
    global passed, failed
    ok = resp.status_code == expected_status
    icon = "✓" if ok else "✗ "
    if ok:
        passed += 1
    else:
        failed += 1
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text[:200]}
    print(f"{icon} {label} [{resp.status_code}]: {json.dumps(body, ensure_ascii=False)[:120]}")
    return body


# ── 1. Register ───────────────────────────────────────────────────────────────
resp = requests.post(f"{BASE_URL}/auth/register", json={
    "name": username, "password": "senha123"
})
data = check("REGISTER", resp, 201)
save("register.json", data)
user_id = data.get("user_id")
jwt_token = data.get("jwt")

# ── 2. Register duplicado ─────────────────────────────────────────────────────
resp = requests.post(f"{BASE_URL}/auth/register", json={
    "name": username, "password": "senha123"
})
check("REGISTER DUPLICADO (esperado 409)", resp, 409)

# ── 3. Login ──────────────────────────────────────────────────────────────────
resp = requests.post(f"{BASE_URL}/auth/login", json={
    "name": username, "password": "senha123"
})
data = check("LOGIN", resp, 200)
save("login.json", data)
jwt_token = data.get("jwt", jwt_token)

# ── 4. Login senha errada ─────────────────────────────────────────────────────
resp = requests.post(f"{BASE_URL}/auth/login", json={
    "name": username, "password": "errada"
})
check("LOGIN SENHA ERRADA (esperado 401)", resp, 401)

headers = {"Authorization": f"Bearer {jwt_token}"}

# ── 5. Stats ──────────────────────────────────────────────────────────────────
resp = requests.get(f"{BASE_URL}/users/me/stats", headers=headers)
data = check("STATS", resp, 200)
save("stats.json", data)

# ── 6. Update user ────────────────────────────────────────────────────────────
new_name = f"alice_{uuid.uuid4().hex[:6]}"
resp = requests.put(f"{BASE_URL}/users/me", json={"name": new_name}, headers=headers)
if resp.status_code == 204:
    print(f"✓ UPDATE USER [204]: sem corpo (atualizado com sucesso)")
    passed += 1
else:
    check("UPDATE USER", resp, 200)

# ── 7. Criar sala ─────────────────────────────────────────────────────────────
resp = requests.post(f"{BASE_URL}/rooms", json={
    "creator_id": user_id,
    "creator_name": new_name,
    "is_anonymous": False,
    "max_players": 2,
    "num_questions": 5,
    "theme": "science"
}, headers=headers)
data = check("CREATE ROOM", resp, 201)
save("room.json", data)
room_code = data.get("room_code")

# ── 8. Consultar sala ─────────────────────────────────────────────────────────
if room_code:
    resp = requests.get(f"{BASE_URL}/rooms/{room_code}", headers=headers)
    data = check("GET ROOM", resp, 200)
    save("room_state.json", data)

# ── 9. Join com jogador anônimo ───────────────────────────────────────────────
anon_id = None
if room_code:
    anon_id = f"anon:{uuid.uuid4()}"
    resp = requests.post(f"{BASE_URL}/rooms/{room_code}/join", json={
        "player_id": anon_id,
        "player_name": "bruno",
        "is_anonymous": True
    })
    data = check("JOIN ROOM", resp, 200)
    save("join.json", data)

# ── 10. Iniciar partida ───────────────────────────────────────────────────────
# Retorna imediatamente via REST — o jogo continua em background via WebSocket
if room_code:
    resp = requests.post(f"{BASE_URL}/rooms/{room_code}/start", json={
        "requester_id": user_id
    }, headers=headers)
    data = check("START GAME", resp, 200)
    save("start.json", data)

# ── 11. Iniciar partida já em andamento (deve retornar 409) ───────────────────
if room_code:
    resp = requests.post(f"{BASE_URL}/rooms/{room_code}/start", json={
        "requester_id": user_id
    }, headers=headers)
    check("START DUPLICADO (esperado 409)", resp, 409)

# ── 12. Tentar start sem ser o criador (deve retornar 403) ────────────────────
if room_code and anon_id:
    resp = requests.post(f"{BASE_URL}/rooms/{room_code}/start", json={
        "requester_id": anon_id
    })
    check("START SEM PERMISSAO (esperado 403)", resp, 403)

# ── 13. Criar sala com tema inválido (deve retornar 400) ──────────────────────
resp = requests.post(f"{BASE_URL}/rooms", json={
    "creator_id": user_id,
    "creator_name": new_name,
    "is_anonymous": False,
    "max_players": 2,
    "num_questions": 5,
    "theme": "tema_invalido"
}, headers=headers)
check("CREATE ROOM TEMA INVALIDO (esperado 400)", resp, 400)

# ── 14. Criar sala com max_players inválido (deve retornar 400) ───────────────
resp = requests.post(f"{BASE_URL}/rooms", json={
    "creator_id": user_id,
    "creator_name": new_name,
    "is_anonymous": False,
    "max_players": 99,
    "num_questions": 5,
    "theme": "science"
}, headers=headers)
check("CREATE ROOM MAX_PLAYERS INVALIDO (esperado 400)", resp, 400)

# ── 15. Health check ──────────────────────────────────────────────────────────
resp = requests.get(f"{BASE_URL}/health")
check("HEALTH CHECK", resp, 200)

# ── Resumo ────────────────────────────────────────────────────────────────────
total = passed + failed
print(f"\n{'='*55}")
print(f"Resultado: {passed}/{total} testes passaram")
if failed == 0:
    print("✓ Todos os endpoints REST estão funcionando corretamente.")
else:
    print(f"✗  {failed} teste(s) falharam — revise os logs acima.")
print(f"{'='*55}")
print(f"\nNota: o fluxo WebSocket (perguntas, respostas, placar, game_over)")
print(f"só pode ser validado via Frontend ou cliente STOMP dedicado.")
print(f"\nRespostas salvas em ./{OUTPUT_DIR}/")