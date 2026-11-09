# Validação 0.12.0

- Backend: `124 passed`.
- Python: `compileall` OK.
- Frontend: código atualizado, mas build local bloqueado neste ambiente porque `npm install` excedeu o limite de execução e as dependências React não estavam pré-instaladas.
- Rust/Tauri: código/configuração preparados; `cargo` não existe neste ambiente, então o build NSIS permanece gate obrigatório no Windows.

Não declarar instalador comercial validado até os gates Windows passarem.
