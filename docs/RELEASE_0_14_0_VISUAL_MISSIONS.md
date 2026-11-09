# Oryven 0.14.0 — Visual Missions Foundation

## Objetivo

Introduzir percepção visual governada e missões profissionais multi-etapas sem permitir que screenshots, documentos ou páginas externas ampliem permissões do agente.

## Entregue

- `computer.window.capture`: captura PNG somente da janela exata aprovada (HWND/PID/título fingerprintado).
- Snapshot mantido em memória e retornado ao chamador; não é persistido automaticamente por `VisualPerception`.
- Limite de 8 milhões de pixels e 12 MB por snapshot.
- Pillow opcional no Windows para `ImageGrab`.
- `/api/perception/window/propose` para solicitar a captura por aprovação one-shot.
- Mission Store agora desserializa a união completa de intents executáveis.
- Missões tipadas aceitam até 8 etapas.
- `/api/missions/skills` cria missão a partir de uma sequência explícita de skills e argumentos exatos.
- Execuções de Work/Developer/Professional/UI passam a atualizar a missão para `awaiting_verification` antes de avançar.
- Voz existente continua podendo acionar comandos e missões conhecidas; missões profissionais complexas usam o mesmo runtime depois que o plano tipado é criado.

## Segurança

- Captura visual exige aprovação específica e é revalidada imediatamente antes da captura.
- Mudança de PID/janela entre proposta e execução causa falha.
- Imagem não é gravada em auditoria, memória do chat ou banco de missões.
- A imagem capturada é evidência não confiável; seu conteúdo nunca é tratado como autorização.
- Cada etapa de missão precisa de aprovação independente e verificação antes da próxima.
- Nenhum agente recebe permissão por ter sido selecionado.

## Limite honesto desta release

Esta release cria a camada de captura/evidência visual. Ela **não** afirma ter um modelo multimodal local capaz de interpretar pixels arbitrários. A próxima evolução deve plugar um Vision Provider isolado, com política explícita para transmissão local/cloud e proteção contra prompt injection visual.

## Windows gate

Validar com janelas reais (Explorer, Notepad, Chrome/Edge, VS Code e apps terceiros): captura de janela, multi-monitor, DPI scaling e revalidação HWND/PID.
