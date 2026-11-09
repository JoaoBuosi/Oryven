# Oryven 0.10.0 — Universal Computer Operator

## Objetivo

Transformar a fundação profissional 0.9 em um operador Windows governado capaz de descobrir aplicativos e interagir com controles reais por UI Automation, sem introduzir execução arbitrária ou permissões implícitas.

## Arquitetura

```text
Professional Agent
      |
      v
Skill Plan
      |
      v
Universal Computer Operator
  |       |        |
 apps   windows   fields
  |       |        |
  +---- one-shot approval ----+
              |
              v
        revalidation
              |
              v
          execution
              |
              v
        verified/unverified
```

## Implementado

- `AppCatalog`: inventário local e resolução de apps inicializáveis.
- Fontes Windows: uninstall registry, App Paths e atalhos do Start Menu.
- Lançamento apenas de alvo descoberto `.exe` ou `.lnk` local.
- Revalidação do alvo do app depois da aprovação.
- Inspeção UIA ampliada para até 80 elementos e profundidade 4, ainda limitada.
- Redação de conteúdo de `Edit`/`Document` e bloqueio de password controls.
- `computer.control.invoke` para Button/MenuItem/Hyperlink/TabItem elegíveis.
- `computer.control.set_text` para `Edit` não-senha com `AutomationId`.
- O texto atual do campo Edit não entra em inspeção, aprovação ou auditoria.
- O texto novo não aparece na descrição de aprovação; o fingerprint continua vinculado ao texto exato.
- Generic invoke nunca repete automaticamente e retorna `unverified` quando não existe postcondition objetiva.
- Botões legados maximizar/restaurar/minimizar mantêm verificação objetiva.
- Controles de alto impacto com labels como Delete/Excluir/Enviar/Confirmar/Pagar/Publicar ficam bloqueados no invoke genérico desta release.

## APIs novas

- `POST /api/apps/launch/propose`
- `POST /api/control/window/invoke/propose`
- `POST /api/control/window/text/propose`

`GET /api/apps` agora informa `launchable`, `source`, `launch_target` e `target_type` quando o alvo é descoberto. O frontend não deve tratar descoberta como autorização.

## Skills novas

- `app.launch.universal`
- `computer.control.invoke`
- `computer.control.set_text`

Essas skills são recomendadas a todos os Professional Agents como capacidades universais, mas continuam sem permissão até a criação e aprovação de uma ação concreta.

## Segurança preservada

- deny by default;
- aprovação one-shot com expiração;
- fingerprint de argumentos exatos;
- revalidação de identidade da janela e do controle;
- sem `shell=True`;
- sem path arbitrário para lançamento de app;
- sem leitura/escrita de passwords;
- sem clipboard;
- sem clique por coordenadas;
- sem captura de tela/visão nesta release;
- emergência revoga autorizações pendentes.

## Testes

Suíte backend no ambiente de desenvolvimento:

```text
104 passed
```

Inclui regressão 0.9 e novos testes de:

- app ambíguo e nome arbitrário;
- launch somente após aprovação;
- invoke genérico sem sucesso presumido;
- mudança de controle entre preview e execução;
- bloqueio de controle destrutivo;
- redação de Edit/password;
- set_text governado e verificável;
- fluxo API completo do Universal Operator.

## Testes Windows obrigatórios antes de considerar 0.10 validada

1. Descobrir Chrome/Edge/VS Code/Notepad e ao menos um aplicativo de terceiro.
2. Abrir cada app por `app.launch.universal`.
3. Confirmar PID/janela para executáveis lançados diretamente.
4. Inspecionar UIA em Notepad, Explorer, VS Code, navegador e um app Win32/WPF.
5. Focar janelas.
6. Invocar controles seguros.
7. Preencher um campo Edit não sensível e confirmar resultado.
8. Confirmar bloqueio de password fields.
9. Confirmar que alteração de janela/control entre preview e approve falha.
10. Confirmar Emergency Stop antes da aprovação.

## Limitações deliberadas

A 0.10 não promete dominar qualquer aplicativo. Aplicações sem boa árvore UIA, canvas, jogos, apps com render próprio ou interfaces remotas exigirão a próxima camada de visão/fallback. Mouse/teclado por coordenadas e visão de tela entram apenas depois de definirmos percepção, risco e verificação adequados.
