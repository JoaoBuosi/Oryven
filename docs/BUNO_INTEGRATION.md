# Conexão Oryven ↔ Buno AI — contrato 0.4

## Contrato observado no repositório Buno

- `GET /api/v1/health`: retorna dados de status (`api`: `ok` no código observado).
- `POST /api/v1/chat/stream`: recebe `{"message":"texto"}` e exige JWT no header `Authorization: Bearer ...`.
- Eventos SSE conhecidos: `start`, `status`, `chunk` com `{"text":"..."}`, `error`, `done`.
- A API Buno **armazena mensagens** e pode criar memórias, conforme o código de `chat.py` verificado.

## Implementação

Em `backend/oryven/buno_bridge.py`, `BunoHealthBridge` faz requests HTTP apenas ao loopback configurado por `ORYVEN_BUNO_API_URL`. `check()` não manda token; `chat()` exige `ORYVEN_BUNO_BEARER_TOKEN` e só pode ser chamado pelo gateway após o consumo de uma aprovação de uso único.

O Oryven não envia automaticamente capturas de tela, arquivos, dados UIA, histórico, prompts ocultos nem chaves ElevenLabs à Buno. A resposta é texto não confiável e não é transformada em chamada de ferramenta. A API Oryven não disponibiliza execução genérica a respostas do modelo.

**A integração foi validada por testes com transportes simulados, não contra seu servidor real.** Mudanças no contrato de autenticação/chat do Buno local exigirão atualização do adaptador.

## Segurança

JWT em `.env` é apenas solução temporária de desenvolvimento. Não comite, compartilhe ou registre o arquivo `.env`. Para distribuição comercial: conta própria por usuário, armazenamento seguro do token, refresh com escopos, revogação, TLS para servidores remotos e consentimento explícito para dados sensíveis.
