//! Coordinate Windows handle inheritance across application process creators.
//!
//! CreatePseudoConsole temporarily duplicates its pipe ends as inheritable.
//! A simultaneous std::process spawn can inherit them, keeping a closed
//! terminal's reader alive until that unrelated process exits. Rust's internal
//! spawn lock cannot coordinate with ConPTY. Both use this outer lock.

/// Run only the creation step here, including any temporary inheritable
/// handles. Release before waiting for output, readiness, or process exit.
/// Never nest calls. Other platforms need no Windows inheritance exclusion.
///
/// On Windows, with the `platform` feature, the creating thread also fails on an
/// unusable program image instead of raising a dialog. Such a dialog is modal and nobody
/// answers it, so the creation would never return and every later creation would wait on
/// the lock held here. The thread's earlier error mode returns when the step ends.
pub fn run<T>(create: impl FnOnce() -> T) -> T {
    #[cfg(windows)]
    let _guard = {
        static CREATION: std::sync::Mutex<()> = std::sync::Mutex::new(());
        CREATION.lock().unwrap_or_else(|error| error.into_inner())
    };
    // A refused mode only leaves the process's own mode in force, so creation goes on.
    #[cfg(all(windows, feature = "platform"))]
    let _headless = cadrumo_platform::error_mode::ThreadDialogSuppression::enter().ok();
    create()
}

#[cfg(all(test, windows, feature = "platform"))]
mod tests {
    use super::run;
    use std::{
        process::Command,
        sync::mpsc,
        time::{Duration, Instant},
    };

    /// Far above a refusal's milliseconds, far below the hung suite's own bound.
    const BOUND: Duration = Duration::from_secs(30);

    /// Creates a process from `image` on a thread of its own and reports its error, or
    /// panics when the creation has not returned within [`BOUND`].
    fn spawn_error(image: &std::path::Path) -> std::io::Error {
        let (sender, receiver) = mpsc::channel();
        let image = image.to_owned();
        std::thread::spawn(move || {
            let outcome = run(|| Command::new(&image).spawn());
            let _ = sender.send(outcome.map(|mut child| {
                let _ = child.kill();
                let _ = child.wait();
            }));
        });
        match receiver.recv_timeout(BOUND) {
            Ok(Err(error)) => error,
            Ok(Ok(())) => panic!("a file that is no program image was started"),
            Err(_) => panic!("the creation did not return: an error dialog is waiting"),
        }
    }

    #[test]
    fn a_file_that_is_no_program_image_fails_the_creation_at_once() {
        let folder = tempfile::tempdir().unwrap();
        let image = folder.path().join("not-a-program.exe");
        std::fs::write(&image, b"#!/bin/sh\nexit 3\n").unwrap();
        let started = Instant::now();
        let error = spawn_error(&image);
        // ERROR_BAD_EXE_FORMAT or ERROR_EXE_MACHINE_TYPE_MISMATCH.
        assert!(
            matches!(error.raw_os_error(), Some(193 | 216)),
            "unexpected error: {error}"
        );
        assert!(started.elapsed() < BOUND);
    }

    #[test]
    fn a_refused_creation_leaves_the_lock_free_for_the_next_one() {
        let folder = tempfile::tempdir().unwrap();
        let image = folder.path().join("not-a-program.exe");
        std::fs::write(&image, b"MZ").unwrap();
        spawn_error(&image);
        // A second creation reaches the lock the first one released.
        spawn_error(&image);
    }
}
