# Trivia Arena — Game Service

Serviço central de partidas: expõe gRPC na porta `9090`, WebSocket/STOMP na porta
`8080`, mantém salas no Redis, lê perguntas dos shards PostgreSQL e publica o
resultado final no tópico Kafka `game-finished`.

## Executar localmente

1. Suba as dependências em `../trivia-infra` com `docker compose up -d`.
2. Copie `.env.example` para `.env` e carregue as variáveis no seu shell.
3. Com Java 21 e Maven instalados, execute `mvn spring-boot:run`.

O seed da infraestrutura contém cinco perguntas por tema. Por isso, em ambiente
local uma sala deve ser criada com `num_questions=5`; configurações maiores são
rejeitadas no início da partida até que novas perguntas sejam carregadas.

## Testes

Execute `mvn test` para os testes unitários e de integração Redis. Os testes de
integração usam Testcontainers e são ignorados automaticamente quando Docker não
está disponível; os demais cenários podem ser exercitados com o compose fornecido.

## Reconexão STOMP

Além do tópico público `/topic/rooms/{roomCode}`, o cliente deve assinar
`/user/queue/rooms/{roomCode}`. Depois dessa assinatura, uma reconexão durante
uma rodada recebe a pergunta em andamento com `remaining_time_ms`.
