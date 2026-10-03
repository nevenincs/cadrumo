#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{io, path::PathBuf};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let data_directory = std::env::var_os("CADRUMO_DESKTOP_PREVIEW_DATA_DIR")
        .map(PathBuf::from)
        .filter(|path| path.is_absolute())
        .ok_or_else(|| {
            io::Error::other(
                "Set an absolute CADRUMO_DESKTOP_PREVIEW_DATA_DIR for this development preview.",
            )
        })?;
    if cfg!(target_os = "macos") {
        return Err(io::Error::other("Native macOS preview awaits WebView storage containment proof; use the frontend preview for UI work.").into());
    }
    tauri::Builder::default()
        .setup(move |app| {
            let title = app
                .config()
                .product_name
                .as_deref()
                .unwrap_or("Desktop preview");
            tauri::WebviewWindowBuilder::new(
                app,
                "main",
                tauri::WebviewUrl::App("index.html".into()),
            )
            .title(format!("{title} · Desktop preview"))
            .inner_size(1440.0, 1050.0)
            .min_inner_size(520.0, 600.0)
            .data_directory(data_directory)
            .build()?;
            Ok(())
        })
        .run(tauri::generate_context!())?;
    Ok(())
}
