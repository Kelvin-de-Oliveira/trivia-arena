# Contrato de Integração — API Gateway

> **Versão:** 1.1
> 
> **Responsável pelo componente:** Kelvin
> 
> **Linguagem:** Python 3.12+ / FastAPI

---

## 0. Sobre este documento

O API Gateway é o **único componente cujo contrato é, por natureza, definido em função dos outros dois**: a interface externa (REST/WebSocket) já está especificada no contrato do **SPA Web Client**, e a interface interna com o jogo já está especificada no contrato do **Game Service**. Este documento, portanto, não repete o que já foi acordado — ele especifica a **tradução** entre as duas pontas: validação de JWT, roteamento, mapeamento de campos e conversão de códigos de erro.

A interface com o **User Service** está especificada na seção 5 e foi validada contra o contrato formal do User Service (versão 1.0).

---

## Sumário

- [Contrato de Integração — API Gateway](#contrato-de-integração--api-gateway)
  - [0. Sobre este documento](#0-sobre-este-documento)
  - [Sumário](#sumário)
  - [1. Visão Geral e Responsabilidades](#1-visão-geral-e-responsabilidades)
  - [2. Autenticação — Emissão e Validação de JWT](#2-autenticação--emissão-e-validação-de-jwt)
    - [2.1 Claims do JWT](#21-claims-do-jwt)
    - [2.2 Algoritmo e expiração](#22-algoritmo-e-expiração)
    - [2.3 Validação](#23-validação)
  - [3. Garantia de Integridade de Identidade](#3-garantia-de-integridade-de-identidade)
    - [3.1 Requisição autenticada (JWT válido presente)](#31-requisição-autenticada-jwt-válido-presente)
    - [3.2 Requisição anônima (sem JWT)](#32-requisição-anônima-sem-jwt)
    - [3.3 Garantia repassada aos serviços internos](#33-garantia-repassada-aos-serviços-internos)
  - [4. Roteamento REST → Backend](#4-roteamento-rest--backend)
    - [4.1 Mapeamento de campos REST ↔ gRPC (Game Service)](#41-mapeamento-de-campos-rest--grpc-game-service)
  - [5. Interface gRPC — API Gateway → User Service](#5-interface-grpc--api-gateway--user-service)
    - [5.1 Arquivo `.proto` proposto](#51-arquivo-proto-proposto)
    - [5.2 Validações e códigos de erro gRPC propostos](#52-validações-e-códigos-de-erro-grpc-propostos)
    - [5.3 Responsabilidade do Gateway nesta interface](#53-responsabilidade-do-gateway-nesta-interface)
  - [6. Proxy WebSocket — Cliente ↔ Game Service](#6-proxy-websocket--cliente--game-service)
    - [6.1 Visão geral](#61-visão-geral)
    - [6.2 Tradução de headers no CONNECT](#62-tradução-de-headers-no-connect)
    - [6.3 Ordem de operações no handshake](#63-ordem-de-operações-no-handshake)
    - [6.4 Reconexão](#64-reconexão)
  - [7. Tradução de Códigos de Erro](#7-tradução-de-códigos-de-erro)
  - [8. Stack Tecnológica](#8-stack-tecnológica)
  - [9. Variáveis de Configuração](#9-variáveis-de-configuração)
  - [10. Restrições](#10-restrições)

---

## 1. Visão Geral e Responsabilidades

O API Gateway é o único ponto de entrada do sistema acessível pela Internet. É responsável por:

- Expor a API REST consumida pelo SPA (contrato já especificado em *Contrato de Integração — SPA Web Client*)
- Validar o JWT nas rotas que o exigem e extrair a identidade do usuário das claims do token
- Traduzir cada chamada REST recebida em uma chamada gRPC ao serviço interno correspondente (Game Service ou User Service)
- Fazer proxy da conexão WebSocket do cliente para o servidor WebSocket do Game Service, validando a identidade no handshake
- Traduzir códigos de status gRPC em códigos de status HTTP e no formato de erro JSON do contrato REST
- Garantir a integridade do `player_id`/`creator_id`/`requester_id` frente ao JWT (seção 3)

O API Gateway **não mantém estado de negócio**. Toda informação de sala, placar ou perfil vive nos serviços internos (Game Service, User Service) e em seus respectivos stores (Redis, PostgreSQL). Isso permite múltiplas réplicas do Gateway atrás do Application Load Balancer sem necessidade de sticky session.

---

## 2. Autenticação — Emissão e Validação de JWT

O Gateway não gera credenciais por conta própria: delega o registro e a verificação de senha ao User Service (seção 5), mas é o Gateway quem **emite e assina o JWT** devolvido ao cliente, e quem o **valida** em toda requisição subsequente.

### 2.1 Claims do JWT

```json
{
  "sub": "user_id (uuid)",
  "name": "string",
  "iat": 1750000000,
  "exp": 1750086400
}
```

| Claim | Descrição |
|---|---|
| `sub` | `user_id` do usuário cadastrado, é o valor usado como identidade autoritativa (seção 3) |
| `name` | Nome do usuário no momento da emissão (pode ficar desatualizado após um `PUT /users/me`; não deve ser usado para exibição, apenas auxiliar) |
| `iat` / `exp` | Emissão e expiração, padrão JWT |

### 2.2 Algoritmo e expiração

- **Algoritmo:** `HS256`, com segredo compartilhado (`JWT_SECRET`, seção 9) — não há necessidade de chave assimétrica, pois apenas o próprio Gateway emite e valida o token
- **Expiração:** 24 horas (`JWT_EXPIRATION_SECONDS=86400`, configurável)
- **Renovação:** não há refresh token nesta versão do contrato; ao expirar, o cliente deve autenticar-se novamente (`401 UNAUTHENTICATED`)

### 2.3 Validação

Em toda rota que exige autenticação (ver tabela da seção 4), o Gateway:

1. Extrai o token do header `Authorization: Bearer {jwt}`
2. Verifica assinatura e expiração
3. Se inválido ou ausente → `401 UNAUTHENTICATED`
4. Se válido → extrai `sub` (claim) como `user_id` autoritativo para o restante da requisição

---

## 3. Garantia de Integridade de Identidade

Esta seção formaliza, do ponto de vista de quem implementa a regra, o que os contratos do Frontend (seção 2.3) e do Game Service (seção 2.3) já declaram do ponto de vista de quem a consome.

### 3.1 Requisição autenticada (JWT válido presente)

O Gateway extrai `user_id` da claim `sub` do JWT e o trata como identidade autoritativa. Ele compara esse valor com o campo equivalente enviado pelo cliente no corpo da requisição (`creator_id` em `POST /rooms`, `player_id` em `POST /rooms/{code}/join`, `requester_id` em `start`/`restart`, ou o header `player-id` no CONNECT WebSocket):

- **Coincide:** segue normalmente, repassando o valor ao serviço interno.
- **Diverge:** rejeita **antes de qualquer chamada gRPC**:
  - REST → `403 PERMISSION_DENIED`
  - WebSocket → fecha a conexão com frame `error` (`code: PLAYER_ID_MISMATCH`) sem completar o CONNECT

### 3.2 Requisição anônima (sem JWT)

O Gateway não possui claim contra a qual validar. Repassa o `player_id` informado pelo cliente sem alteração. Espera-se o formato `anon:{uuid}`; um valor que não segue esse padrão pode ser rejeitado com `400 INVALID_ARGUMENT` (validação defensiva, não estritamente exigida pelos outros contratos, mas recomendada).

### 3.3 Garantia repassada aos serviços internos

Como consequência de 3.1 e 3.2, **Game Service e User Service nunca precisam revalidar identidade** — ambos confiam integralmente no valor que chega via gRPC, exatamente como já documentado na seção 10 do contrato do Game Service.

---

## 4. Roteamento REST → Backend

Tabela de roteamento completa. O corpo e os campos de cada requisição/resposta REST já estão especificados no contrato do SPA (seção 4) — aqui o que importa é o destino e a operação interna correspondente.

| Rota REST | Autenticação | Destino | Operação interna |
|---|---|---|---|
| `POST /auth/register` | Não | User Service (gRPC) | `RegisterUser` |
| `POST /auth/login` | Não | User Service (gRPC) | `LoginUser` |
| `POST /rooms` | Não (opcional) | Game Service (gRPC) | `CreateRoom` |
| `POST /rooms/{code}/join` | Não (opcional) | Game Service (gRPC) | `JoinRoom` |
| `GET /rooms/{code}` | Não | Game Service (gRPC) | `GetRoom` |
| `POST /rooms/{code}/start` | Não (opcional) | Game Service (gRPC) | `StartGame` |
| `POST /rooms/{code}/restart` | Não (opcional) | Game Service (gRPC) | `RestartGame` |
| `PUT /users/me` | **Sim** | User Service (gRPC) | `UpdateUser` |
| `GET /users/me/stats` | **Sim** | User Service (gRPC) | `GetUserStats` |
| `ws://.../ws/rooms/{code}` | Não (opcional) | Game Service (proxy WS) | — (seção 6) |

> "Não (opcional)" significa: a rota não exige JWT para ser chamada (permite anônimos), mas **se** um JWT for enviado, ele é validado e a regra da seção 3.1 se aplica.

### 4.1 Mapeamento de campos REST ↔ gRPC (Game Service)

Os nomes de campo entre o corpo JSON recebido do cliente e a mensagem gRPC enviada ao Game Service são **idênticos** — o Gateway faz passagem direta (1:1), sem renomear nada. Isso já foi confirmado campo a campo entre o contrato do Frontend e o `.proto` do Game Service (`creator_id`, `creator_name`, `player_id`, `requester_id`, `new_theme`, `max_players`, `num_questions`, `theme`). O Gateway **não deve introduzir nenhuma transformação de nome de campo** nessa direção — qualquer divergência futura entre os dois contratos é bug, não tradução esperada.

A única transformação de fato realizada pelo Gateway nesse sentido é a verificação de identidade (seção 3), que pode **sobrescrever ou rejeitar** o campo de identidade — nunca renomeá-lo.

---

## 5. Interface gRPC — API Gateway → User Service

- **Porta:** `9090` (mesma porta gRPC padrão usada pelo Game Service, em host distinto)
- **Protocolo:** gRPC / Protocol Buffers

### 5.1 Arquivo `.proto` proposto

```protobuf
syntax = "proto3";

package trivia.user.v1;

option java_package = "com.trivia.user.grpc";
option java_outer_classname = "UserServiceProto";

service UserService {
  rpc RegisterUser  (RegisterUserRequest)  returns (AuthResponse);
  rpc LoginUser      (LoginUserRequest)     returns (AuthResponse);
  rpc UpdateUser    (UpdateUserRequest)    returns (UpdateUserResponse);
  rpc GetUserStats  (GetUserStatsRequest)  returns (GetUserStatsResponse);
}

message RegisterUserRequest {
  string name     = 1;
  string password = 2;
}

message LoginUserRequest {
  string name     = 1;
  string password = 2;
}

message AuthResponse {
  string user_id = 1;
  string name    = 2;
  // o JWT NÃO é emitido aqui — o Gateway assina o token (seção 2)
  // usando user_id e name retornados por esta chamada
}

message UpdateUserRequest {
  string user_id = 1;
  optional string name     = 2;
  optional string password = 3;
}

message UpdateUserResponse {
  bool success = 1;
}

message GetUserStatsRequest {
  string user_id = 1;
}

message GetUserStatsResponse {
  int32 games_played   = 1;
  double avg_position  = 2;
  double avg_points    = 3;
  int32 highest_score   = 4;
  int32 games_won       = 5;
}
```

### 5.2 Validações e códigos de erro gRPC propostos

| RPC | Validação obrigatória | Status gRPC em erro |
|---|---|---|
| `RegisterUser` | `name` e `password` não vazios; `name` não cadastrado | `INVALID_ARGUMENT` / `ALREADY_EXISTS` |
| `LoginUser` | Credenciais devem corresponder a um usuário existente | `UNAUTHENTICATED` |
| `UpdateUser` | Ao menos um campo (`name` ou `password`) enviado; novo `name`, se enviado, não pode estar em uso | `INVALID_ARGUMENT` / `ALREADY_EXISTS` |
| `GetUserStats` | `user_id` deve existir | `NOT_FOUND` |

### 5.3 Responsabilidade do Gateway nesta interface

- Em `RegisterUser`/`LoginUser`: o Gateway recebe `user_id` e `name` do User Service, **assina o JWT** (seção 2) e devolve `{ "jwt": "...", "user_id": "..." }` ao cliente — exatamente o formato já especificado no contrato do Frontend (4.1/4.2).
- Em `UpdateUser`/`GetUserStats`: o Gateway já validou o JWT antes de chegar aqui (rotas exigem autenticação) e usa o `sub` da claim como `user_id` da chamada gRPC  o cliente nunca informa `user_id` diretamente nessas duas rotas.

---

## 6. Proxy WebSocket — Cliente ↔ Game Service

### 6.1 Visão geral

O Gateway não implementa lógica de jogo no WebSocket — ele estabelece duas conexões e repassa frames entre elas após validar a identidade no handshake:

```
Cliente  ──ws://{API_GATEWAY_HOST}/ws/rooms/{code}──▶  Gateway  ──ws://game-service:8080/ws──▶  Game Service
```

### 6.2 Tradução de headers no CONNECT

| Header recebido do cliente | Header enviado ao Game Service | Transformação |
|---|---|---|
| `player-id` | `player-id` | Repassado **após** a verificação da seção 3 (pode ser rejeitado antes de chegar aqui) |
| `room-code` | `room-code` | Repassado sem alteração |
| `authorization: Bearer {jwt}` (opcional) | `authenticated=true\|false` | O Gateway valida o JWT (seção 2.3) e repassa apenas o resultado booleano — o Game Service nunca recebe o token |

### 6.3 Ordem de operações no handshake

1. Cliente abre WebSocket com o Gateway, enviando os headers de CONNECT
2. Gateway valida o JWT, se presente (seção 2.3)
3. Gateway aplica a regra de integridade de identidade (seção 3.1/3.2) — rejeita aqui se houver divergência, **antes** de abrir a conexão com o Game Service
4. Gateway abre a conexão com o Game Service, com os headers traduzidos (6.2)
5. A partir daqui, o Gateway apenas repassa frames nos dois sentidos, sem inspecionar ou alterar o corpo das mensagens STOMP (`/topic/rooms/{code}`, `/app/rooms/{code}/answer`)

### 6.4 Reconexão

O Gateway não mantém estado de sessão entre reconexões, cada tentativa de reconexão do cliente (contrato do Frontend, seção 5.6) é um novo handshake completo, repetindo os passos 1–5. A recuperação do estado da partida é responsabilidade do cliente (via `GET /rooms/{code}`) e do Game Service (que reenvia `game_over` automaticamente se a sala já estiver `FINISHED`, conforme seção 3.1 do contrato do Game Service), o Gateway não participa dessa lógica.

---

## 7. Tradução de Códigos de Erro

Tabela canônica de tradução entre o status gRPC retornado pelos serviços internos e o status HTTP + corpo de erro devolvido ao cliente (formato já especificado no contrato do Frontend, seção 3).

| Status gRPC | Status HTTP | `error` no JSON |
|---|---|---|
| `INVALID_ARGUMENT` | `400` | `INVALID_ARGUMENT` |
| `UNAUTHENTICATED` | `401` | `UNAUTHENTICATED` |
| `PERMISSION_DENIED` | `403` | `PERMISSION_DENIED` |
| `NOT_FOUND` | `404` | `NOT_FOUND` |
| `ALREADY_EXISTS` | `409` | `ALREADY_EXISTS` |
| `FAILED_PRECONDITION` | `409` | `FAILED_PRECONDITION` |
| `UNAVAILABLE` | `503` | `UNAVAILABLE` |

> Esta tabela é a fonte única da verdade para a tradução de erros. Qualquer novo código de erro adicionado a um contrato de serviço interno deve primeiro ganhar uma linha aqui antes de ser usado.

O corpo de erro sempre segue o formato:
```json
{
  "status": 400,
  "error": "INVALID_ARGUMENT",
  "message": "descrição legível do erro, obtida da mensagem gRPC original ou de validação própria do Gateway"
}
```

---

## 8. Stack Tecnológica

| Componente | Tecnologia |
|---|---|
| Linguagem | Python 3.12+ |
| Framework HTTP/WS | FastAPI + Starlette (WebSocket nativo) |
| Cliente gRPC | `grpcio` + `grpcio-tools` (stubs gerados dos `.proto` do Game Service e User Service) |
| JWT | `python-jose` ou `PyJWT` |
| Servidor ASGI | `uvicorn` |

---

## 9. Variáveis de Configuração

```env
# Game Service
GAME_SERVICE_GRPC_HOST=game-service
GAME_SERVICE_GRPC_PORT=9090
GAME_SERVICE_WS_HOST=game-service
GAME_SERVICE_WS_PORT=8080

# User Service
USER_SERVICE_GRPC_HOST=user-service
USER_SERVICE_GRPC_PORT=9090

# JWT
JWT_SECRET=change-me-in-production
JWT_EXPIRATION_SECONDS=86400

# Servidor
PORT=8000
```

> A porta `8000` é interna ao contêiner. A exposição externa é gerenciada pelo Application Load Balancer da AWS, conforme o documento de escopo - não impacta este contrato.

---

## 10. Restrições

O API Gateway **não deve**:

- Conter lógica de negócio do jogo (cálculo de créditos, controle de rodada) ou de usuário (regras de unicidade de nome, hashing de senha) — toda essa lógica vive no Game Service e no User Service
- Acessar Redis, Kafka, o Question Database ou o User Database diretamente — toda persistência é mediada pelos serviços de domínio via gRPC
- Manter estado de sessão de jogo ou de WebSocket entre requisições — cada instância do Gateway deve ser substituível sem efeito colateral, permitindo escalonamento horizontal atrás do ALB sem sticky session
- Inspecionar ou alterar o corpo das mensagens STOMP que ele faz proxy (seção 6.3) — sua responsabilidade no WebSocket termina na validação de identidade do handshake