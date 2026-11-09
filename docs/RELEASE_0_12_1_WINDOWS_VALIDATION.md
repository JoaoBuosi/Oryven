# Oryven 0.12.1 — Windows release validation

0.12.1 is a release gate over the 0.12 voice/Tauri work. It does not claim a Windows installer has been validated outside Windows.

Run on Windows PowerShell from the repository:

```powershell
.\scripts\validate-windows-0121.ps1
```

The gate requires Python/venv, Node/npm and Rust/Cargo, runs the full backend regression, builds the PyInstaller sidecar, boots that EXE and verifies `/api/health`, builds the React frontend, runs `tauri build`, requires an NSIS `.exe`, and prints its SHA-256.

To copy the validated installer into `release/`:

```powershell
.\scripts\build-release-windows.ps1
```

A release is not considered Windows-validated until this script succeeds on a Windows 10/11 machine and the resulting installer is installed/tested on a clean Windows user profile.
