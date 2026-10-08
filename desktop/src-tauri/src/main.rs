#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Emitter, Listener, Manager, WindowEvent,
};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

const DEV_FRONTEND_URL: &str = "http://localhost:3000";
const PROD_DIST_HINT: &str = "../frontend/build";
const AGENT_BROWSER_URL_DEFAULT: &str = "https://www.google.com";
const HOTKEY: &str = "Ctrl+Shift+F";

// ---------- Tauri commands: agent calls these via invoke() ----------

#[derive(Serialize)]
struct DesktopInfo {
    platform: String,
    arch: String,
    forge_root: String,
}

#[tauri::command]
fn desktop_info() -> DesktopInfo {
    let home = dirs_next();
    let root = home.join("Documents").join("FORGE");
    DesktopInfo {
        platform: std::env::consts::OS.to_string(),
        arch: std::env::consts::ARCH.to_string(),
        forge_root: root.display().to_string(),
    }
}

#[tauri::command]
fn browser_navigate(app: tauri::AppHandle, url: String) -> Result<String, String> {
    let win = app
        .get_webview_window("agent-browser")
        .ok_or_else(|| "agent-browser window not found".to_string())?;
    // WebView2 navigate via eval
    let js = format!("window.location.href = {};", serde_json::to_string(&url).unwrap());
    win.eval(&js).map_err(|e| e.to_string())?;
    // also tell frontend about navigation
    let _ = app.emit("forge:browser-navigate", &url);
    Ok(url)
}

#[tauri::command]
fn browser_eval(app: tauri::AppHandle, js: String) -> Result<String, String> {
    let win = app
        .get_webview_window("agent-browser")
        .ok_or_else(|| "agent-browser window not found".to_string())?;
    // eval and return via a one-shot channel: use window.eval which is fire-and-forget;
    // for a real return value, frontend can listen on forge:browser-result
    win.eval(&js).map_err(|e| e.to_string())?;
    Ok("eval dispatched".into())
}

#[tauri::command]
fn browser_content(app: tauri::AppHandle) -> Result<String, String> {
    // Ask the agent-browser to post its document outerHTML back via event
    let win = app
        .get_webview_window("agent-browser")
        .ok_or_else(|| "agent-browser not found".to_string())?;
    win.eval(
        "window.__TAURI_INTERNALS__ && window.dispatchEvent(new CustomEvent('forge:request-content'))",
    )
    .map_err(|e| e.to_string())?;
    Ok("content requested".into())
}

#[tauri::command]
fn open_path(path: String) -> Result<String, String> {
    // Reveal/open a file via OS — sandboxed: only allow FORGE root + temp
    let p = std::path::Path::new(&path);
    if !is_allowed_path(p) {
        return Err(format!("path not allowed (sandboxed to ~/Documents/FORGE): {}", path));
    }
    opener::open(&path).map_err(|e| e.to_string())?;
    Ok(path)
}

#[tauri::command]
fn open_url(url: String) -> Result<String, String> {
    // open any https URL in default browser
    if !url.starts_with("http://") && !url.starts_with("https://") {
        return Err("only http/https URLs allowed".into());
    }
    opener::open(&url).map_err(|e| e.to_string())?;
    Ok(url)
}

#[tauri::command]
fn shell_run(cmd: String, cwd: Option<String>) -> Result<String, String> {
    let cwd = cwd.unwrap_or_else(|| forge_root().display().to_string());
    let cwd_path = std::path::Path::new(&cwd);
    if !is_allowed_path(cwd_path) {
        return Err(format!("cwd not allowed (sandboxed to ~/Documents/FORGE): {}", cwd));
    }
    let output = std::process::Command::new("cmd")
        .args(["/C", &cmd])
        .current_dir(cwd_path)
        .output()
        .map_err(|e| e.to_string())?;
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    let combined = if stderr.is_empty() {
        stdout
    } else {
        format!("{stdout}\n[stderr]\n{stderr}")
    };
    if !output.status.success() {
        return Err(format!(
            "exit {}: {}",
            output.status.code().unwrap_or(-1),
            combined.chars().take(4000).collect::<String>()
        ));
    }
    Ok(combined.chars().take(8000).collect())
}

