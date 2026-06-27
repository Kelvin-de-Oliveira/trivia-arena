# Trivia Arena - Game Service

Servico central de partidas. Expoe gRPC em `9090`, WebSocket/STOMP em `8080`,
mantem salas no Redis, le perguntas dos shards PostgreSQL e publica o resultado
final no topico Kafka `game-finished`.

## Pre-requisitos

- Docker e Docker Compose
- Java 21
- Maven 3.9+

> O `pom.xml` usa Java 21. Se `mvn -version` apontar para Java 11 ou 8,
> configure `JAVA_HOME` para um JDK 21 antes de rodar a aplicacao.

## Subir dependencias locais

Execute a infraestrutura a partir da raiz do repositorio:

```powershell
cd C:\Users\hugo.santos\Desktop\Faculdade\trivia-arena\infra
Copy-Item .env.example .env
docker compose --env-file .env up -d
```

Servicos uteis:

- Redis Commander: `http://localhost:8091`
- Kafka UI: `http://localhost:8090`
- Redis: `localhost:6379`
- Kafka: `localhost:9092`
- Question DB Shard A: `localhost:5432`
- Question DB Shard B: `localhost:5433`

## Rodar o Game Service

```powershell
cd C:\Users\hugo.santos\Desktop\Faculdade\trivia-arena\game-service\trivia-game-service
Copy-Item .env.example .env
Get-Content .env | Where-Object { $_ -and $_ -notmatch '^#' } | ForEach-Object { $k,$v = $_ -split '=',2; Set-Item "Env:$k" $v }
mvn spring-boot:run
```

Portas expostas localmente:

- HTTP/WebSocket STOMP: `localhost:8080/ws`
- gRPC: `localhost:9090`

## Validar gRPC

Com o servico rodando:

```powershell
grpcurl -plaintext localhost:9090 list trivia.game.v1.GameService
```

Criar sala:

```powershell
grpcurl -plaintext -d "{`"creator_id`":`"player-001`",`"creator_name`":`"Ana`",`"is_anonymous`":false,`"max_players`":2,`"num_questions`":5,`"theme`":`"science`"}" localhost:9090 trivia.game.v1.GameService/CreateRoom
```

Entrar na sala:

```powershell
grpcurl -plaintext -d "{`"room_code`":`"ABC123`",`"player_id`":`"player-002`",`"player_name`":`"Bruno`",`"is_anonymous`":false}" localhost:9090 trivia.game.v1.GameService/JoinRoom
```

Consultar sala:

```powershell
grpcurl -plaintext -d "{`"room_code`":`"ABC123`"}" localhost:9090 trivia.game.v1.GameService/GetRoom
```

Iniciar partida:

```powershell
grpcurl -plaintext -d "{`"room_code`":`"ABC123`",`"requester_id`":`"player-001`"}" localhost:9090 trivia.game.v1.GameService/StartGame
```

Substitua `ABC123` pelo `room_code` retornado em `CreateRoom`.

## Testes

```powershell
mvn -DskipTests compile
mvn test
```

Os testes de Redis usam Testcontainers e sao ignorados automaticamente quando
Docker nao esta disponivel.

## Observacoes locais

O seed da infraestrutura possui 5 perguntas por tema. Em ambiente local, crie
salas com `num_questions=5`; valores maiores so funcionam depois de carregar
mais perguntas no shard correspondente.

O evento Kafka publicado no fim da partida segue o contrato do Game Service:
`room_code`, `finished_at`, `theme`, `num_questions` e `results`.
