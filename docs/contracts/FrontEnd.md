# Contrato de Integração — SPA Web Client (Consolidado)

> **Versão:** 1.3
> 
> **Responsável pelo componente:** Felipe
> 
> **Stack:** React + Vite

---

## Sumário

- [Contrato de Integração — SPA Web Client (Consolidado)](#contrato-de-integração--spa-web-client-consolidado)
  - [Sumário](#sumário)
  - [1. Visão Geral e Responsabilidades](#1-visão-geral-e-responsabilidades)
  - [2. Autenticação e Identidade](#2-autenticação-e-identidade)
    - [2.1 Usuário cadastrado — JWT](#21-usuário-cadastrado--jwt)
    - [2.2 Jogador anônimo — ID temporário](#22-jogador-anônimo--id-temporário)
    - [2.3 Consistência entre `player_id` e identidade do JWT](#23-consistência-entre-player_id-e-identidade-do-jwt)
  - [3. Convenções da API REST](#3-convenções-da-api-rest)
  - [4. Endpoints REST](#4-endpoints-rest)
    - [4.1 `POST /auth/register` — Cadastro](#41-post-authregister--cadastro)
    - [4.2 `POST /auth/login` — Login](#42-post-authlogin--login)
    - [4.3 `POST /rooms` — Criar sala](#43-post-rooms--criar-sala)
    - [4.4 `POST /rooms/{code}/join` — Entrar em sala](#44-post-roomscodejoin--entrar-em-sala)
    - [4.5 `GET /rooms/{code}` — Consultar estado da sala](#45-get-roomscode--consultar-estado-da-sala)
    - [4.6 `POST /rooms/{code}/start` — Iniciar partida](#46-post-roomscodestart--iniciar-partida)
    - [4.7 `POST /rooms/{code}/restart` — Reiniciar partida](#47-post-roomscoderestart--reiniciar-partida)
    - [4.8 `PUT /users/me` — Atualizar perfil](#48-put-usersme--atualizar-perfil)
    - [4.9 `GET /users/me/stats` — Estatísticas históricas](#49-get-usersmestats--estatísticas-históricas)
  - [5. Interface WebSocket](#5-interface-websocket)
    - [5.1 Headers no CONNECT](#51-headers-no-connect)
    - [5.2 Subscribe — eventos recebidos do servidor](#52-subscribe--eventos-recebidos-do-servidor)
    - [5.3 Send — envio de resposta ao servidor](#53-send--envio-de-resposta-ao-servidor)
    - [5.4 Mensagens recebidas — Servidor → Cliente](#54-mensagens-recebidas--servidor--cliente)
    - [5.5 Mensagem enviada — Cliente → Servidor](#55-mensagem-enviada--cliente--servidor)
    - [5.6 Reconexão](#56-reconexão)
  - [6. Fluxos da Aplicação](#6-fluxos-da-aplicação)
    - [6.1 Cadastro e login](#61-cadastro-e-login)
    - [6.2 Entrada anônima](#62-entrada-anônima)
    - [6.3 Criar sala](#63-criar-sala)
    - [6.4 Entrar em sala](#64-entrar-em-sala)
    - [6.5 Tela de espera (lobby da sala)](#65-tela-de-espera-lobby-da-sala)
    - [6.6 Partida](#66-partida)
    - [6.7 Reiniciar partida](#67-reiniciar-partida)
    - [6.8 Consulta de perfil (usuário cadastrado)](#68-consulta-de-perfil-usuário-cadastrado)
  - [7. Tratamento de Erros](#7-tratamento-de-erros)
    - [7.1 Erros HTTP](#71-erros-http)
    - [7.2 Erros WebSocket](#72-erros-websocket)
    - [7.3 Falha de conexão WebSocket](#73-falha-de-conexão-websocket)
  - [8. Stack Tecnológica e Dependências](#8-stack-tecnológica-e-dependências)
  - [9. Restrições](#9-restrições)

---

## 1. Visão Geral e Responsabilidades

O SPA é a interface com o usuário, acessada pelo navegador. É responsável por:

- Renderizar as telas de cadastro, login e entrada anônima
- Renderizar o lobby de criação e entrada em sala
- Manter **uma única conexão WebSocket com o API Gateway**, aberta ao entrar no lobby e mantida durante toda a partida, exibindo jogadores conectados, perguntas, resultados de rodada e ranking em tempo real
- Renderizar o painel de estatísticas históricas de usuários cadastrados
- Gerenciar o estado local de sessão (JWT e player ID)

O SPA **não** contém lógica de negócio — toda validação, cálculo de créditos e controle de estado do jogo é responsabilidade dos serviços backend. O SPA também **não se conecta diretamente ao Game Service**: toda comunicação, REST ou WebSocket, passa pelo API Gateway.

---

## 2. Autenticação e Identidade

### 2.1 Usuário cadastrado — JWT

Ao realizar login ou cadastro com sucesso, a API retorna um JWT no campo `jwt` da resposta. O SPA deve:

- Armazenar o JWT **em memória** (`useState` ou contexto React) — não usar `localStorage` nem `sessionStorage`
- Incluir o JWT em todas as requisições que exigem autenticação via header:

```
Authorization: Bearer {jwt}
```

- Descartar o JWT ao encerrar a sessão (fechar aba ou fazer logout)

### 2.2 Jogador anônimo — ID temporário

Para jogadores que optam por entrar sem cadastro, o SPA deve gerar um identificador temporário localmente:

```javascript
const playerId = "anon:" + crypto.randomUUID();
```

- Armazenar em memória (`useState`)
- Não enviar header `Authorization`
- O ID é descartado ao fechar a aba

### 2.3 Consistência entre `player_id` e identidade do JWT

O API Gateway valida essa correspondência contra o JWT; uma divergência resulta em:

- **REST:** `403 PERMISSION_DENIED`
- **WebSocket:** fechamento da conexão com frame `error` (`code: PLAYER_ID_MISMATCH`) antes de o CONNECT ser concluído

Jogadores anônimos não estão sujeitos a essa verificação, por não enviarem JWT.

---

## 3. Convenções da API REST

**Base URL:** `http://{API_GATEWAY_HOST}`

**Headers obrigatórios em todas as requisições:**
```
Content-Type: application/json
```

**Header de autenticação (quando aplicável):**
```
Authorization: Bearer {jwt}
```

**Formato de resposta de erro:**
```json
{
  "status": 400,
  "error": "INVALID_ARGUMENT",
  "message": "descrição legível do erro"
}
```

---

## 4. Endpoints REST

### 4.1 `POST /auth/register` — Cadastro

**Autenticação:** não exigida

**Request:**
```json
{
  "name": "string",
  "password": "string"
}
```

**Response `200`:**
```json
{
  "jwt": "string",
  "user_id": "uuid"
}
```

**Erros:**

| Status | Código | Situação |
|---|---|---|
| 400 | `INVALID_ARGUMENT` | Campos ausentes ou inválidos |
| 409 | `ALREADY_EXISTS` | Nome de usuário já cadastrado |

---

### 4.2 `POST /auth/login` — Login

**Autenticação:** não exigida

**Request:**
```json
{
  "name": "string",
  "password": "string"
}
```

**Response `200`:**
```json
{
  "jwt": "string",
  "user_id": "uuid"
}
```

**Erros:**

| Status | Código | Situação |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Credenciais inválidas |

---

### 4.3 `POST /rooms` — Criar sala

**Autenticação:** não exigida (permitido para anônimos)

**Request:**
```json
{
  "creator_id": "string",
  "creator_name": "string",
  "is_anonymous": false,
  "max_players": 4,
  "num_questions": 10,
  "theme": "science"
}
```

**Restrições de valores:**
- `max_players`: inteiro entre 2 e 10
- `num_questions`: inteiro entre 5 e 20
- `theme`: um dos valores válidos listados abaixo

**Temas válidos:**

| Valor | Exibição |
|---|---|
| `music` | Música |
| `sport_and_leisure` | Esporte e Lazer |
| `film_and_tv` | Cinema e TV |
| `arts_and_literature` | Artes e Literatura |
| `history` | História |
| `society_and_culture` | Sociedade e Cultura |
| `science` | Ciência |
| `geography` | Geografia |
| `food_and_drink` | Gastronomia |
| `general_knowledge` | Conhecimentos Gerais |

**Response `200`:**
```json
{
  "room_code": "ABC123"
}
```

**Erros:**

| Status | Código | Situação |
|---|---|---|
| 400 | `INVALID_ARGUMENT` | Valores fora dos limites ou tema inválido |
| 503 | `UNAVAILABLE` | Shard do tema indisponível |

---

### 4.4 `POST /rooms/{code}/join` — Entrar em sala

**Autenticação:** não exigida (permitido para anônimos)

**Request:**
```json
{
  "player_id": "string",
  "player_name": "string",
  "is_anonymous": false
}
```

**Response `200`:**
```json
{
  "players": [
    { "player_id": "string", "player_name": "string", "is_anonymous": false, "score": 0 }
  ],
  "status": "WAITING",
  "theme": "science",
  "max_players": 4,
  "creator_id": "string",
  "num_questions": 10
}
```

**Erros:**

| Status | Código | Situação |
|---|---|---|
| 404 | `NOT_FOUND` | Sala não encontrada |
| 409 | `FAILED_PRECONDITION` | Sala não está em `WAITING` ou atingiu o limite de jogadores |

---

### 4.5 `GET /rooms/{code}` — Consultar estado da sala

**Autenticação:** não exigida

Usado tanto na entrada manual de código quanto na recuperação de estado após reconexão de WebSocket (ver seção 5.6).

**Response `200`:**
```json
{
  "room_code": "ABC123",
  "status": "WAITING",
  "theme": "science",
  "max_players": 4,
  "num_questions": 10,
  "players": [
    { "player_id": "string", "player_name": "string", "is_anonymous": false, "score": 0 }
  ],
  "creator_id": "string"
}
```

**Erros:**

| Status | Código | Situação |
|---|---|---|
| 404 | `NOT_FOUND` | Sala não encontrada |

---

### 4.6 `POST /rooms/{code}/start` — Iniciar partida

**Autenticação:** não exigida (validação de permissão é feita pelo Game Service via `requester_id`)

**Request:**
```json
{
  "requester_id": "string"
}
```

**Response `200`:**
```json
{
  "started": true
}
```

> O início do jogo de fato é sinalizado pelo evento WebSocket `game_started`, não por esta resposta.

**Erros:**

| Status | Código | Situação |
|---|---|---|
| 403 | `PERMISSION_DENIED` | Solicitante não é o criador da sala |
| 409 | `FAILED_PRECONDITION` | Sala não está em `WAITING` ou tem menos de 2 jogadores |

---

### 4.7 `POST /rooms/{code}/restart` — Reiniciar partida

**Autenticação:** não exigida (validação de permissão é feita pelo Game Service)

**Request:**
```json
{
  "requester_id": "string",
  "new_theme": "history"
}
```

**Response `200`:**
```json
{
  "started": true
}
```

**Erros:**

| Status | Código | Situação |
|---|---|---|
| 403 | `PERMISSION_DENIED` | Solicitante não é o criador da sala |
| 409 | `FAILED_PRECONDITION` | Sala não está em `FINISHED` |
| 503 | `UNAVAILABLE` | Shard do novo tema indisponível |

---

### 4.8 `PUT /users/me` — Atualizar perfil

**Autenticação:** obrigatória (JWT)

Permite alterar nome e/ou senha do usuário autenticado. Não há outros dados de perfil.

**Request:** ao menos um dos campos deve ser enviado
```json
{
  "name": "string",
  "password": "string"
}
```

**Response `200`:**
```json
{
  "success": true
}
```

**Erros:**

| Status | Código | Situação |
|---|---|---|
| 400 | `INVALID_ARGUMENT` | Nenhum campo enviado |
| 401 | `UNAUTHENTICATED` | JWT ausente ou inválido |
| 409 | `ALREADY_EXISTS` | Novo nome já está em uso |

---

### 4.9 `GET /users/me/stats` — Estatísticas históricas

**Autenticação:** obrigatória (JWT)

**Response `200`:**
```json
{
  "games_played": 42,
  "avg_position": 2.3,
  "avg_points": 31.5,
  "highest_score": 87,
  "games_won": 15
}
```

| Campo | Tipo | Descrição |
|---|---|---|
| `games_played` | int | Número de partidas disputadas |
| `avg_position` | float | Posição média do jogador nas partidas |
| `avg_points` | float | Média de pontos por partida |
| `highest_score` | int | Maior pontuação já obtida em uma única partida |
| `games_won` | int | Número de vitórias (partidas terminadas em 1º lugar) |

**Erros:**

| Status | Código | Situação |
|---|---|---|
| 401 | `UNAUTHENTICATED` | JWT ausente ou inválido |

---

## 5. Interface WebSocket

A conexão WebSocket é estabelecida **com o API Gateway** ao entrar no lobby de uma sala e mantida durante toda a partida. O Gateway atua como proxy para o servidor WebSocket do Game Service — o SPA nunca se conecta diretamente a ele.

- **URL:** `ws://{API_GATEWAY_HOST}/ws/rooms/{room_code}`
- **Protocolo:** WebSocket / STOMP
- **Biblioteca recomendada:** `@stomp/stompjs`

### 5.1 Headers no CONNECT

```
player-id:     {player_id}
room-code:     {room_code}
authorization: Bearer {jwt}     ← omitir se anônimo
```

### 5.2 Subscribe — eventos recebidos do servidor

```
/topic/rooms/{room_code}
```

### 5.3 Send — envio de resposta ao servidor

```
/app/rooms/{room_code}/answer
```

### 5.4 Mensagens recebidas — Servidor → Cliente

**`player_joined`** — novo jogador entrou na sala
```json
{
  "type": "player_joined",
  "player_id": "string",
  "player_name": "string",
  "players": [
    { "player_id": "string", "player_name": "string", "is_anonymous": false, "score": 0 }
  ]
}
```

**`game_started`** — partida iniciada pelo criador
```json
{
  "type": "game_started",
  "total_questions": 10,
  "theme": "science"
}
```

**`question`** — pergunta da rodada atual
```json
{
  "type": "question",
  "idx": 1,
  "question_id": "uuid",
  "text": "Qual o maior planeta?",
  "options": {
    "a": "Terra",
    "b": "Júpiter",
    "c": "Marte",
    "d": "Vênus"
  },
  "time_limit_ms": 20000
}
```

> O SPA deve iniciar um contador regressivo de `time_limit_ms` ao receber este evento. Não confiar no relógio local para calcular tempo de resposta — o servidor é a fonte de verdade.

**`round_result`** — resultado após encerramento de uma rodada
```json
{
  "type": "round_result",
  "question_id": "uuid",
  "correct_option": "b",
  "credits": [
    { "player_id": "string", "earned": 6, "position": 1 },
    { "player_id": "string", "earned": 3, "position": 2 },
    { "player_id": "string", "earned": 1, "position": 3 }
  ],
  "scores": [
    { "player_id": "string", "player_name": "string", "total_score": 47 }
  ]
}
```

> O SPA deve encerrar o temporizador visual, destacar a opção correta e atualizar o placar.

**`game_over`** — fim da partida
```json
{
  "type": "game_over",
  "ranking": [
    { "player_id": "string", "player_name": "string", "total_score": 47, "position": 1 }
  ]
}
```

**`error`** — erro no servidor
```json
{
  "type": "error",
  "code": "ROOM_NOT_FOUND",
  "message": "string"
}
```

### 5.5 Mensagem enviada — Cliente → Servidor

**Resposta do jogador**
```json
{
  "type": "answer",
  "question_id": "uuid",
  "option": "b"
}
```

> Deve ser enviada apenas uma vez por rodada. O servidor ignora respostas duplicadas do mesmo jogador na mesma rodada. Ao selecionar uma opção, o SPA deve desabilitar imediatamente as demais para impedir o envio de uma segunda resposta.

### 5.6 Reconexão

A conexão WebSocket pode cair por queda de instância do Game Service ou da rede. O SPA deve implementar reconexão automática com **exponential backoff**:

- Detectar queda via evento `onclose` do WebSocket
- Tentar reconectar com intervalos crescentes: 1s, 2s, 4s, 8s (máximo 4 tentativas)
- Após reconectar, chamar `GET /rooms/{code}` (seção 4.5) para recuperar o estado atual da sala
  - Se o estado retornado for `FINISHED`, aguardar o evento `game_over` via WebSocket — o servidor o reenvia automaticamente ao cliente reconectado
  - Se o estado for `WAITING` ou `IN_PROGRESS`, aguardar os eventos normais do fluxo de jogo
- Se todas as tentativas falharem, exibir mensagem de erro com opção de reconexão manual

A biblioteca `@stomp/stompjs` possui suporte nativo a reconexão via `reconnectDelay`.

---

## 6. Fluxos da Aplicação

### 6.1 Cadastro e login
```
Preenche formulário
→ POST /auth/register ou POST /auth/login
→ Armazena jwt e user_id em memória
→ Redireciona para lobby
```

### 6.2 Entrada anônima
```
Clica em "Entrar como visitante"
→ Gera playerId = "anon:" + crypto.randomUUID()
→ Armazena em memória
→ Redireciona para lobby (sem JWT)
```

### 6.3 Criar sala
```
Preenche configuração (tema, max_players, num_questions)
→ POST /rooms
→ Recebe room_code
→ Conecta WebSocket ws://{API_GATEWAY_HOST}/ws/rooms/{room_code}
→ Aguarda outros jogadores (ouve player_joined)
```

### 6.4 Entrar em sala
```
Informa room_code
→ POST /rooms/{code}/join
→ Recebe estado atual da sala
→ Conecta WebSocket ws://{API_GATEWAY_HOST}/ws/rooms/{room_code}
→ Aguarda início da partida (ouve game_started)
```

### 6.5 Tela de espera (lobby da sala)
- Exibe jogadores conectados, atualizados via `player_joined`
- Botão **Iniciar** visível apenas para o criador (comparar `player_id`/`creator_id` local com o da sala)
- Botão **Iniciar** habilitado apenas com ≥ 2 jogadores → `POST /rooms/{code}/start`

### 6.6 Partida
```
Recebe game_started → exibe tela de jogo
Recebe question    → exibe pergunta, opções e inicia contador
Envia answer        → /app/rooms/{code}/answer (desabilita opções após envio)
Recebe round_result → encerra timer, destaca resposta correta, atualiza placar
... repete por num_questions rodadas ...
Recebe game_over    → exibe ranking final
```

### 6.7 Reiniciar partida
```
Criador escolhe novo tema (ou mantém o mesmo)
→ POST /rooms/{code}/restart { requester_id, new_theme }
→ Aguarda game_started via WebSocket
```

### 6.8 Consulta de perfil (usuário cadastrado)
```
GET /users/me/stats (com JWT)
→ Exibe dashboard: games_played, avg_position,
  avg_points, highest_score, games_won

Formulário de edição (name e/ou password)
→ PUT /users/me (com JWT)
→ Exibe confirmação de sucesso
```

---

## 7. Tratamento de Erros

### 7.1 Erros HTTP

| Código | Comportamento esperado no SPA |
|---|---|
| 400 | Exibir mensagem de validação ao lado do campo correspondente |
| 401 | Redirecionar para tela de login, descartar JWT |
| 403 | Exibir mensagem "Você não tem permissão para esta ação" |
| 404 | Exibir mensagem "Sala não encontrada" |
| 409 | Exibir mensagem específica do `error` retornado |
| 503 | Exibir mensagem "Tema temporariamente indisponível, tente outro" |

### 7.2 Erros WebSocket

Ao receber mensagem do tipo `error`:

| `code` | Comportamento esperado |
|---|---|
| `ROOM_NOT_FOUND` | Redirecionar para lobby |
| Outros | Exibir mensagem genérica na tela atual |

### 7.3 Falha de conexão WebSocket

Se todas as tentativas de reconexão (seção 5.6) falharem, exibir mensagem de erro com opção de tentar reconectar manualmente.

---

## 8. Stack Tecnológica e Dependências

| Componente | Tecnologia |
|---|---|
| Framework | React 18+ |
| Build tool | Vite |
| WebSocket / STOMP | `@stomp/stompjs` |
| HTTP client | `fetch` nativo ou `axios` |
| Gerenciamento de estado | React Context + `useState` |
| Roteamento | `react-router-dom` |

---

## 9. Restrições

O SPA **não deve**:

- Armazenar JWT em `localStorage` ou `sessionStorage` — risco de XSS
- Calcular créditos ou validar respostas localmente — toda lógica está no servidor
- Conectar-se diretamente ao Game Service — toda comunicação (REST e WebSocket) passa pelo API Gateway
- Acessar Redis, Kafka, o User Service ou qualquer outro serviço interno diretamente
- Confiar no timestamp ou relógio local para calcular tempo de resposta ou ordenar respostas — o servidor é a fonte de verdade
