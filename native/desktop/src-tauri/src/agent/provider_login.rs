//! Forward a console login's cache invalidation. Only the service reads login status.
use cadrumo_platform::file_changes::{FileChanges, Wake, Waker};
use std::{
    path::Path,
    sync::Arc,
    sync::atomic::{AtomicBool, Ordering},
    thread,
};
use tauri::{AppHandle, Emitter, Runtime};

pub(super) struct Watch {
    stop: Arc<AtomicBool>,
    wake: Waker,
    worker: Option<thread::JoinHandle<()>>,
}

impl Watch {
    pub(super) fn start<R: Runtime>(app: AppHandle<R>, storage: &Path) -> Option<Self> {
        let directory = storage.join("agent").join("login-notices");
        if let Err(error) = std::fs::create_dir_all(&directory) {
            log::warn!("could not watch provider login notices: {}", error.kind());
            return None;
        }
        let modified = || {
            std::fs::metadata(&directory)
                .and_then(|m| m.modified())
                .ok()
        };
        let mut changes = FileChanges::new(vec![directory.clone()]);
        let mut last = modified();
        let wake = changes.waker();
        let stop = Arc::new(AtomicBool::new(false));
        let stopping = stop.clone();
        let worker = thread::Builder::new()
            .name("provider-login-notices".into())
            .spawn(move || {
                while !stopping.load(Ordering::Acquire) {
                    let why = changes.wait(None);
                    if stopping.load(Ordering::Acquire) {
                        break;
                    }
                    let current = std::fs::metadata(&directory)
                        .and_then(|m| m.modified())
                        .ok();
                    if why == Wake::Changed || current != last {
                        last = current;
                        let _ = app.emit("provider-login-changed", ());
                    }
                }
            })
            .ok()?;
        Some(Self {
            stop,
            wake,
            worker: Some(worker),
        })
    }
}

impl Drop for Watch {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Release);
        self.wake.wake();
        if let Some(worker) = self.worker.take() {
            let _ = worker.join();
        }
    }
}
