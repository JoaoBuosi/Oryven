## Oryven 0.11.3 - Professional Packs

Veja `docs/RELEASE_0_11_3_PROFESSIONAL_PACKS.md`. Instale também `requirements-professional.txt` para Office/PDF.

# Oryven 0.10.0 — Universal Computer Operator

## 0.10.0 — Universal Computer Operator

A 0.10 adiciona a primeira camada universal de operação do Windows sobre a base profissional 0.9:

- inventário de aplicativos com distinção entre instalado e inicializável;
- lançamento governado de `.exe` e atalhos `.lnk` descobertos localmente;
- UI Automation com caminhos limitados e revalidação HWND/PID/título/path/AutomationId;
- `InvokePattern` para controles não sensíveis de tipos permitidos;
- escrita supervisionada em controles `Edit` não-senha sem ler o conteúdo anterior;
- bloqueio inicial de controles de alto impacto no invoke genérico;
- nenhuma automação por coordenadas, clipboard global ou senha nesta versão.

Toda ação nova continua one-shot: planejar, descobrir ou inspecionar não concede permissão de execução.


> Evolução incremental sobre a base existente: agentes profissionais + skills governadas + Work Runtime.

# Oryven by Buno AI — Computer Control 0.5

**Escopo deste pacote:** seleção de janelas e invocação controlada dos botões de janela **Maximizar / Restaurar / Minimizar** via Windows UI Automation (`pywinauto`). Cada ação exige autorização individual de uso único. O Oryven verifica o foco ou o estado da janela depois; se não conseguir comprovar o resultado, informa **não verificado**, sem repetir automaticamente.

**Não é controle universal nem versão comercial.** Não implementa cliques por coordenadas, texto em formulários, terminal PowerShell, controle remoto do navegador pessoal ou operações de escrita em arquivos. Ele preserva ElevenLabs, Vosk, Oryven Missions, inspeção Playwright e conector Buno em modo opt-in da versão 0.4.

## Instalação Windows 10/11

Extraia o ZIP em uma pasta nova. Não sobrescreva projetos existentes.

```powershell
.\scripts\setup-windows.ps1
.\scripts\setup-control-windows.ps1
.\scripts\run-control-tests.ps1
.\scripts\run-backend.ps1
```

Em **outro terminal**, na raiz:

```powershell
.\scripts\run-desktop.ps1
```

Alternativa para testar apenas React sem Tauri: `cd web; npm run dev`, navegador em `http://127.0.0.1:5173`. Executar no Windows precisa de Python 3.11, Node 20+, e Rust/Build Tools/WebView2 para a versão Tauri. Consulte o README histórico abaixo e [o guia 0.5](docs/WINDOW_ACTIONS_0_5.md).

## Primeira demonstração segura

1. Abra o **Bloco de Notas** e deixe a janela em estado normal, não maximizada.
2. Inicie backend/UI e clique em **Solicitar inspeção de janelas**. Confirme a autorização. Dados pessoais em títulos podem ser exibidos na UI.
3. Na janela do Bloco de Notas, clique **Solicitar foco**, confira o título/HWND/PID da autorização e aprove. Confira o resultado **verificado** (caso a UIA confirme que ela ficou ativa).
4. Clique em **Solicitar árvore UIA**, confirme; procure o controle **Maximizar** / **Maximize**. Quando elegível, use **Solicitar ação**.
5. Confira a aprovação para aquela janela e controle, clique **Autorizar uma vez**. O backend reidentifica janela e botão, invoca UIA e tenta confirmar `WindowPattern` no estado maximizado.
6. O resultado pode ser **verificado**, **não verificado** ou **falha**. Nem todas as versões do Notepad expõem o botão à profundidade 2: ausência de botão não autoriza clicar por coordenadas.
7. Faça o mesmo com **Restaurar** para reverter, se o controle estiver disponível.

**Parada de emergência** revoga aprovações pendentes. Não interrompe de forma garantida uma chamada UIA síncrona em curso, nem reverte o que já foi feito.

## Testes e status

