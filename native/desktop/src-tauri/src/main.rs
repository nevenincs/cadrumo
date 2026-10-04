mod gui;
mod mode;
mod package;
mod terminal;

use cadrumo_application::{
    child::ChildConfiguration,
    diagnostics::{Diagnostics, EventKind},
    failure::{Failure, FailureCode, Operation, Result},
    process,
};
use std::{
    ffi::OsString,
    path::PathBuf,
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
    },
};

const CLI_ENTRYPOINT: &str = r#"
import sys
from importlib.metadata import distribution
from cadrumo.core.product_identity import PRODUCT_IDENTITY
sys.argv[0] = PRODUCT_IDENTITY.cli_executable
entry = next(e for e in distribution(PRODUCT_IDENTITY.distribution).entry_points
             if e.group == 'console_scripts' and e.name == PRODUCT_IDENTITY.cli_executable)
entry.load()()
"#;

fn run(diagnostics: Arc<Diagnostics>) -> Result<i32> {
    let arguments = std::env::args_os().skip(1).collect();
    let mode = mode::select(arguments, mode::desktop_available());
    diagnostics.event(EventKind::HostStarted, None, None);
    let root = match std::env::var_os("CADRUMO_DESKTOP_PACKAGE_ROOT").filter(|v| !v.is_empty()) {
        Some(path) => PathBuf::from(path),
        None => std::env::current_exe()
            .map_err(|e| launch_error().caused_by(e))?
            .parent()
            .ok_or_else(launch_error)?
            .to_owned(),
    };
    let launch = tauri::async_runtime::block_on(package::resolve(root, diagnostics.clone()))?;
    match mode? {
        mode::Mode::Gui => gui::run(launch),
        mode::Mode::Cli(arguments) => {
            diagnostics.event(EventKind::HeadlessSelected, None, None);
            let configuration = ChildConfiguration::new(
                launch.child.executable().to_owned(),
                std::env::current_dir().map_err(|e| launch_error().caused_by(e))?,
                launch.child.environment().clone(),
            )
            .map_err(|e| launch_error().caused_by(e))?;
            let mut forwarded: Vec<OsString> =
                vec!["-u".into(), "-c".into(), CLI_ENTRYPOINT.into()];
            forwarded.extend(arguments);
            let cancelled = Arc::new(AtomicBool::new(false));
            let interrupted = cancelled.clone();
            ctrlc::set_handler(move || interrupted.store(true, Ordering::Release))
                .map_err(|e| launch_error().caused_by(e))?;
            process::passthrough(&configuration, &forwarded, diagnostics, cancelled)
        }
    }
}
fn launch_error() -> Failure {
    Failure::new(FailureCode::EnvironmentFailed, Operation::Launch)
}

fn main() {
    let diagnostics = Arc::new(Diagnostics::default());
    // Report after unwinding: hooks run before locks held by the panicking code release.
    // Suppress Rust's default hook, which can expose private payloads on stderr.
    std::panic::set_hook(Box::new(|_| {}));
    let outcome =
        std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| run(diagnostics.clone())))
            .unwrap_or_else(|_| Err(Failure::new(FailureCode::Panic, Operation::Launch)));
    let code = match outcome {
        Ok(code) => code,
        Err(error) => {
            diagnostics.failure(error.clone());
            eprintln!(
                "{}",
                serde_json::to_string(&error).unwrap_or_else(|_| "application_error".into())
            );
            match error.code {
                FailureCode::InvalidArguments => 64,
                FailureCode::DesktopUnavailable => 69,
                _ => 1,
            }
        }
    };
    diagnostics.event(EventKind::HostStopped, None, None);
    std::process::exit(code);
}
