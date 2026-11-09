> Histórico da versão 0.4 (inspeção somente leitura). Para ações limitadas da versão 0.5, leia [WINDOW_ACTIONS_0_5.md](WINDOW_ACTIONS_0_5.md).

# Oryven Computer Control 0.4 — especificação e guia

## Escopo implementado

- `computer.windows.list`: Windows UI Automation com `pywinauto.Desktop(backend="uia")`; lista **até 25** janelas visíveis depois de aprovação de uso único.
- `computer.window.inspect`: inspeciona **até 50** metadados superficiais da árvore de controles da janela (até profundidade 2) depois de autorização vinculada ao HWND.
- `browser.inspect`: usa Chromium Playwright em um **contexto não persistente**, não herda cookies, recusa downloads e bloqueia requisições para outros domínios. Consulta título, cabeçalhos H1 e HTTP, não preenche formulários.
- `buno.health`: consulta endpoint `GET /api/v1/health` da Buno local, sem enviar segredo ou prompt.
- `buno.chat`: proposta de envio de mensagem (até 500 caracteres) ao endpoint autenticado `POST /api/v1/chat/stream`; exige aprovação de uso único para o hash exato da mensagem e configuração local de JWT. O texto de resposta **não é executado**.

Oryven Computer Control 0.4 é um protótipo local de *inspeção e integração condicionada* — não possui automação de cliques UIA, preenchimento de formulários ou controle genérico de aplicativos. Isso é intencional nesta etapa.

## Scripts Windows

Na raiz do projeto, PowerShell:

```powershell
.\scripts\setup-windows.ps1
.\scripts\setup-control-windows.ps1
.\scripts\run-backend-tests.ps1
.\scripts\run-backend.ps1
```

Novo terminal:

```powershell
.\scripts\run-desktop.ps1
```

Para testar a interface web sem compilar Tauri, no diretório `web`, rode `npm run dev`. A interface aponta para `http://127.0.0.1:8765`.

O `setup-control-windows.ps1` instala `pywinauto` e `playwright` no venv e baixa o Chromium do Playwright. Requer Windows, Python 3.11 e internet para instalação. A compilação do Tauri requer Rust e ferramentas de compilação Windows além de Node.

## Percurso manual de demonstração

1. Inicie backend e interface. **Microfone desligado** até sua ativação.
2. Em **Computer Control**, clique em `Solicitar inspeção de janelas`.
3. Leia a autorização (títulos de janelas podem conter informações pessoais). Aprove uma vez; aparecem títulos e IDs de janelas. Negar não efetua leitura.
4. Escolha `Solicitar árvore UIA` em uma janela aberta, aprove uma vez. Campos Edit/Document/Password têm conteúdo omitido. A visualização não salva valores.
5. Em **Playwright**, use `https://example.com/`; solicite e aprove. Com Chromium instalado, deve retornar título `Example Domain`, HTTP e H1. O acesso pode falhar por rede/antibot; falha é mostrada sem marcar sucesso.
6. Em **Buno AI**, cheque o health local. Se a Buno estiver em `127.0.0.1:8000` e autenticada por JWT, preencha `ORYVEN_BUNO_BEARER_TOKEN` no `.env` e reinicie. Digite pergunta, solicite envio e aprove. A Buno pode registrar a mensagem em conversas/memórias.
7. Execute `Parada de emergência` para revogar aprovações pendentes e desligar o microfone. Ações em andamento não podem ser anuladas instantaneamente.

## Compatibilidade e limitações

- Windows UIA: requer Windows 10/11. Alguns aplicativos não expõem controles, sobretudo interfaces customizadas. Não tenta ultrapassar UAC/UIPI nem ler janelas elevadas de outro nível de integridade.
- Metadados UIA: mesmo um título de janela ou nome de botão pode conter dados pessoais. Só inspecione janelas adequadas e em máquina de desenvolvimento. O escopo de acesso não representa proteção contra aplicações hostis no mesmo usuário Windows.
- UIA em `pywinauto` opera de forma síncrona e não implementa timeout por elemento; interfaces travadas podem atrasar a resposta. O backend ainda não suporta cancelamento cooperativo de inspeções já iniciadas.
- Playwright: hospedeiro permitido `example.com`, `playwright.dev`, `docs.python.org`, `www.python.org`, `developer.mozilla.org`, `learn.microsoft.com`, em HTTPS 443. URL local, IP e outras origens são recusados. Chromium precisa ser instalado separadamente. Conteúdo DOM é **não confiável**.
- O browser Playwright é aberto em modo **headless e isolado**, fechado após a inspeção. Não controla o navegador pessoal já aberto. A ação original `browser.search` continua abrindo busca no navegador padrão, sem verificação de carregamento.
- Buno: integrou-se ao contrato **observado no repositório GitHub consultado em novembro/2026**, que pode diferir do seu código local. A Buno precisa estar executando e possuir usuário/JWT válidos. Não lemos/geramos tokens. O JWT será guardado no `.env` **apenas para desenvolvimento**; produção exige Windows Credential Manager ou equivalente.
- Endpoints de desenvolvimento na interface local não têm autenticação multiusuário, proteção contra malware com o mesmo usuário ou isolamento de processos. Não exponha portas FastAPI à internet.

## API — endpoints adicionados

Todas exigem header `X-Oryven-Session`, obtido da UI local `GET /api/session`:

| Endpoint | Método | Efeito |
|---|---|---|
| `/api/control/windows/propose` | POST | Cria proposta de leitura de janelas |
| `/api/control/window/propose` | POST | Proposta da árvore de um HWND, corpo `{"handle":123}` |
| `/api/control/browser/propose` | POST | Proposta pública, corpo `{"url":"https://example.com/"}` |
| `/api/integrations/buno/health` | GET | Consulta local de disponibilidade, não manda prompts |
| `/api/integrations/buno/chat/propose` | POST | Proposta de envio, corpo `{"message":"Olá"}` |
| `/api/actions/{id}/decision` | POST | Executa somente após `{"decision":"approve"}`; devolve `data` efêmero |

Toda autorização é expirada após 120 segundos, consumida uma vez e vinculada ao tipo e destino exatos da ação. Reiniciar o backend revoga aprovações em memória. Os dados brutos da UIA, browser e respostas Buno não são gravados nos registros de auditoria do Oryven; no entanto, são enviados à interface local e podem permanecer na memória do processo até a limpeza/sessão acabar.

## Próximo incremento proposto (0.5)

1. Implementar seletor de janela que valide **foco, tipo do controle e retângulo** antes de executar uma ação específica, com revisão humana e botão Stop.
2. Adicionar verificação antes/depois por snapshot de UIA/DOM (sem textos sensíveis); nunca presumir que um clique teve sucesso.
3. Melhorar controle Playwright com `get_by_role` e ações reversíveis somente em páginas explicitamente permitidas. Nenhum POST, upload, compras, logins ou exclusões sem nova classe de permissão.
4. Adaptador Buno de modelos com formato de saída estruturado validado por Pydantic; o modelo propõe, mas a governança local **não delega aprovação**.
5. Testes E2E no Windows com Notepad, Chromium real, Vosk e ElevenLabs, e compilação Tauri assinada.

## Referências de API

- https://pywinauto.readthedocs.io/en/latest/getting_started.html
- https://playwright.dev/python/docs/api/class-browser
- https://playwright.dev/python/docs/api/class-browsercontext
- https://learn.microsoft.com/en-us/windows/security/threat-protection/security-policy-settings/user-account-control-allow-uiaccess-applications-to-prompt-for-elevation-without-using-the-secure-desktop
