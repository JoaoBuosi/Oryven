# Oryven 0.17.0-rc1 — Release Candidate 1

This release freezes major feature work and moves the project into release engineering.

## RC goals

- one source of truth for version `0.17.0-rc1` across Python, React/Tauri and release scripts;
- rotating local diagnostics in `<ORYVEN_DATA_DIR>/logs/oryven.log`;
- local crash marker `last_crash.json` for fatal backend failures;
- stricter Windows release gate with backend tests, compile check, sidecar health, version check, frontend build, Tauri/NSIS build and SHA-256;
- Buno integration check that never prints the bearer token;
- diagnostics collector that records only whether secrets are configured, never their values;
- clean-PC validation remains mandatory before calling the installer validated.

## Windows commands

```powershell
.\scripts\setup-windows.ps1
.\scripts\check-buno-integration.ps1
.\scripts\validate-windows-017.ps1
.\scripts\build-release-windows.ps1
```

Expected output after the final command:

```text
release\Oryven-Setup-0.17.0-rc1.exe
release\SHA256SUMS.txt
```

## Clean-PC acceptance gate

1. Install without VS Code or a global Python dependency.
2. Launch Oryven and confirm the bundled backend answers `/api/health` as `0.17.0-rc1`.
3. Register/login and restart the app; the session must restore.
4. Complete onboarding and select an active project.
5. Validate microphone, Vosk/wake word, local TTS and ElevenLabs fallback if configured.
6. Validate real Buno connection and authenticated mission planning.
7. Run one Development mission and one Office/Data mission end to end.
8. Exercise one authorization denial and Emergency Stop.
9. Close to tray, restore, then quit from tray; backend must terminate.
10. Reboot Windows and repeat launch/session checks.
11. Uninstall and verify expected data-retention behavior.

Until these checks pass on Windows, the project is an RC build, not a validated commercial installer.
