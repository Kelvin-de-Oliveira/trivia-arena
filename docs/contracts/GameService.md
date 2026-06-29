# Contrato de Integração — Game Service

> **Versão:** 1.2 
> 
> **Responsável pelo serviço:** Hugo 
> 
> **Linguagem:** Java 21 + Spring Boot 3.x  

---

## Sumário

- [Contrato de Integração — Game Service](#contrato-de-integração--game-service)
  - [Sumário](#sumário)
  - [1. Visão Geral e Responsabilidades](#1-visão-geral-e-responsabilidades)
    - [Temas disponíveis](#temas-disponíveis)
  - [2. Interface gRPC — API Gateway → Game Service](#2-interface-grpc--api-gateway--game-service)
    - [2.1 Arquivo .proto](#21-arquivo-proto)
    - [2.2 Validações e códigos de erro gRPC](#22-validações-e-códigos-de-erro-grpc)
    - [2.3 Garantia de integridade de identidade do jogador](#23-garantia-de-integridade-de-identidade-do-jogador)
  - [3. Interface WebSocket — Game Service ↔ Clientes](#3-interface-websocket--game-service--clientes)
    - [3.1 Headers STOMP no CONNECT](#31-headers-stomp-no-connect)
    - [3.2 Tópico de recebimento — Servidor → Cliente](#32-tópico-de-recebimento--servidor--cliente)
    - [3.3 Destino de envio — Cliente → Servidor](#33-destino-de-envio--cliente--servidor)
    - [3.4 Schemas das mensagens](#34-schemas-das-mensagens)
      - [Servidor → Cliente](#servidor--cliente)
      - [Cliente → Servidor](#cliente--servidor)
  - [4. Interface Kafka — Game Service → Kafka (Produtor)](#4-interface-kafka--game-service--kafka-produtor)
    - [Schema da mensagem](#schema-da-mensagem)
  - [5. Interface Redis — Game Service ↔ Redis](#5-interface-redis--game-service--redis)
    - [5.1 Estrutura de chaves](#51-estrutura-de-chaves)
    - [5.2 Hash `room:{code}:state`](#52-hash-roomcodestate)
    - [5.3 Hash `room:{code}:players`](#53-hash-roomcodeplayers)
    - [5.4 Pub/Sub `room:{code}:broadcast`](#54-pubsub-roomcodebroadcast)
  - [5.5 Hash `room:{code}:round:{idx}:answers`](#55-hash-roomcoderoundidxanswers)
    - [Por que essa chave existe](#por-que-essa-chave-existe)
    - [Operação de registro de resposta correta](#operação-de-registro-de-resposta-correta)
    - [Operação de leitura ao encerrar a rodada](#operação-de-leitura-ao-encerrar-a-rodada)
    - [Limpeza](#limpeza)
  - [6. Interface Question Database — Game Service → PostgreSQL](#6-interface-question-database--game-service--postgresql)
    - [6.1 Schema esperado em cada shard](#61-schema-esperado-em-cada-shard)
    - [6.2 Tabela de mapeamento estático — tema → shard](#62-tabela-de-mapeamento-estático--tema--shard)
    - [6.3 Query executada no início de cada partida](#63-query-executada-no-início-de-cada-partida)
    - [6.4 Comportamento em caso de falha de shard](#64-comportamento-em-caso-de-falha-de-shard)
  - [7. Regras de Negócio Internas](#7-regras-de-negócio-internas)
    - [7.1 Máquina de estados da sala](#71-máquina-de-estados-da-sala)
    - [7.2 Algoritmo de distribuição de créditos](#72-algoritmo-de-distribuição-de-créditos)
    - [7.3 Requisitos de thread safety](#73-requisitos-de-thread-safety)
    - [7.4 Timeout por rodada](#74-timeout-por-rodada)
  - [8. Stack Tecnológica](#8-stack-tecnológica)
  - [9. Variáveis de Configuração](#9-variáveis-de-configuração)
  - [10. Restrições](#10-restrições)

---

## 1. Visão Geral e Responsabilidades

O Game Service é o módulo central do jogo. É responsável por:

- Criar e gerenciar salas e seu ciclo de vida completo
- Conduzir o fluxo de perguntas durante a partida
- Calcular e distribuir créditos por rodada de forma concorrente
- Manter o estado das salas e o placar no Redis
- Publicar o resultado final no Kafka ao término de cada partida
- Expor servidor gRPC para chamadas de gerenciamento vindas do API Gateway
- Expor servidor WebSocket para comunicação em tempo real com os clientes

### Temas disponíveis

Os seguintes valores são os únicos aceitos no campo `theme`:

| Valor | Descrição |
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

---

## 2. Interface gRPC — API Gateway → Game Service

O API Gateway chama o Game Service via gRPC para todas as operações de gerenciamento de sala.

- **Porta:** `9090`
- **Protocolo:** gRPC / Protocol Buffers

### 2.1 Arquivo .proto

```protobuf
syntax = "proto3";
 
package trivia.game.v1;
 
option java_package = "com.trivia.game.grpc";
option java_outer_classname = "GameServiceProto";
 
service GameService {
  rpc CreateRoom   (CreateRoomRequest)   returns (CreateRoomResponse);
  rpc JoinRoom     (JoinRoomRequest)     returns (JoinRoomResponse);
  rpc StartGame    (StartGameRequest)    returns (StartGameResponse);
  rpc RestartGame  (RestartGameRequest)  returns (StartGameResponse);
  rpc GetRoom      (GetRoomRequest)      returns (GetRoomResponse);
}
 
// ── Mensagens ──────────────────────────────────────────────────────────────
 
message CreateRoomRequest {
  string creator_id    = 1;
  string creator_name  = 2;
  bool   is_anonymous  = 3;
  int32  max_players   = 4;  // 2 a 10
  int32  num_questions = 5;  // 5 a 20
  string theme         = 6;
}
 
message CreateRoomResponse {
  string room_code = 1;
}
 
message JoinRoomRequest {
  string room_code    = 1;
  string player_id    = 2;
  string player_name  = 3;
  bool   is_anonymous = 4;
}
 
message JoinRoomResponse {
  repeated Player players     = 1;
  RoomStatus      status      = 2;
  string          theme       = 3;
  int32           max_players = 4;
  string          creator_id  = 5; 
  int32 num_questions = 6;
}
 
message StartGameRequest {
  string room_code    = 1;
  string requester_id = 2;
}
 
message StartGameResponse {
  bool started = 1;
}
 
message RestartGameRequest {
  string room_code    = 1;
  string requester_id = 2;
  string new_theme    = 3;
}
 
message GetRoomRequest {
  string room_code = 1;
}
 
message GetRoomResponse {
  string          room_code     = 1;
  RoomStatus      status        = 2;
  string          theme         = 3;
  int32           max_players   = 4;
  int32           num_questions = 5;
  repeated Player players       = 6;
  string          creator_id    = 7;
}
 
message Player {
  string player_id    = 1;
  string player_name  = 2;
  bool   is_anonymous = 3;
  int32  score        = 4;
}
 
enum RoomStatus {
  WAITING     = 0;
  IN_PROGRESS = 1;
  FINISHED    = 2;
}
```



### 2.2 Validações e códigos de erro gRPC

| RPC | Validação obrigatória | Status gRPC em erro |
|---|---|---|
| `CreateRoom` | `max_players` entre 2 e 10; `num_questions` entre 5 e 20; `theme` deve ser um dos valores válidos; shard do `theme` deve estar disponível | `INVALID_ARGUMENT` / `UNAVAILABLE` |
| `JoinRoom` | Sala deve existir e estar em `WAITING`; não atingiu `max_players` | `NOT_FOUND` / `FAILED_PRECONDITION` |
| `StartGame` | `requester_id` deve ser o `creator_id` da sala; sala em `WAITING`; mínimo 2 jogadores | `PERMISSION_DENIED` / `FAILED_PRECONDITION` |
| `RestartGame` | `requester_id` deve ser o `creator_id`; sala em `FINISHED`; shard do `new_theme` deve estar disponível | `PERMISSION_DENIED` / `FAILED_PRECONDITION` / `UNAVAILABLE` |
| `GetRoom` | Sala deve existir no Redis | `NOT_FOUND` |
 
> **Nota sobre `GetRoom`:** este RPC existe para que o API Gateway possa servir o endpoint REST `GET /rooms/{roomCode}` sem acessar o Redis diretamente. O Game Service é o único componente que lê e escreve no Redis,  o Gateway não deve conhecer o schema interno das chaves. A implementação do `GetRoom` no Game Service lê `room:{code}:state` e `room:{code}:players` e mapeia para `GetRoomResponse`, sem lógica de negócio adicional. 
> **Nota sobre `RestartGame`** Exige um passo de sanitização atômica sobre room:{code}:players, zerando todos os valores antes de liberar a abertura de uma nova partida.
 
### 2.3 Garantia de integridade de identidade do jogador

Os campos `player_id`, `creator_id` e `requester_id` recebidos pelo Game Service, via gRPC ou no header `player-id` do CONNECT WebSocket — já chegam verificados pelo API Gateway:

- **Requisição autenticada (JWT válido):** o Gateway extrai o `user_id` das claims do token e o usa como identidade autoritativa, rejeitando qualquer valor divergente enviado pelo cliente no corpo da requisição ou no header `player-id`.
- **Requisição anônima (sem JWT):** o Gateway não tem claim contra o qual validar, então repassa o `player_id` informado pelo cliente sem alteração (formato esperado: `anon:{uuid}`).

O Game Service **não deve revalidar essa identidade**, ele confia integralmente no valor recebido do Gateway, da mesma forma que já não valida JWT (seção 10).

---

## 3. Interface WebSocket — Game Service ↔ Clientes

O Game Service expõe um servidor WebSocket com STOMP. O API Gateway faz proxy das conexões dos clientes para esse servidor.

- **Porta:** `8080`
- **Endpoint de conexão:** `ws://game-service:8080/ws`
- **Protocolo:** WebSocket / STOMP

### 3.1 Headers STOMP no CONNECT

```
player-id:     {player_id}          ← obrigatório
room-code:     {room_code}          ← obrigatório
authenticated=true|false            ← (injetado pelo API Gateway após validação do JWT)
```

O Game Service deve registrar o mapeamento `player_id → sessão WebSocket` em memória local ao receber o CONNECT.
Se o estado da sala for `FINISHED` no momento do CONNECT, o servidor envia imediatamente um `game_over` com o ranking final ao cliente reconectado.

### 3.2 Tópico de recebimento — Servidor → Cliente

O cliente se inscreve em:

```
/topic/rooms/{room_code}
```

Todos os eventos do jogo são enviados como broadcast nesse tópico.

### 3.3 Destino de envio — Cliente → Servidor

O cliente envia respostas para:

```
/app/rooms/{room_code}/answer
```

### 3.4 Schemas das mensagens

#### Servidor → Cliente

**Jogador entrou na sala**
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

**Jogo iniciado**
```json
{
  "type": "game_started",
  "total_questions": 10,
  "theme": "science"
}
```

**Pergunta enviada**
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

**Resultado da rodada**
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

**Fim de partida**
```json
{
  "type": "game_over",
  "ranking": [
    { "player_id": "string", "player_name": "string", "total_score": 47, "position": 1 }
  ]
}
```

**Erro**
```json
{
  "type": "error",
  "code": "ROOM_NOT_FOUND",
  "message": "string"
}
```

#### Cliente → Servidor

**Resposta do jogador**
```json
{
  "type": "answer",
  "question_id": "uuid",
  "option": "b"
}
```
>**Nota 1:** Ao receber o CONNECT de um jogador, o servidor envia um evento `player_joined` para todos os inscritos no tópico da sala, incluindo o próprio jogador que acabou de conectar
> **Nota 2:**: `game_started` é enviado como broadcast para todos os jogadores inscritos no tópico, incluindo o criador, imediatamente após a transição de estado para `IN_PROGRESS` no Redis
> **Nota 3:** O `player_id` do respondente (mensagem answer) é obtido do mapeamento em memória `player_id → sessão WebSocket` registrado no CONNECT, não do corpo da mensagem.
---

## 4. Interface Kafka — Game Service → Kafka (Produtor)

O Game Service publica um único tipo de evento ao término de cada partida.

| Atributo | Valor |
|---|---|
| **Tópico** | `game-finished` |
| **Chave de partição** | `room_code` |
| **Quando publicar** | Ao término da partida, em paralelo com o broadcast `game_over` via WebSocket |
| **Configuração do producer** | `acks=all` |
| **Serialização** | JSON |

### Schema da mensagem

```json
{
  "room_code": "ABC123",
  "finished_at": "2026-06-18T14:32:00Z",
  "theme": "science",
  "num_questions": 10,
  "results": [
    {
      "player_id": "uuid-cadastrado",
      "player_name": "João",
      "is_anonymous": false,
      "score": 47,
      "position": 1,
      "won": true
    },
    {
      "player_id": "anon:f3a2c1",
      "player_name": "Visitante",
      "is_anonymous": true,
      "score": 31,
      "position": 2,
      "won": false
    }
  ]
}
```

> `won: true` deve ser atribuído exclusivamente ao jogador em `position: 1`.  
> Jogadores anônimos têm `player_id` prefixado com `anon:`.

---

## 5. Interface Redis — Game Service ↔ Redis

O Redis é o state store das salas ativas. O Game Service opera sempre sobre o nó **master**.

- **Porta:** `6379`
- **Cliente:** Lettuce (via Spring Data Redis)

### 5.1 Estrutura de chaves

| Chave | Tipo Redis | Descrição |
|---|---|---|
| `room:{code}:state` | Hash | Configuração e status da sala |
| `room:{code}:players` | Hash | Placar acumulado dos jogadores |
| `room:{code}:round:{idx}:answers` | Hash | Respostas corretas da rodada em andamento |
| `room:{code}:broadcast` | Pub/Sub channel | Broadcast entre instâncias do Game Service |

### 5.2 Hash `room:{code}:state`

| Campo | Tipo | Descrição |
|---|---|---|
| `status` | string | `WAITING`, `IN_PROGRESS` ou `FINISHED` |
| `creator_id` | string | `player_id` do criador da sala |
| `max_players` | int | Limite de jogadores configurado na criação |
| `num_questions` | int | Quantidade de perguntas configurada na criação |
| `theme` | string | Tema atual da partida |
| `current_question_idx` | int | Índice da pergunta em andamento (base 0) |
| `question_ids` | string | IDs das perguntas separados por vírgula, carregados no início da partida |

**TTL:** `3600` segundos a partir da última escrita. Salas abandonadas são limpas automaticamente.

### 5.3 Hash `room:{code}:players`

Mapeamento direto `player_id → score_acumulado (int)`.

Atualizado com `MULTI/EXEC` ao final de cada rodada para garantir atomicidade.

### 5.4 Pub/Sub `room:{code}:broadcast`

Utilizado para broadcast entre instâncias do Game Service. Quando uma instância precisa enviar uma mensagem para todos os jogadores de uma sala, incluindo os conectados a outras instâncias, ela publica nesse canal. Todas as instâncias assinam os canais das salas que possuem conexões ativas e repassam as mensagens via WebSocket aos seus clientes.

O payload publicado no canal é o mesmo JSON das mensagens WebSocket descritas na seção 3.4.

## 5.5 Hash `room:{code}:round:{idx}:answers` 
 
Registra as respostas corretas recebidas durante a rodada de índice `{idx}` (base 0). Cada campo é o `player_id` de um jogador que acertou; o valor é o timestamp ISO 8601 do instante em que a resposta correta chegou ao servidor.
 
| Campo | Tipo | Descrição |
|---|---|---|
| `{player_id}` | string (timestamp ISO 8601) | Instante de chegada da resposta correta |
 
**TTL:** mesmo TTL da sala (`GAME_ROOM_TTL_SECONDS`).
 
### Por que essa chave existe
 
Com múltiplas instâncias do Game Service e sticky session por IP do cliente, jogadores da mesma sala podem estar conectados a instâncias diferentes. Um `ConcurrentHashMap` local a cada instância não seria visível pelas demais, cada instância teria uma visão parcial das respostas da rodada, resultando em cálculo de créditos incorreto.
 
Ao centralizar as respostas no Redis, qualquer instância que registre uma resposta correta a torna imediatamente visível para todas as outras. A instância condutora da rodada (a que chamou `StartGame` ou `RestartGame`) lê o estado completo do Redis ao encerrar a rodada e calcula os créditos com base em todas as respostas recebidas.
 
### Operação de registro de resposta correta
 
Ao receber uma resposta correta de um jogador, a instância executa:
 
```
HSETNX room:{code}:round:{idx}:answers {player_id} {timestamp}
```
 
`HSETNX` é atômico e só escreve se o campo ainda não existe, garante que um jogador que envie múltiplas respostas (acidentalmente ou não) seja registrado apenas uma vez, com o timestamp da primeira resposta correta. Não é necessário nenhum lock adicional.
 
### Operação de leitura ao encerrar a rodada
 
Ao expirar o timeout da rodada, a instância condutora executa:
 
```
HGETALL room:{code}:round:{idx}:answers
```
 
O resultado é ordenado por timestamp para determinar a posição de cada acertante. O cálculo de créditos segue o algoritmo descrito na seção 7.2. Após o cálculo, o placar é atualizado em `room:{code}:players` via `MULTI/EXEC` e o resultado é publicado no canal `room:{code}:broadcast`.
 
### Limpeza
 
A chave expira automaticamente pelo TTL da sala. Não é necessário apagá-la explicitamente ao avançar de rodada, o índice `{idx}` na chave garante que cada rodada usa seu próprio namespace isolado.

---

## 6. Interface Question Database — Game Service → PostgreSQL
 
O Game Service acessa o Question DB via JDBC somente no início de cada partida. Acesso exclusivamente de leitura.
 
O Question DB adota particionamento horizontal (sharding) entre duas instâncias PostgreSQL fisicamente separadas. Cada instância armazena um subconjunto disjunto de temas e possui seu próprio processo de banco de dados, sua própria conexão e seu próprio espaço em disco. O roteamento é implementado no Game Service por meio de uma tabela de mapeamento estática: ao receber o tema da sala, o serviço resolve o shard correspondente e abre a conexão com a instância correta. Ambos os shards compartilham o mesmo schema.
 
### 6.1 Schema esperado em cada shard
 
```sql
CREATE TABLE questions (
    id             UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    theme          TEXT    NOT NULL,
    language       TEXT    NOT NULL DEFAULT 'pt-BR',
    text           TEXT    NOT NULL,
    option_a       TEXT    NOT NULL,
    option_b       TEXT    NOT NULL,
    option_c       TEXT    NOT NULL,
    option_d       TEXT    NOT NULL,
    correct_option CHAR(1) NOT NULL CHECK (correct_option IN ('a', 'b', 'c', 'd'))
);
 
CREATE INDEX idx_questions_theme_language ON questions (theme, language);
```
 
### 6.2 Tabela de mapeamento estático — tema → shard
 
| Tema | Shard |
|---|---|
| `history` | Shard A |
| `science` | Shard A |
| `geography` | Shard A |
| `arts_and_literature` | Shard A |
| `society_and_culture` | Shard A |
| `music` | Shard B |
| `sport_and_leisure` | Shard B |
| `film_and_tv` | Shard B |
| `food_and_drink` | Shard B |
| `general_knowledge` | Shard B |
 
### 6.3 Query executada no início de cada partida
 
Executada sobre o shard resolvido pela tabela de mapeamento:
 
```sql
SELECT id, text, option_a, option_b, option_c, option_d, correct_option
FROM questions
WHERE theme = ?
ORDER BY RANDOM()
LIMIT ?
```
 
> O Game Service deve armazenar os IDs retornados no Redis e carregar os dados completos em memória para a sessão. **Não deve consultar o banco a cada rodada.**
 
### 6.4 Comportamento em caso de falha de shard
 
Se um shard ficar indisponível, o Game Service deve retornar erro `UNAVAILABLE` nas chamadas gRPC `CreateRoom` (campo `theme`) e `RestartGame` (campo `new_theme`) para temas pertencentes àquele shard. Partidas com temas do shard disponível continuam funcionando normalmente. A falha é isolada por partição e não se propaga para o acervo completo.
 
---

## 7. Regras de Negócio Internas

### 7.1 Máquina de estados da sala

```
       CreateRoom
           │
           ▼
        WAITING  ◄────────────────────────────────┐
           │                                       │
           │  StartGame                            │
           │  (criador, mín. 2 jogadores)          │
           ▼                                       │
      IN_PROGRESS                                  │
           │                                       │
           │  todas as perguntas respondidas        │
           ▼                                       │
        FINISHED                                   │
           │                                       │
           │  RestartGame (criador)                │
           └───────────────────────────────────────┘
```

Transições inválidas devem retornar `FAILED_PRECONDITION` no gRPC.

### 7.2 Algoritmo de distribuição de créditos

Cada pergunta possui um pool de **10 créditos**, distribuídos apenas entre os jogadores que acertaram, em ordem de chegada da resposta correta.

**Fórmula:**

```
N = número de jogadores que acertaram

peso da posição i (1 = mais rápido) = N - i + 1
soma_dos_pesos                       = N × (N + 1) / 2
créditos da posição i                = floor((peso_i / soma_dos_pesos) × 10)
```

Créditos residuais após o `floor` (diferença entre 10 e a soma calculada) são adicionados à posição 1.

**Exemplo com 3 acertantes:**

| Posição | Peso | Créditos calculados | Créditos finais |
|---|---|---|---|
| 1º | 3 | floor(3/6 × 10) = 5 | **6** (+1 residual) |
| 2º | 2 | floor(2/6 × 10) = 3 | **3** |
| 3º | 1 | floor(1/6 × 10) = 1 | **1** |
| **Total** | | **9** | **10** |

> Se nenhum jogador acertar, nenhum crédito é distribuído naquela rodada.

### 7.3 Requisitos de thread safety

O registro de respostas corretas é centralizado no Redis via `HSETNX`, que é atômico por natureza. Múltiplas threads podem chamar `HSETNX` concorrentemente para a mesma chave sem risco de duplicidade,  o Redis garante que apenas o primeiro write por `player_id` por rodada seja aceito. Não são necessários locks adicionais para esse fluxo.

O que requer estruturas thread-safe locais é o gerenciamento das sessões WebSocket dentro de cada instância:
-  `ConcurrentHashMap<String, WebSocketSession>` para o mapeamento `player_id → sessão WebSocket`. Conexões e desconexões ocorrem concorrentemente e precisam de acesso thread-safe a esse mapa.
  
O  `AtomicInteger` para contagem de acertos não é mais necessárioa fonte de verdade é o Redis. A instância condutora executa  `HGETALL room:{code}:round:{idx}:answers` ao encerrar a rodada e obtém o conjunto completo de respostas de todas as instâncias.
 
### 7.4 Timeout por rodada

Cada pergunta possui tempo limite configurável via variável de ambiente. Ao expirar, o Game Service processa as respostas recebidas até aquele momento e avança para o resultado da rodada, mesmo que nem todos os jogadores tenham respondido.

---

## 8. Stack Tecnológica

| Componente | Tecnologia |
|---|---|
| Linguagem | Java 21 |
| Framework | Spring Boot 3.x |
| Servidor gRPC | `grpc-spring-boot-starter` (LogNet) + `grpc-java` |
| WebSocket | Spring WebSocket com STOMP (`spring-boot-starter-websocket`) |
| Kafka producer | `spring-kafka` |
| Redis client | Spring Data Redis com Lettuce (`spring-boot-starter-data-redis`) |
| JDBC | `spring-boot-starter-jdbc` + driver PostgreSQL |
| Build | Maven ou Gradle |

---
 
## 9. Variáveis de Configuração
 
```yaml
server:
  port: 8080
 
grpc:
  server:
    port: 9090
 
spring:
  datasource:
    shard-a:
      url: jdbc:postgresql://${DB_SHARD_A_HOST}:${DB_SHARD_A_PORT}/${DB_SHARD_A_NAME}
      username: ${DB_SHARD_A_USER}
      password: ${DB_SHARD_A_PASS}
      # temas: history, science, geography, arts_and_literature, society_and_culture
 
    shard-b:
      url: jdbc:postgresql://${DB_SHARD_B_HOST}:${DB_SHARD_B_PORT}/${DB_SHARD_B_NAME}
      username: ${DB_SHARD_B_USER}
      password: ${DB_SHARD_B_PASS}
      # temas: music, sport_and_leisure, film_and_tv, food_and_drink, general_knowledge
 
  data:
    redis:
      host: ${REDIS_HOST}
      port: ${REDIS_PORT}
 
  kafka:
    bootstrap-servers: ${KAFKA_BROKERS}
    producer:
      acks: all
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.springframework.kafka.support.serializer.JsonSerializer
 
game:
  question-timeout-ms: ${GAME_QUESTION_TIMEOUT_MS}
  room-ttl-seconds: ${GAME_ROOM_TTL_SECONDS}
```

> As portas `8080` e `9090` são portas **internas do container**. Em ambiente Docker/AWS, a exposição externa é gerenciada pela infraestrutura (ALB + Docker network) e não impacta este contrato.

---

## 10. Restrições

O Game Service **não deve**:

- Validar JWT — responsabilidade do API Gateway, que injeta o `player-id` já identificado
- Chamar o User Service diretamente — a comunicação com o serviço de usuários é exclusivamente via Kafka
- Persistir estatísticas de usuários — responsabilidade do User Service ao consumir o evento Kafka
- Inserir ou alterar perguntas no banco de dados
