# Oryven Missions 0.3 — especificação executável

## Escopo presente

O MVP **não usa LLM para decidir ferramentas**. O parser produz somente `browser.search` e `app.launch` para notepad, calculator, explorer. Aceita 1–3 etapas explícitas, sem executar o resto se alguma etapa for desconhecida. Nunca há shell, arquivos, Git ou rede arbitrária.

## Fluxo e garantias

1. `POST /api/missions` com texto de até 500 caracteres cria plano persistido no arquivo `missions.sqlite3`.
2. O primeiro passo tem autorização de alvo exato com prazo de 120 s e uso único; negar cancela a missão.
3. Autorizar despacha a ação para o SO/navegador. Isso **não comprova que ocorreu**.
4. A missão fica em `awaiting_verification`; o usuário marca se viu o resultado. Se confirmou, o próximo passo recebe **nova** autorização. Se não confirmou, missão falha.
5. Após todas as confirmações, a missão termina `completed`, ou seja **confirmada pelo usuário**, nunca comprovada por telemetria.
6. `POST /api/stop` invalida aprovações ainda não usadas, desliga microfone e coloca missões aguardando autorização em `paused`. Ações já despachadas não são revertidas.
7. Reiniciar a API invalida autorizações de memória e transforma missões não despachadas em `paused`. Se o processo foi interrompido entre autorização e registro do resultado, marca `needs_review`, **sem repetição automática**.
8. Histórico de missões terminais pode ser excluído com `DELETE /api/missions/{id}` (controle local de privacidade); auditoria mínima é armazenada separadamente.

## Endpoints (todos menos /api/health e /api/session exigem sessão local)

| Rota | Função |
|---|---|
| `POST /api/missions` | Cria plano `{ "text": "Abra a calculadora e depois abra o bloco de notas" }` |
| `GET /api/missions` | Lista missões recentes |
| `GET /api/missions/{id}` | Lê status e etapas |
| `POST /api/actions/{action_id}/decision` | Aprova ou nega a etapa individual |
| `POST /api/missions/{id}/verify` | Confirma observação manual: `{ "confirmed": true }` |
| `POST /api/missions/{id}/resume` | Reemite a autorização após pausa |
| `POST /api/missions/{id}/cancel` | Cancela o que ainda não foi executado |
| `DELETE /api/missions/{id}` | Exclui histórico de missão terminal |

## Exemplos de comandos

- `Abra o navegador e pesquise inteligência artificial` — 1 ação.
- `Abra a calculadora e depois abra o bloco de notas` — 2 ações.
- `Pesquise inteligência artificial e depois abra a calculadora` — 2 ações.
- `Abra o PowerShell e delete arquivos` — recusado integralmente.

## Prontos para futura versão

- Objetos de estado e eventos para a UI, logs e futura integração de LLM através de contrato tipado.
- Próxima fase deve introduzir verificação de DOM/janelas com testes e captura de evidência consentida, não substituir silenciosamente `confirmed` por `completed`.
- Para usar com múltiplos usuários, será obrigatória autenticação do processo Tauri/sidecar e autorização por usuário. API atual não é comercial.
