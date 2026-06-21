# Infraestrutura Local — TriviaArena

> **Versão:** 2.0
>
> **Responsável:** Kelvin
>
> Esta infraestrutura atende ao desenvolvimento de todos os componentes do sistema: Game Service, User Service e API Gateway.

---

## Pré-requisitos

- Docker
- Docker Compose

## Estrutura

```
trivia-infra/
├── docker-compose.yml
├── .env.example
└── init/
    ├── shard-a/
    │   ├── 01_schema.sql
    │   └── 02_seed.sql
    ├── shard-b/
    │   ├── 01_schema.sql
    │   └── 02_seed.sql
    └── userdb/
        └── 01_schema.sql
```

## Como subir

```bash
cp .env.example .env
docker-compose up -d
```

## Serviços e portas

| Serviço | Porta | Descrição |
|---|---|---|
| Redis | 6379 | Game state cache |
| Redis Commander | 8091 | UI web para inspeção das chaves do Redis |
| db-shard-a | 5432 | Question DB — Shard A |
| db-shard-b | 5433 | Question DB — Shard B |
| db-user-primary | 5434 | User DB — instância primária (escrita) |
| db-user-replica | 5435 | User DB — instância réplica (leitura) |
| Kafka | 9092 | Broker (acesso externo via host) |
| Kafka UI | 8090 | UI web para inspeção de tópicos e mensagens |

## Particionamento dos temas

| Shard | Banco | Temas |
|---|---|---|
| Shard A | questions_shard_a | `history`, `science`, `geography`, `arts_and_literature`, `society_and_culture` |
| Shard B | questions_shard_b | `music`, `sport_and_leisure`, `film_and_tv`, `food_and_drink`, `general_knowledge` |

O Game Service resolve o shard em runtime via tabela de mapeamento estática.
Se um shard estiver indisponível, apenas os temas daquele shard são afetados.

## Ferramentas de debug

### Redis Commander — http://localhost:8091

Permite inspecionar todas as chaves do Redis em tempo real. Útil para acompanhar:

- `room:{code}:state` — configuração e status da sala
- `room:{code}:players` — placar acumulado
- `room:{code}:round:{idx}:answers` — respostas corretas da rodada em andamento

### Kafka UI — http://localhost:8090

Permite inspecionar tópicos, partições e mensagens. Útil para validar:

- Tópico `game-finished` — eventos publicados ao fim de cada partida

## Acesso aos bancos via psql

```bash
# Question DB — Shard A
docker exec -it trivia-db-shard-a psql -U trivia -d questions_shard_a

# Question DB — Shard B
docker exec -it trivia-db-shard-b psql -U trivia -d questions_shard_b

# User DB — Primário
docker exec -it trivia-db-user-primary psql -U trivia -d trivia_users

# User DB — Réplica
docker exec -it trivia-db-user-replica psql -U trivia -d trivia_users
```

## Parar os serviços

```bash
docker-compose down       # mantém volumes (dados persistem)
docker-compose down -v    # remove volumes (dados apagados)
```

---

## Testando a interface gRPC sem o API Gateway

Durante o desenvolvimento do Game Service, o API Gateway não está disponível no compose local. Para chamar os RPCs diretamente e validar o comportamento, use uma das opções abaixo.

### grpcurl (linha de comando)

Instale o grpcurl: https://github.com/fullstorydev/grpcurl#installation

O Game Service deve estar rodando localmente na porta `9090`. Os exemplos abaixo cobrem o fluxo completo de uma partida.

**Criar sala:**
```bash
grpcurl -plaintext \
  -d '{
    "creator_id": "player-001",
    "creator_name": "Ana",
    "is_anonymous": false,
    "max_players": 2,
    "num_questions": 5,
    "theme": "science"
  }' \
  localhost:9090 trivia.game.v1.GameService/CreateRoom
```

**Entrar na sala (segundo jogador):**
```bash
grpcurl -plaintext \
  -d '{
    "room_code": "XXXXX",
    "player_id": "player-002",
    "player_name": "Bruno",
    "is_anonymous": false
  }' \
  localhost:9090 trivia.game.v1.GameService/JoinRoom
```

**Consultar estado da sala:**
```bash
grpcurl -plaintext \
  -d '{"room_code": "XXXXX"}' \
  localhost:9090 trivia.game.v1.GameService/GetRoom
```

**Iniciar partida (apenas o criador pode):**
```bash
grpcurl -plaintext \
  -d '{
    "room_code": "XXXXX",
    "requester_id": "player-001"
  }' \
  localhost:9090 trivia.game.v1.GameService/StartGame
```

**Reiniciar partida com novo tema:**
```bash
grpcurl -plaintext \
  -d '{
    "room_code": "XXXXX",
    "requester_id": "player-001",
    "new_theme": "history"
  }' \
  localhost:9090 trivia.game.v1.GameService/RestartGame
```

> Substitua `XXXXX` pelo `room_code` retornado no `CreateRoom`.

