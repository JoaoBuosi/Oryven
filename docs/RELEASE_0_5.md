# Relatório de release — Oryven Computer Control 0.5

## Mudanças entregues

- Modelo de intenção `computer.window.focus`: proposta vinculada à identidade real da janela (HWND, PID, título, hash do título completo, classe), decisão com TTL de 120 segundos, execução `set_focus()` e verificação `is_active()`.
- Modelo de intenção `computer.button.invoke`: proposta por caminho visível na árvore UIA, restrita a `Maximize`, `Maximizar`, `Minimize`, `Minimizar`, `Restore`, `Restaurar`. Compara janela e botão novamente no momento do despacho; usa `InvokePattern` sem mouse ou teclado.
- Confere `get_show_state()` antes/depois; apenas reporta sucesso quando o estado esperado é observado. Não repete ações automaticamente após falha ou incerteza.
- UI de pedido de foco, botões elegíveis, aprovação de uso único, exibição de resultado confirmado/não confirmado.
- Manifests declarativos registrados para as duas novas skills, sem execução dinâmica por catálogo.
- Integração preservada com voz ElevenLabs/Vosk, Oryven Missions, Playwright leitura e Buno chat opt-in.
- Documentos e scripts atualizados para testes no Windows.

## Evidências coletadas neste ambiente

- **65/65 testes do backend** com `PYTHONPATH=backend python -m pytest backend/tests -q` — passaram.
- Cenários: aprovação e expiração; uma única invocação; recusa de botões perigosos; caminho UIA inválido; janela ou controle alterado; Stop; verificação de estado; foco; erro controlado fora do Windows; API; regressão das versões anteriores.
- **TSX:** transpilation de sintaxe com TypeScript global sem diagnósticos de parsing.
- **JSON/skills:** todos os manifests declarativos válidos ao validador Pydantic e os dois novos itens aparecem no catálogo.

## Ainda não validado

- Windows 10/11 real: pywinauto instalado, árvore UIA de Notepad/Calculadora, WindowPattern disponível, `InvokePattern` de botões reais, tempo e estabilidade.
- Compilação React/Vite/Tauri: o ambiente não contém `node_modules`, então `npm run build` falhou porque `react`, `lucide-react` e os respectivos tipos não estão instalados. O parse TSX **não é** teste de build.
- ElevenLabs e Vosk usando chave/modelo/microfone reais, Chromium Playwright, conexão Buno com JWT; estes recursos são herdados das versões anteriores, sem nova validação E2E.
- Segurança de produção; o endpoint de bootstrap local ainda não é autenticação comercial. Não existe instalador standalone.

## Dependências, custos e riscos

- Python 3.11; `pywinauto` (somente Windows) via `requirements-control.txt`; FastAPI, pytest; Node 20+, React/Vite/Tauri; Windows com WebView2 e ferramentas Rust para desktop; Chromium instalado para Playwright.
- As novas ações UIA não exigem API paga e não usam token LLM. ElevenLabs e Buno podem ter custos conforme uso/plano, não estimados neste release.
- A execução UIA síncrona pode bloquear; Stop revoga aprovações não consumidas, mas não cancela garantidamente ação já enviada.
- A identidade UIA não impede aplicativos hostis no mesmo usuário de expor metadados enganadores.

## Gate de release posterior

Antes de habilitar novos botões, confirmar resultados de E2E Windows. Separar perfis e permissões mais fortes para clicar em menus, preencher formulários, trabalhar com arquivos ou usar terminal. O primeiro MVP comercial exige autenticação forte do processo local e instalador assinado.
