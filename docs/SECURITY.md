# Segurança e governança

**Regra:** sugerir proativamente; executar somente com autorização explícita e específica.

1. Negação por padrão: somente `browser.search` e `app.launch` (Notepad, Calculator, Explorer).
2. Missões: no máximo 3 ações; cada ação recebe aprovação individual e confirmação humana. Se o processo cair durante o envio de uma ação, a missão exige revisão e NÃO a repete automaticamente.
3. Aprovação: ID aleatório, argumento exato, hash da ação, 120 segundos, consumo único. Sem aprovação global.
4. Auditoria: metadados em SQLite local, sem registrar áudio bruto, credenciais ou prompt completo.
5. Áudio: microfone desligado por padrão; habilitação manual; reconhecimento local com Vosk. ElevenLabs recebe somente texto de respostas quando habilitada no `.env`.
6. Destrutivo: PowerShell, exclusão, push, deploy, pagamentos, modificações de sistema e ações arbitrárias estão desabilitados.
7. Emergência: cancela autorizações futuras e tenta interromper captura/fala; não desfaz ações já enviadas ao sistema operacional, nem garante cancelar uma chamada em andamento.
8. Dados: configuração via `.env` local ignorado pelo Git; para produção usar Windows Credential Manager, chave rotacionável e limites no painel ElevenLabs.
9. Proteção contra injection: o parser não executa código produzido por sites, documentos ou modelos. Nenhuma integração capaz de ler páginas está habilitada.

## Limitações atuais IMPORTANTES

O bootstrap HTTP `/api/session` serve o token ao cliente local, protegido somente por loopback, validação de origem/host e política CORS. Essas medidas NÃO substituem autenticação de desktop: processos locais ou outros clientes capazes de falar com o loopback ainda são um risco. **Não publicar a porta 8765, não expor via túnel nem usar em multiusuário.** Na versão comercial, substituir por IPC autenticado, pareamento do sidecar, binding de processo e token de usuário protegido.

Nenhuma informação do Registro Windows é modificada na descoberta. Uma abertura de processo pode ter consequências não verificadas; por isso requer autorização.

## Privacidade das missões

O SQLite das missões guarda título digitado e argumentos das ações planejadas, além do status de execução; ele não guarda gravações de voz. Esses títulos podem conter consultas pessoais; não compartilhe o arquivo `missions.sqlite3`. A interface permite apagar históricos de missões encerradas. O `audit.sqlite3` registra apenas eventos mínimos; exclusão do histórico de missões não remove automaticamente eventos de auditoria (podem ser removidos separadamente).


## Controles adicionais 0.4

- UIA lista títulos que podem conter informação pessoal; não execute em desktop com dados que você não deseja expor. Senhas/Edit/Document não são lidos; metadados não são armazenados no audit.
- Playwright usa contexto novo, sem cookies, sem downloads e domínios públicos allowlisted, com redirecionamentos cross-host bloqueados. O conteúdo da página permanece dado não confiável.
- Buno chat requer consentimento para a mensagem exata e token JWT Buno local, enviado apenas ao loopback; Buno pode persistir a mensagem. Nunca executar a resposta como ferramenta.
- O botão Stop revoga autorizações pendentes, mas não encerra instantaneamente operações síncronas já iniciadas.
- `.env` e tokens são para teste local apenas; em produção usar armazenamento do SO e autenticação.

## Controles adicionais 0.5

O Oryven adicionou `computer.window.focus` e `computer.button.invoke` (somente **Maximizar / Restaurar / Minimizar**). Aprovações ficam ligadas a HWND/PID/classe/título e, para botões, caminho UIA/nome/AutomationID. Antes de agir, todos os campos são novamente conferidos; a árvore continua superficial e campos sensíveis não podem ser alvos. Após ação, verifica foco ou estado final. Falhas/incertezas não causam repetição automática. O texto de títulos/controles não entra no SQLite audit; a interface pode exibir nomes pessoais em memória.

**Limitações:** um aplicativo malicioso no mesmo usuário pode enganar a UIA; o bootstrap HTTP continua impróprio para distribuição comercial. Ações em andamento não são canceláveis com garantia. Não há automação arbitrária, privilégios elevados ou autorização delegável ao modelo.
