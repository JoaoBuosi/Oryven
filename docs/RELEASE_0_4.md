# Oryven Computer Control — Relatório de release 0.4

**Implementado no código:** Windows UIA read-only, Playwright public-page inspection, Buno health+chat opt-in, manifests declarativos, UI de controle, aprovações específicas, testes automatizados, scripts de setup e documentação.

**Validação no ambiente de construção:** 45 testes pytest passaram (Linux, com simulações de UIA/Playwright/Buno); sintaxe TSX verificada pelo parser TypeScript; 10 JSON validados; suíte pytest backend executada com fakes para UIA e Playwright, transportes httpx para Buno; ver `backend/tests/test_computer_control.py`. `compileall`/integridade ZIP executados na preparação do pacote. O teste com Chromium real e Windows não foi feito neste ambiente Linux.

**Não validado:** interface React/Tauri compilada, latência de controle de janelas do Windows, microfone Vosk, chamada real ElevenLabs, Buno local real, Chromium Playwright em Windows e instalador comercial.

**Não implementado:** clique e preenchimento UIA, inspeção de screenshots, controle remoto, orquestração dinâmica de agentes, criação de tarefas por LLM ou execução de código/PowerShell.

Os recursos anteriores de voz, pesquisa no navegador e missões são preservados do MVP 0.3, sem modificações dos repositórios Buno ou Flow Commerce.

**Frontend:** `npm install --offline` falhou por cache não disponível para `@tauri-apps/cli`; nenhum build do React/Tauri foi realizado ou alegado.