#[tauri::command]
fn ensure_forge_root() -> Result<String, String> {
    let root = forge_root();
    std::fs::create_dir_all(&root).map_err(|e| e.to_string())?;
    Ok(root.display().to_string())
}

fn forge_root() -> std::path::PathBuf {
    dirs_next().join("Documents").join("FORGE")
}

fn dirs_next() -> std::path::PathBuf {
    dirs::home_dir().unwrap_or_else(|| std::path::PathBuf::from("C:\\Users\\Public"))
}

fn is_allowed_path(p: &std::path::Path) -> bool {
    // allow: ~/Documents/FORGE/**, %APPDATA%/forge/**, %TEMP%/**
    let s = p.display().to_string().to_lowercase();
    let home = dirs_next().display().to_string().to_lowercase();
    let forge = forge_root().display().to_string().to_lowercase();
    if s.starts_with(&forge) {
        return true;
    }
    // allow temp
    if let Ok(tmp) = std::env::var("TEMP") {
        if s.starts_with(&tmp.to_lowercase()) {
            return true;
        }
    }
    if let Ok(tmp) = std::env::var("TMP") {
        if s.starts_with(&tmp.to_lowercase()) {
            return true;
        }
    }
    // allow appdata forge
    if let Ok(appdata) = std::env::var("APPDATA") {
        let a = format!("{}\\forge", appdata).to_lowercase();
        if s.starts_with(&a) {
            return true;
        }
    }
    // also allow the exact home/Documents/FORGE root creation even if it doesn't exist yet
    if s == forge || s.starts_with(&format!("{}\\documents\\forge", home)) {
        return true;
    }
    false
}