**Listar todos os RPCs disponíveis (requer reflection ativa no serviço):**
```bash
grpcurl -plaintext localhost:9090 list trivia.game.v1.GameService
```

---

### Postman (interface gráfica)

O Postman suporta gRPC nativamente a partir da versão 10.

1. Abra o Postman e crie uma nova requisição do tipo **gRPC**
2. Informe o endereço: `localhost:9090`
3. Importe o arquivo `.proto` em **Import a .proto file** (use o arquivo `game_service.proto` do repositório do Game Service)
4. Selecione o método desejado (ex: `CreateRoom`) e preencha o body em JSON
5. Clique em **Invoke**

---

### Kreya (alternativa gráfica leve)

Download: https://kreya.app

1. Crie um novo projeto e importe o `.proto`
2. Configure o endpoint `localhost:9090` (plaintext, sem TLS)
3. Execute os RPCs diretamente pela interface

---

### Testando o WebSocket (respostas durante a partida)

Após iniciar uma partida via gRPC, conecte-se ao WebSocket para simular um jogador respondendo. Use o **websocat** (linha de comando) ou o **Postman**.

**Instalar websocat:** https://github.com/vi/websocat#installation

```bash
# Conectar como jogador (STOMP sobre WebSocket)
websocat ws://localhost:8080/ws
```

Após conectar, envie o frame STOMP de CONNECT:
```
CONNECT
player-id:player-001
room-code:XXXXX
accept-version:1.2

^@
```

Inscreva-se no tópico da sala:
```
SUBSCRIBE
id:sub-0
destination:/topic/rooms/XXXXX

^@
```

Envie uma resposta:
```
SEND
destination:/app/rooms/XXXXX/answer
content-type:application/json

{"type":"answer","question_id":"uuid-da-pergunta","option":"b"}
^@
```

> `^@` representa o caractere nulo (null byte), delimitador de frame STOMP. No websocat, pressione `Ctrl+@` ou envie `\0`.

---

### Validando os efeitos colaterais

Após executar os RPCs, confirme os efeitos esperados nas ferramentas de debug:

| O que verificar | Onde |
|---|---|
| Chaves `room:{code}:state` e `room:{code}:players` criadas | Redis Commander — http://localhost:8091 |
| Chave `room:{code}:round:{idx}:answers` populada durante a rodada | Redis Commander — http://localhost:8091 |
| Evento `game-finished` publicado ao encerrar a partida | Kafka UI — http://localhost:8090 → tópico `game-finished` |

---

## Conflito de portas com serviços locais

As portas abaixo são padrão de seus respectivos serviços. Se você tiver qualquer um deles rodando localmente (instalação nativa, não Docker), o `docker-compose up` vai falhar com `bind: address already in use`.

| Porta | Serviço no compose | Conflito comum |
|---|---|---|
| `5432` | db-shard-a | PostgreSQL instalado localmente |
| `5433` | db-shard-b | Outro PostgreSQL local na porta 5433 |
| `5434` | db-user-primary | Outro PostgreSQL local na porta 5434 |
| `5435` | db-user-replica | Outro PostgreSQL local na porta 5435 |
| `6379` | Redis | Redis instalado localmente |
| `9092` | Kafka | Kafka local |

**Solução rápida — parar os serviços locais antes de subir o compose:**

```bash
# macOS / Linux — parar PostgreSQL
brew services stop postgresql   # Homebrew
sudo systemctl stop postgresql  # systemd

# macOS / Linux — parar Redis
brew services stop redis
sudo systemctl stop redis
```

**Solução alternativa — mudar as portas do host no docker-compose.yml:**

Se preferir manter os serviços locais rodando, altere apenas o lado esquerdo do mapeamento de portas (host:container). Basta atualizar os valores correspondentes no `.env` também.

```yaml
# Exemplo: mover shard-a para a porta 5436 no host
db-shard-a:
  ports:
    - "5436:5432"   # era 5432:5432
```

```env
# .env — atualizar a porta correspondente
DB_SHARD_A_PORT=5436
```

---

## Dados de teste — limitação e como expandir

O seed atual possui **5 perguntas por tema**. Isso cobre apenas partidas com `num_questions = 5` (o mínimo). Para testar com valores maiores, adicione mais perguntas diretamente no banco:

```bash
# Acessar o shard desejado
docker exec -it trivia-db-shard-a psql -U trivia -d questions_shard_a

# Inserir novas perguntas
INSERT INTO questions (theme, language, text, option_a, option_b, option_c, option_d, correct_option)
VALUES ('science', 'pt-BR', 'Sua pergunta aqui?', 'Op A', 'Op B', 'Op C', 'Op D', 'b');
```

Para temas do Shard B, substitua `trivia-db-shard-a` por `trivia-db-shard-b` e `questions_shard_a` por `questions_shard_b`. Recomenda-se ter no mínimo **20 perguntas por tema** para cobrir o limite máximo de `num_questions`.