Os testes automatizados de backend são simulados para UIA; [relatório de release](docs/RELEASE_0_5.md) separa claramente esses testes da validação em Windows. O pacote não inclui `.env`, tokens, API keys, modelos de voz, navegador Chromium ou instalador compilado. Execute os testes no seu Windows antes de liberar acesso a mais aplicativos.

## Segurança

- Aprovação de cada ação ligada ao tipo, HWND, PID, título, classe, caminho UIA e ID do botão.
- Apenas nomes exatos de botões reconhecidos de **Maximizar, Minimizar, Restaurar** (português/inglês).
- UIA `InvokePattern`: não há clique com coordenadas nem escrita em teclas/campos.
- Verificação do estado final por `WindowPattern` e do foco por `is_active()`.
- Identidade alterada => recusa; resultado não confirmado => não há repetição automática.
- O servidor é somente para desenvolvimento em `127.0.0.1:8765`. A sessão bootstrap atual **não é autenticação apropriada para produção**.

---

## Histórico da versão 0.4 e módulos anteriores

# Oryven by Buno AI — Computer Control 0.4

**Marco atual:** inspeção de janelas e interfaces via Windows UI Automation, navegação pública autorizada via Playwright e integração opt-in com a API Buno. **Não é controle universal pronto.**

## Começar no Windows 10/11

```powershell
.\scripts\setup-windows.ps1
.\scripts\setup-control-windows.ps1
.\scripts\run-backend-tests.ps1
.\scripts\run-backend.ps1
```

Abra um segundo terminal na raiz do projeto:

```powershell
.\scripts\run-desktop.ps1
```

Configure `.env` a partir de `.env.example`; ElevenLabs requer API key e Voice ID. O conector Buno usa apenas `127.0.0.1` e aceita um JWT *opcional* de sessão de desenvolvimento. Não compartilhe nenhum segredo.

- **Windows UIA:** listar janelas / inspecionar metadados rasos após autorizar cada ação.
- **Playwright:** acessar `https://example.com/` ou domínios públicos pré-aprovados sem cookies pessoais.
- **Buno Intelligence:** health sem prompts e consulta textual SSE mediante aprovação individual; nenhuma resposta do modelo executa ações.
- **Segurança:** aprovações pontuais expiráveis, auditoria sem dados brutos UIA ou mensagens Buno, Stop que revoga autorizações pendentes.

**Leia [docs/COMPUTER_CONTROL.md](docs/COMPUTER_CONTROL.md) antes de testar no Windows**, inclusive limitações de UIA, autenticação e comandos de teste. Status de validação em [docs/RELEASE_0_4.md](docs/RELEASE_0_4.md).

---

## Histórico — conteúdo do MVP 0.3 preservado

### Oryven by Buno AI — Starter Kit 0.3 (Windows 10/11)

**Protótipo funcional inicial, não um assistente universal pronto.** Monorepositório independente dos produtos existentes da Buno. Não há chaves nem dados reais no pacote.

## Primeira demonstração

> “Oryven, acordar. Abra o navegador e pesquise inteligência artificial.”

Após ligar o microfone na interface, o sistema reconhece o comando via **Vosk offline**, cria uma solicitação específica e aguarda **Autorizar uma vez**. Após aprovação, solicita ao navegador padrão que abra a URL da pesquisa e emite resposta falada pela **ElevenLabs**, se configurada, ou pela voz local Windows (quando disponível). Abrir a URL **não comprova** que o carregamento ou os resultados foram concluídos.

### Novo no 0.3: Oryven Missions (limitado e verificável)

Na interface, use **Criar missão com aprovação por etapa** com um exemplo:

> "Abra a calculadora e depois abra o bloco de notas"

O Oryven salva o plano em SQLite e pede autorização individual para o primeiro aplicativo. Depois que o Windows recebe a solicitação de abertura, a missão fica em **Aguardando verificação humana**. Clique em **Confirmo que ocorreu** somente se você realmente viu o resultado; só então o Oryven solicitará autorização para o próximo passo. É possível negar, cancelar, pausar pelo botão de emergência, retomar e excluir o histórico de missões encerradas. Ao reiniciar a API, as aprovações anteriores deixam de valer.