fn main() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_os::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            None,
        ))
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(win) = app.get_webview_window("main") {
                let _ = win.show();
                let _ = win.set_focus();
            }
        }))
        .plugin(tauri_plugin_window_state::Builder::new().build())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_shortcuts([HOTKEY])
                .unwrap()
                .build(),
        )
        .invoke_handler(tauri::generate_handler![
            desktop_info,
            browser_navigate,
            browser_eval,
            browser_content,
            open_path,
            open_url,
            shell_run,
            ensure_forge_root
        ]);

    builder
        .setup(|app| {
            // Ensure ~/Documents/FORGE exists
            let _ = ensure_forge_root();
            eprintln!("[FORGE] sandbox root: {}", forge_root().display());

            // Global hotkey Ctrl+Shift+F → summon FORGE (best-effort; don't crash if taken)
            let handle = app.handle().clone();
            match app.global_shortcut().on_shortcut(HOTKEY, move |_app, _shortcut, event| {
                if event.state == ShortcutState::Pressed {
                    if let Some(win) = handle.get_webview_window("main") {
                        let _ = win.show();
                        let _ = win.set_focus();
                        let _ = win.unminimize();
                    }
                }
            }) {
                Ok(_) => eprintln!("[FORGE] hotkey {} registered", HOTKEY),
                Err(e) => eprintln!("[FORGE] hotkey {} not registered (already in use?): {}", HOTKEY, e),
            }

            // Create hidden agent-browser window (agents drive this; user can pop it)
            let _agent_win = tauri::WebviewWindowBuilder::new(
                app,
                "agent-browser",
                tauri::WebviewUrl::External(AGENT_BROWSER_URL_DEFAULT.parse().unwrap()),
            )
            .title("FORGE — Agent Browser")
            .inner_size(1100.0, 750.0)
            .visible(false)
            .build()?;
            eprintln!("[FORGE] agent-browser window created (hidden)");

            // Listen for frontend requesting to show/hide agent browser
            let app_h = app.handle().clone();
            app.listen("forge:show-browser", move |event| {
                let url = event.payload().trim_matches('"').to_string();
                if let Some(win) = app_h.get_webview_window("agent-browser") {
                    if !url.is_empty() && url.starts_with("http") {
                        let js = format!("window.location.href = {};", serde_json::to_string(&url).unwrap());
                        let _ = win.eval(&js);
                    }
                    let _ = win.show();
                    let _ = win.set_focus();
                }
            });
            let app_h2 = app.handle().clone();
            app.listen("forge:hide-browser", move |_| {
                if let Some(win) = app_h2.get_webview_window("agent-browser") {
                    let _ = win.hide();
                }
            });
            // Forward browser content back to main window / backend bridge
            let app_h3 = app.handle().clone();
            app.listen("forge:browser-content", move |event| {
                // re-emit so frontend + business-os bridge can read it
                let _ = app_h3.emit("forge:browser-content-fwd", event.payload());
            });

            // System tray — FORGE lives in the tray, doesn't die on close
            let show = MenuItem::with_id(app, "show", "Show FORGE (Ctrl+Shift+F)", true, None::<&str>)?;
            let browser =
                MenuItem::with_id(app, "show-browser", "Show Agent Browser", true, None::<&str>)?;
            let dash = MenuItem::with_id(app, "dashboard", "Open Dashboard", true, None::<&str>)?;
            let store =
                MenuItem::with_id(app, "store", "Open Store (DRIFT)", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit FORGE", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &browser, &dash, &store, &quit])?;

            let _tray = TrayIconBuilder::with_id("forge-tray")
                .menu(&menu)
                .icon(app.default_window_icon().unwrap().clone())
                .tooltip("FORGE — Your company. Running on autopilot. (Ctrl+Shift+F)")
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" | "dashboard" => {
                        if let Some(win) = app.get_webview_window("main") {
                            let _ = win.show();
                            let _ = win.set_focus();
                        }
                    }
                    "show-browser" => {
                        if let Some(win) = app.get_webview_window("agent-browser") {
                            let _ = win.show();
                            let _ = win.set_focus();
                        }
                    }
                    "store" => {
                        if let Some(win) = app.get_webview_window("main") {
                            let _ = win.show();
                            let _ = win.set_focus();
                        }
                    }
                    "quit" => app.exit(0),
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(win) = app.get_webview_window("main") {
                            let _ = win.show();
                            let _ = win.set_focus();
                        }
                    }
                })
                .build(app)?;

            #[cfg(debug_assertions)]
            {
                spawn_dev_sidecars(app.handle().clone());
                eprintln!(
                    "[FORGE] Dev: frontend → {} | dist fallback → {}",
                    DEV_FRONTEND_URL, PROD_DIST_HINT
                );
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            let label = window.label().to_string();
            if label == "agent-browser" {
                if let WindowEvent::CloseRequested { api, .. } = event {
                    let _ = window.hide();
                    api.prevent_close();
                }
                return;
            }
            // main window: Close → hide to tray instead of quitting
            if let WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .run(tauri::generate_context!())
        .expect("FORGE failed to launch");
}

#[cfg(debug_assertions)]
fn spawn_dev_sidecars(app: tauri::AppHandle) {
    use std::process::Command;
    use std::path::PathBuf;

    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("..");
    let bus_dir = root.join("business-os");
    let factory_dir = root.join("factory");

    let ports_open = |port: u16| -> bool {
        std::net::TcpStream::connect(format!("127.0.0.1:{}", port)).is_ok()
    };
    if ports_open(8000) && ports_open(3001) {
        eprintln!("[FORGE] Sidecars already running (:8000+:3001) — reusing");
        return;
    }
    if !ports_open(8000) {
        let bus = bus_dir.clone();
        std::thread::spawn(move || {
            eprintln!("[FORGE] Starting business-os on :8000 from {:?}", bus);
            let _ = Command::new("python")
                .args(["-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"])
                .current_dir(&bus)
                .spawn();
        });
    }
    if !ports_open(3001) {
        std::thread::spawn(move || {
            eprintln!("[FORGE] Starting factory on :3001 from {:?}", factory_dir);
            let _ = Command::new("cmd")
                .args(["/C", "npm run dev"])
                .current_dir(&factory_dir)
                .spawn();
        });
    }
    let _ = app;
}
