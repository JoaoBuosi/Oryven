# Oryven 0.6 — auditoria inicial e patch de voz (incremento 1)

## Base
Pacote integral Oryven Computer Control 0.5. Não modifica outros projetos. Este é um **patch preparatório**, não um instalador nem uma versão 0.6 concluída.

## Evidência de auditoria
- Backend Python FastAPI, UI React/TypeScript, Tauri 2 (configuração NSIS), Windows UI Automation e Playwright presentes no código.
- `web/src-tauri/Cargo.toml` ainda indica `0.2.0`, enquanto `tauri.conf.json` indica `0.5.0`: alinhar antes de empacotar.
- `tauri.conf.json` aponta frontend para localhost:8765, mas a configuração atual não comprova gerenciamento automático do processo Python em distribuição.
- `Speaker` local inicializa `pyttsx3` uma vez e desativa a voz permanentemente após erro. É um possível fator para voz parar, não uma causa comprovada no Windows do usuário.
- `ElevenLabsSpeaker.speak_once` antes tratava apenas HTTPError, TTSUnavailable e OSError; falhas inesperadas de reprodução podiam encerrar a thread silenciosamente.
- O usuário confirmou 41 testes do subconjunto de controle no Windows; a suíte completa requer `run-backend-tests.ps1`.

## Mudanças incrementais
- `backend/oryven/elevenlabs_tts.py`: falha inesperada na chamada/reprodução não encerra o worker; fallback local é tentado; falha do fallback não quebra a chamada.
- Diagnóstico sem detalhes sensíveis: `last_error` contém somente nomes de classes de exceção, `last_provider` indica `elevenlabs`, `local-fallback` ou `unavailable`.
- Após falha temporária, próxima chamada tenta ElevenLabs novamente.
- `backend/tests/test_voice_resilience.py`: 4 testes novos sem áudio ou rede reais.

## Validação local
Na raiz do projeto, após instalar dependências:

```powershell
.\scripts\run-backend-tests.ps1
.\.venv\Scripts\python.exe -m pytest backend\tests\test_voice_resilience.py -q
```

## Evidências e limitações
- Linux container: **69 testes de backend aprovados** com dependências disponíveis no ambiente; testes usam fakes/mocks.
- Windows real: **não executado para este patch**. ElevenLabs real, alto-falante, microfone e instalador não validados.
- O patch não corrige automaticamente falhas persistentes do SAPI local, nem adiciona bandeja/autostart/sidecar. Não alterou permissões de Computer Control.

## Próximas alterações
1. Instrumentar teste explícito de voz local e status seguro no frontend, diagnosticar SAPI.
2. Auditar e testar transições de missão versus autorizações.
3. Validar foco e InvokePattern no Windows real.
4. Gerenciar backend via Tauri sidecar, instância única e encerramento seguro; alinhar versões.
5. Testar e assinar instalador NSIS no Windows.