**Importante:** este não é um planejador com LLM. O motor aceita apenas **1 a 3 ações de tipos permitidos**: pesquisa web e abertura dos três aplicativos autorizados. Confirmação humana não é verificação automatizada de telas. Missões com etapas desconhecidas são recusadas integralmente, sem executar etapas parcialmente. [Detalhes e contratos](docs/MISSIONS.md).

Outros comandos permitidos no MVP: `Abra o bloco de notas`, `Abra a calculadora`, `Abra o explorador de arquivos`. Esses utilitários também exigem aprovação. Nenhum comando PowerShell, Git, edição de arquivos ou automação irrestrita é executável nesta versão.

## Requisitos

- Windows 10/11 (principal alvo), **Python 3.11** recomendado, Node.js 20+, microfone e navegador padrão.
- Para o modo desktop Tauri: Rust e pré-requisitos Windows descritos em https://v2.tauri.app/start/prerequisites/ (Microsoft C++ Build Tools + WebView2).
- Vosk offline pt-BR: baixar `vosk-model-small-pt-0.3` em https://alphacephei.com/vosk/models e descompactar em `C:\modelos\vosk-model-small-pt-0.3`, ou apontar `ORYVEN_VOSK_MODEL`.
- ElevenLabs opcional: chave com permissão Text-to-Speech e Voice ID. A API envia **apenas o texto da resposta** para síntese; nenhum áudio capturado pelo microfone é enviado ao serviço.

## Instalação rápida (PowerShell, raiz do projeto)

```powershell
.\scripts\setup-windows.ps1
notepad .env
```

Edite **localmente** a `.env`:

```env
ELEVENLABS_ENABLED=true
ELEVENLABS_API_KEY=coloque_sua_chave_aqui
ELEVENLABS_VOICE_ID=seu_id_da_voz
ELEVENLABS_MODEL_ID=eleven_flash_v2_5
ORYVEN_VOSK_MODEL=C:\modelos\vosk-model-small-pt-0.3
```

Nunca inclua a API key no frontend, ZIP enviado a terceiros ou repositório. Para desligar o envio de texto ao provedor, defina `ELEVENLABS_ENABLED=false`. O modelo Flash é uma sugestão configurável; confirme o plano, custo e disponibilidade na ElevenLabs.

**Terminal 1:**

```powershell
.\scripts\run-backend.ps1
```

**Terminal 2:**

```powershell
.\scripts\run-desktop.ps1
```

Alternativa sem Rust: `cd web; npm run dev` e abra http://127.0.0.1:5173. O backend permanece separado e precisa estar rodando. Um instalador independente que inclua Python ainda **não foi implementado**.

## Testes

Diagnóstico inicial, sem executar comandos que modifiquem o sistema:

```powershell
.\scripts\diagnose-windows.ps1
```

```powershell
.\scripts\run-tests.ps1
```

No Linux/CI, para testes de backend (sem áudio e sem Windows):

```bash
PYTHONPATH=backend python -m pytest backend/tests -q
```

## Estrutura

```text
backend/oryven/      API FastAPI, intents, missions SQLite, executores, voz, auditoria, segurança
backend/oryven/agents/  Interfaces tipadas futuras (sem execução multiagente)
backend/tests/       Testes de contrato, permissões, API e sintetizador simulado
web/src/             Interface React + TypeScript
web/src-tauri/       Casca Tauri 2, ícone e configuração de build
skills/builtin/      Manifests declarativos validados, sem execução dinâmica
scripts/             Comandos de setup, diagnóstico, execução e testes em Windows PowerShell
docs/                Arquitetura, segurança, integrações e roadmap
.env.example         Exemplo sem segredos
```

### O que foi testado neste pacote

- **24 testes automatizados Python passaram** no ambiente Linux, incluindo ciclo de vida de missões, cancelamento, recuperação após interrupção e controle por API.
- O build React/Tauri **não pôde ser testado** aqui: as dependências npm não estavam instaladas e a rede não alcançou o registro npm. No seu Windows, o script de setup deve instalar as dependências e `npm run build` precisa ser executado.
- Nenhum teste foi executado em Windows real, com microfone físico ou com credenciais reais da ElevenLabs.

