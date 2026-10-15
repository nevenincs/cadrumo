use crate::{app::Commands, environment, shell};
use cadrumo_application::{
    diagnostics::{Diagnostics, EventKind, HostOutcome, HostStage},
    error::application::{ApplicationError, ErrorCode, Operation, Result},
};
use serde::Serialize;
use std::{
    path::PathBuf,
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
};
use tauri::{Manager, State};

#[derive(Clone, Copy, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Phase {
    Environment,
    Runtime,
    Workspace,
}

#[derive(Clone, Serialize)]
pub struct Progress {
    phase: Phase,
    locale: Option<String>,
    failure: Option<ApplicationError>,
}

pub struct Startup {
    input: Mutex<Option<(PathBuf, environment::Parent)>>,
    progress: Mutex<Progress>,
    task: Mutex<Option<tauri::async_runtime::JoinHandle<()>>>,
    cancelled: AtomicBool,
    diagnostics: Arc<Diagnostics>,
    pub script: String,
    pub origins: Vec<String>,
}

impl Startup {
    pub fn new(
        root: PathBuf,
        parent: environment::Parent,
        diagnostics: Arc<Diagnostics>,
        script: String,
        origins: Vec<String>,
    ) -> Self {
        Self {
            input: Mutex::new(Some((root, parent))),
            progress: Mutex::new(Progress {
                phase: Phase::Environment,
                locale: None,
                failure: None,
            }),
            task: Mutex::new(None),
            cancelled: AtomicBool::new(false),
            diagnostics,
            script,
            origins,
        }
    }

    pub fn stage(&self, phase: Phase) {
        self.progress.lock().unwrap().phase = phase;
    }

    pub fn cancel(&self) {
        self.cancelled.store(true, Ordering::Release);
    }

    pub fn check_cancelled(&self) -> Result<()> {
        if self.cancelled.load(Ordering::Acquire) {
            Err(ApplicationError::new(
                ErrorCode::SessionUnavailable,
                Operation::Launch,
            ))
        } else {
            Ok(())
        }
    }

    pub fn failed(&self) -> bool {
        self.progress.lock().unwrap().failure.is_some()
    }

    pub async fn wait_cancelled(&self) {
        while !self.cancelled.load(Ordering::Acquire) {
            tokio::time::sleep(std::time::Duration::from_millis(50)).await;
        }
    }

    pub async fn settle(&self) {
        let task = self.task.lock().unwrap().take();
        if let Some(task) = task {
            let _ = task.await;
        }
    }
}

#[tauri::command]
fn startup_status(state: State<'_, Arc<Startup>>) -> Progress {
    state.progress.lock().unwrap().clone()
}

// The loading document calls this after its first paint, so package discovery
// and Python initialization cannot hold up the first visible feedback.
#[tauri::command]
fn startup_begin<R: tauri::Runtime>(app: tauri::AppHandle<R>, state: State<'_, Arc<Startup>>) {
    let mut task = state.task.lock().unwrap();
    let Some((root, parent)) = state.input.lock().unwrap().take() else {
        return;
    };
    let startup = state.inner().clone();
    *task = Some(tauri::async_runtime::spawn_blocking(move || {
        let outcome = tauri::async_runtime::block_on(async {
            startup.check_cancelled()?;
            crate::startup_logging::configure(&parent, &startup.diagnostics);
            startup
                .diagnostics
                .host_event(EventKind::StageStarted, HostStage::Environment);
            let launch = environment::resolve(root, &parent, startup.diagnostics.clone())
                .await
                .inspect_err(|error| {
                    startup
                        .diagnostics
                        .host_failure(HostStage::Environment, error.clone())
                })?;
            startup
                .diagnostics
                .host_outcome(HostStage::Environment, HostOutcome::Ready);
            startup.progress.lock().unwrap().locale = Some(launch.output_language.clone());
            startup.check_cancelled()?;
            crate::app::assemble(app.clone(), launch, &startup).await
        });
        if let Err(error) = outcome {
            startup.diagnostics.failure(error.clone());
            if startup.check_cancelled().is_ok() {
                startup.progress.lock().unwrap().failure = Some(error);
            }
            if let Some(manager) = app.try_state::<Arc<crate::manager::ManagerStart>>() {
                tauri::async_runtime::block_on(manager.close());
            }
            if let Some(sign_in) = app.try_state::<Arc<shell::sign_in::SignIn>>() {
                let _ = tauri::async_runtime::block_on(sign_in.stop());
            }
        }
    }));
}

pub fn commands<R: tauri::Runtime>() -> Commands<R> {
    crate::app::commands![startup_begin, startup_status]
}

pub fn plugin<R: tauri::Runtime>(diagnostics: Arc<Diagnostics>) -> tauri::plugin::TauriPlugin<R> {
    let activation = diagnostics.clone();
    let builder = tauri::plugin::Builder::new("cadrumo-startup").on_window_ready(move |window| {
        if window.label() == "startup" {
            shell::single_instance::attach(&window, activation.clone());
        }
    });
    #[cfg(windows)]
    let builder = builder.on_webview_ready(move |webview| {
        if webview.label() == "startup" {
            shell::webview::restrict(&webview, diagnostics.clone());
            shell::webview::observe(&webview, diagnostics.clone());
        }
    });
    builder.build()
}

#[cfg(test)]
mod tests {
    use super::*;
    use tauri::test::{mock_builder, mock_context, noop_assets};

    fn startup() -> Arc<Startup> {
        Arc::new(Startup::new(
            std::env::temp_dir().join("cadrumo-absent-startup-package"),
            environment::Parent {
                environment: vec![(
                    cadrumo_platform::ROOT_VARIABLE.into(),
                    std::env::temp_dir()
                        .join(format!("cadrumo-startup-test-{}", std::process::id()))
                        .into_os_string(),
                )],
                working_directory: std::env::temp_dir(),
            },
            Arc::new(Diagnostics::default()),
            String::new(),
            vec![],
        ))
    }

    #[test]
    fn package_failure_remains_available_without_assembling_services() {
        let startup = startup();
        let app = mock_builder()
            .manage(startup.clone())
            .build(mock_context(noop_assets()))
            .unwrap();
        startup_begin(app.handle().clone(), app.state::<Arc<Startup>>());
        tauri::async_runtime::block_on(startup.settle());
        assert!(startup.failed());
        assert_eq!(
            startup
                .progress
                .lock()
                .unwrap()
                .failure
                .as_ref()
                .unwrap()
                .code,
            ErrorCode::PackageUnavailable
        );
        assert!(
            app.try_state::<Arc<crate::manager::ManagerStart>>()
                .is_none()
        );
        startup_begin(app.handle().clone(), app.state::<Arc<Startup>>());
        assert!(startup.task.lock().unwrap().is_none());
    }

    #[test]
    fn closing_before_start_cancels_without_assembling_or_reporting_a_failure() {
        let startup = startup();
        startup.cancel();
        let app = mock_builder()
            .manage(startup.clone())
            .build(mock_context(noop_assets()))
            .unwrap();
        startup_begin(app.handle().clone(), app.state::<Arc<Startup>>());
        tauri::async_runtime::block_on(startup.settle());
        assert!(!startup.failed());
        assert!(
            app.try_state::<Arc<crate::manager::ManagerStart>>()
                .is_none()
        );
        assert_eq!(
            startup.check_cancelled().unwrap_err().code,
            ErrorCode::SessionUnavailable
        );
    }
}
