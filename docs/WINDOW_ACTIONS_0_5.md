# Oryven Computer Control 0.5 — Protocolo de atuação segura

## Componentes

- `backend/oryven/window_actions.py`: adaptação UI Automation (Windows); somente foco e InvokePattern de três botões de janela.
- `backend/oryven/computer_control.py`: exposição da árvore UIA superficial com `path` e `eligible_action`; continua omitindo campos Edit/Document/Password.
- `backend/oryven/models.py`: intenções tipadas `computer.window.focus` e `computer.button.invoke`.
- `backend/oryven/governance.py`: hash SHA-256 do **modelo de intenção inteiro**, inclusive janela e caminho do controle, além de TTL de 120 segundos.
- `backend/oryven/api.py`: propostas autenticadas por token de desenvolvimento, mesma etapa de aprovação existente.
- `web/src/App.tsx`: botões para solicitar foco, solicitar ação elegível e observar a verificação.

## Contrato de segurança

1. Nenhuma leitura de janela/ação inicia automaticamente por comando de modelo Buno; o usuário solicita pela interface e aprova uma vez.
2. A proposta prende `HWND`, `process_id`, `window_class`, `window_title`, `path` e, para botões, `button_name`, `button_automation_id`.
3. A ação resolve novamente a janela visível pelo HWND, compara identidade e percorre o **caminho UIA** até profundidade 2 (no máximo 25 filhos por nível); a árvore deve continuar expondo o botão no limite de 50 nós.
4. Somente controles do tipo `Button`, visíveis, habilitados e com nome exatamente `Maximize/Maximizar`, `Minimize/Minimizar` ou `Restore/Restaurar` podem ser invocados. Rótulos desconhecidos, Edit, Document, Password, OK, Enviar, Comprar, Excluir ou Confirmar não podem ser executados.
5. `button.invoke()` aplica o padrão UI Automation InvokePattern; **não** usa posição de mouse, `click_input`, teclado ou PowerShell.
6. A verificação consulta o `WindowPattern` antes/depois (`get_show_state`: 0 normal, 1 maximizada, 2 minimizada) e `is_active()` para foco. **Resposta de API não é prova de sucesso quando `verified=false`.**
7. A aprovação é consumida uma única vez; não há repetição automática em caso de resultado incerto.
8. O registro de auditoria armazena tipo, status e ID da aprovação, sem gravar títulos de janelas, ID/nome dos botões ou árvore UIA. A interface poderá exibir títulos (potencialmente privados) durante a sessão.

## Endpoints adicionados em 0.5

- `POST /api/control/window/focus/propose` com `{"handle":7331}` → `{pending:{...}}`.
- `POST /api/control/window/button/propose` com `{"handle":7331,"path":[0,2]}` → `{pending:{...}}`.
- `POST /api/actions/{id}/decision` com `{"decision":"approve"}` → `outcome: verified | unverified | failed` e `data` efêmero.

Os endpoints exigem `X-Oryven-Session` e origem local autorizada; ainda não há autenticação forte nem isolamento de processos locais. Nunca expor o servidor via túnel ou IP externo.

## O que demonstrar no Windows

1. Executar `run-control-tests.ps1`. Os testes automatizados **não** acessam o desktop.
2. Iniciar Oryven, abrir Notepad e inspecionar a janela.
3. Pedir foco, verificar que `verified: true` significa que UIA identificou a janela ativa.
4. Se o botão Maximizar estiver visível no nível inspecionado, solicitar sua invocação, aprovar e verificar resultado na própria janela.
5. Alterar título, fechar janela ou trocar controle entre proposta e aprovação: a execução deve falhar, sem tentar adivinhar outra janela.
6. Negar e usar Parada de emergência; confirmar que ações pendentes não executam.
7. Medir latência, acessibilidade da janela, divergências entre Windows 10/11 e casos em que `InvokePattern` não existe. Registrar resultados manualmente antes de alegar compatibilidade.

## Limitações e riscos residuais

- UIA não garante acesso consistente em todos os apps; janelas de integridade elevada/UAC e desktops protegidos não são contornados.
- PID, HWND, título, classe e automação não são uma barreira criptográfica contra malware no mesmo usuário; são validações defensivas de intenção e contexto. Um aplicativo hostil pode fornecer metadados enganosos.
- Uma chamada UIA síncrona pode travar; o Stop não cancela uma chamada já invocada. O `pywinauto.invoke` pode retornar após timeout interno, por isso a pós-condição exige estado verificado e não é repetida automaticamente.
- A árvore superficial pode não conter controles da barra de título de alguns aplicativos. Nesses casos, Oryven informa a limitação. Não há fallback automático para cliques com mouse.
- O modelo Buno, ElevenLabs, Playwright e Oryven Missions não ganham permissão automática para essas ações. Cada habilidade nova exigirá revisão de contrato e testes.

## Próximo marco possível 0.6

Controle Playwright com ações não destrutivas explicitamente escopadas, verificação DOM antes/depois e bloqueio de navegações POST/cookies pessoais. Integração Buno somente como planejador que devolve intenções tipadas, sempre sujeitas ao verificador local. Primeiro realizar E2E real de UIA 0.5.