## Funcionalidades verificáveis e limitações

| Recurso | Status |
|---|---|
| Pesquisa via navegador padrão, com aprovação de uso único | Implementada (retorno da solicitação, sem verificação de carregamento) |
| Abertura de Notepad/Calculadora/Explorer | Implementada, validação real necessária no Windows |
| Vosk pt-BR, ativação `Oryven, acordar` | Implementada como reconhecimento de frase; dependente do modelo/microfone |
| ElevenLabs TTS com fallback local Windows | Implementada; teste de API real com chave e reprodução pendentes |
| Catálogo declarativo de 2 skills | Implementado; não há plugins dinâmicos |
| Descoberta de apps no Registro Windows | Parcial; leitura somente |
| SQLite audit, autorização de 120 s e interrupção emergencial | Implementadas para este MVP local |
| Oryven Missions com 1–3 passos, confirmação humana e persistência local | Implementado no 0.3; execução de ferramentas continua restrita |
| Planejador LLM, verificação automática, multiagentes, memória, Maya, Git, UI Automation | Não implementados ainda |
| Instalador Windows standalone, contas, pagamentos, marketplace | Não implementados ainda |

**Limite de segurança:** A API HTTP oferece token de bootstrap para a UI local e NÃO deve ser exposta à rede, Docker com porta publicada ou túnel. Não fornece autenticação apropriada para uso multiusuário/comercial. Leia [docs/SECURITY.md](docs/SECURITY.md).

## Próximos marcos

1. Verificar em Windows 10/11: microfone, wake phrase, ElevenLabs, e a primeira missão de duas etapas; medir latência e falhas.
2. Corrigir bootstrap inseguro para produção: canal autenticado entre Tauri e processo Python sidecar; empacotar instalador de verdade.
3. Integrar provider Buno AI por contrato, mantendo aprovação antes das ferramentas.
4. Evoluir o motor de Missions atual com Playwright/Windows UI Automation, verificadores explícitos e autorização por janela.
5. Integrações Developer (VS Code/Git/GitHub) e Studio (Maya Python/MEL) em sandboxes/escopos específicos.

Não foram feitas modificações nos repositórios Buno, Buno-api ou Flow Commerce.

## 0.8.0 — Professional Agents Foundation

Oryven now includes a governed universal professional-agent catalog. The existing Developer
Runtime remains the software execution specialist, while the new Professional Agent Runtime
routes work across 32 packaged profiles including software, AI/ML, data, office, marketing,
finance, legal operations, HR, design, 3D/Maya, audiovisual, e-commerce, logistics, engineering,
architecture/BIM, science, healthcare operations and a universal fallback.

Agent routing is advisory: selecting a profession never grants execution permission. Side effects
continue to pass through Oryven's explicit tool/approval governance.

See `docs/PROFESSIONAL_AGENT_RUNTIME.md`.


## Oryven 0.14.0 — Visual Missions Foundation

Veja `docs/RELEASE_0_14_0_VISUAL_MISSIONS.md`. A release adiciona captura visual governada de janelas e missões profissionais tipadas de até 8 etapas, sempre com aprovação por ação.

## Oryven 0.14.2 — Vision Provider + Multi-App Voice Missions

Veja `docs/RELEASE_0_14_2_VISION_MULTI_APP.md`. Esta release adiciona Screen Understanding governado, provider multimodal local opcional via Ollama e a primeira missão multi-app acionável por voz, com contexto explícito e aprovações por etapa.


## Oryven 0.15.0 — Supervised Autonomous Mission Orchestrator

Veja `docs/RELEASE_0_15_0_AUTONOMOUS_ORCHESTRATOR.md`. Esta release adiciona planejamento adaptativo local, seleção de agente profissional, verificação automática de etapas verificáveis e recuperação supervisionada com orçamento limitado, preservando autorização one-shot para cada ação.
