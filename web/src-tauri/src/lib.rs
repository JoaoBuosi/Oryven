use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::{Manager, WindowEvent};
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};

struct BackendProcess(Mutex<Option<Child>>);

fn spawn_backend(app: &tauri::AppHandle) -> Result<Child, String> {
    if let Ok(explicit) = std::env::var("ORYVEN_BACKEND_EXE") {
        return Command::new(explicit)
            .stdout(Stdio::null()).stderr(Stdio::null())
            .spawn().map_err(|e| format!("backend explícito não iniciou: {e}"));
    }

    if let Ok(resource_dir) = app.path().resource_dir() {
        let bundled = resource_dir.join("oryven-backend.exe");
        if bundled.is_file() {
            return Command::new(bundled)
                .stdout(Stdio::null()).stderr(Stdio::null())
                .spawn().map_err(|e| format!("backend empacotado não iniciou: {e}"));
        }
    }

    // Development fallback. Find the repository backend and inject PYTHONPATH only for the child.
    let cwd = std::env::current_dir().map_err(|e| format!("diretório atual indisponível: {e}"))?;
    let mut candidates = vec![cwd.clone(), cwd.join(".."), cwd.join("../..")];
    if let Some(parent) = cwd.parent() { candidates.push(parent.to_path_buf()); }
    for root in candidates {
        let backend = root.join("backend");
        if backend.join("oryven").is_dir() {
            return Command::new("python")
                .args(["-m", "oryven"])
                .env("PYTHONPATH", &backend)
                .current_dir(&root)
                .stdout(Stdio::null()).stderr(Stdio::null())
                .spawn().map_err(|e| format!("backend Python de desenvolvimento não iniciou: {e}"));
        }
    }
    Err("backend Oryven não encontrado; defina ORYVEN_BACKEND_EXE ou gere o sidecar".into())
}

fn show_main(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.set_focus();
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(BackendProcess(Mutex::new(None)))
        .setup(|app| {
            let handle = app.handle().clone();
            let child = spawn_backend(&handle)?;
            if let Ok(mut slot) = app.state::<BackendProcess>().0.lock() {
                *slot = Some(child);
            }

            // Tray integration is optional at runtime. A tray/menu initialization
            // failure must never prevent the main Oryven window from starting.
            if let (Ok(open), Ok(quit)) = (
                MenuItem::with_id(app, "open", "Abrir Oryven", true, None::<&str>),
                MenuItem::with_id(app, "quit", "Sair", true, None::<&str>),
            ) {
                if let Ok(menu) = Menu::with_items(app, &[&open, &quit]) {
                    let tray_handle = handle.clone();
                    let _ = TrayIconBuilder::new()
                        .menu(&menu)
                        .tooltip("Oryven by Buno AI")
                        .on_menu_event(move |app, event| match event.id.as_ref() {
                            "open" => show_main(app),
                            "quit" => app.exit(0),
                            _ => {}
                        })
                        .on_tray_icon_event(move |_tray, event| {
                            if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. } = event {
                                show_main(&tray_handle);
                            }
                        })
                        .build(app);
                }
            }

            // Make the main window visible/focused even if tray initialization
            // is unavailable on a particular Windows machine.
            show_main(&handle);
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .build(tauri::generate_context!())
        .expect("erro ao construir a interface Oryven");

    app.run(|handle, event| {
        if let tauri::RunEvent::Exit = event {
            if let Ok(mut slot) = handle.state::<BackendProcess>().0.lock() {
                if let Some(child) = slot.as_mut() {
                    let _ = child.kill();
                    let _ = child.wait();
                }
                *slot = None;
            }
        }
    });
}
