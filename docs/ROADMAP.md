# Roadmap técnico Oryven — revisão 0.5

- **0.1–0.2, base local:** FastAPI, React/Tauri inicial, Vosk, ElevenLabs opcional, pesquisa aprovada, três aplicativos permitidos.
- **0.3, Missions:** planejador por regras para até três ações conhecidas, aprovação por etapa, verificação humana e persistência SQLite.
- **0.4, inspeção:** UI Automation superficial em Windows, Playwright para sites públicos, conector Buno health/chat opt-in.
- **0.5, atuação UIA limitada:** foco de janela e InvokePattern de Maximizar/Restaurar/Minimizar, com pré-visualização, identidade presa e verificação de estado, testes simulados.
- **0.6 (planejado):** E2E Windows, hardening de sessão desktop, ações reversíveis no Playwright, provedores Buno estruturados com políticas locais.
- **0.7+ (planejado):** Oryven Developer (VS Code/Git) e Studio (Maya Python/MEL em cópia de cena) por skills específicas com revisão humana.
- **Comercialização (futura):** sidecar empacotado, IPC autenticado, instalador assinado, logs seguros, contas e billing, compatibilidade multi-dispositivo.

**Definição de pronto:** evidência de testes por sistema operacional, escopo de permissão, pós-condição comprovável, modo de falha explícito, rollback quando aplicável e transparência de custos.

## 0.8.0 — Professional Agents Foundation

- 32 professional profiles + universal fallback.
- Deterministic local domain routing.
- API for agent catalog and professional task planning.
- No permission escalation from agent selection.
- Next: real shared skill packs (files, supervised terminal, Office, Maya, browser actions) and voice/Tauri/accounts.


## 0.15.0 — Supervised Autonomous Mission Orchestrator
Planejamento adaptativo, verificação e recuperação supervisionada entre skills/agentes, sem ampliar permissões.
