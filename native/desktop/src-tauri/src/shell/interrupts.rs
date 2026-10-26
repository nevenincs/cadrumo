//! Ctrl+C in a terminal tab reaches its child.
//!
//! A host started in a new process group carries the Windows "ignore
//! Ctrl+C" attribute, and every terminal child would inherit it: the console
//! would deliver Ctrl+C and the child would drop it. The host clears the
//! attribute once, before any terminal child exists.
#![cfg(windows)]

use cadrumo_application::{
    diagnostics::Diagnostics,
    error::application::{ApplicationError, ErrorCode, Operation},
};

/// Clears the inherited attribute. A failure is recorded and the host keeps
/// running, since only Ctrl+C delivery to terminal children depends on it.
pub fn restore(diagnostics: &Diagnostics) {
    if let Err(error) = cadrumo_platform::desktop::ignore_console_interrupts(false) {
        diagnostics.failure(
            ApplicationError::new(ErrorCode::EnvironmentFailed, Operation::Terminal)
                .caused_by(error),
        );
    }
}

// The attribute is process-wide; run with one test thread, as the host's test
// recipe does, so no other test starts a child while it is set.
#[cfg(all(test, feature = "live-package-tests"))]
mod tests {
    use super::*;
    use portable_pty::{CommandBuilder, PtySize, native_pty_system};
    use std::{
        io::{Read, Write},
        path::PathBuf,
        sync::{Arc, Mutex},
        time::{Duration, Instant},
    };

    const SCRIPT: &str = "import time\n\
print('READY', flush=True)\n\
try:\n    time.sleep(8)\n    print('SLEPT', flush=True)\n\
except KeyboardInterrupt:\n    print('INTERRUPTED', flush=True)\n";

    fn interpreter() -> PathBuf {
        let root = PathBuf::from(
            std::env::var_os("CADRUMO_DESKTOP_PACKAGE_ROOT").expect("select real package"),
        );
        let contract: serde_json::Value =
            serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json"))).unwrap();
        root.join(contract["layout"]["paths"]["executable"].as_str().unwrap())
    }

    fn text(output: &Mutex<Vec<u8>>) -> String {
        String::from_utf8_lossy(&output.lock().unwrap()).into_owned()
    }

    fn wait_for(output: &Mutex<Vec<u8>>, markers: &[&str], deadline: Duration) -> Option<String> {
        let started = Instant::now();
        while started.elapsed() < deadline {
            let seen = text(output);
            if let Some(found) = markers.iter().find(|marker| seen.contains(**marker)) {
                return Some((*found).to_owned());
            }
            std::thread::sleep(Duration::from_millis(50));
        }
        None
    }

    /// Starts a Python REPL-style child in a pseudo console, sends Ctrl+C
    /// while it sleeps, and reports which way the sleep ended.
    fn ending_after_ctrl_c() -> String {
        let pty = native_pty_system()
            .openpty(PtySize {
                rows: 24,
                cols: 80,
                pixel_width: 0,
                pixel_height: 0,
            })
            .unwrap();
        let mut command = CommandBuilder::new(interpreter());
        command.args(["-c", SCRIPT]);
        let mut child = pty.slave.spawn_command(command).unwrap();
        drop(pty.slave);
        let output = Arc::new(Mutex::new(Vec::new()));
        let mut reader = pty.master.try_clone_reader().unwrap();
        let sink = output.clone();
        let pump = std::thread::spawn(move || {
            let mut buffer = [0; 4096];
            while let Ok(count) = reader.read(&mut buffer) {
                if count == 0 {
                    break;
                }
                sink.lock().unwrap().extend_from_slice(&buffer[..count]);
            }
        });
        let mut writer = pty.master.take_writer().unwrap();
        // The pseudo console asks for the cursor position before it lets the
        // child write; a terminal answers, as the shell's terminal does.
        let asked = wait_for(&output, &["[6n"], Duration::from_secs(30));
        assert!(asked.is_some(), "{:?}", text(&output));
        writer.write_all(b"[1;1R").unwrap();
        writer.flush().unwrap();
        let ready = wait_for(&output, &["READY"], Duration::from_secs(30));
        assert!(ready.is_some(), "{:?}", text(&output));
        writer.write_all(b"\x03").unwrap();
        writer.flush().unwrap();
        let ending = wait_for(&output, &["INTERRUPTED", "SLEPT"], Duration::from_secs(30))
            .expect("the child ends its sleep one way or the other");
        child.wait().unwrap();
        drop(writer);
        drop(pty.master);
        pump.join().unwrap();
        ending
    }

    /// Clears the attribute even when an assertion fails, so later tests in
    /// this process start children normally.
    struct Cleared;
    impl Drop for Cleared {
        fn drop(&mut self) {
            let _ = cadrumo_platform::desktop::ignore_console_interrupts(false);
        }
    }

    #[test]
    fn terminal_children_receive_ctrl_c_once_the_inherited_attribute_is_cleared() {
        let _cleared = Cleared;
        // As if the host had been started in a new process group.
        cadrumo_platform::desktop::ignore_console_interrupts(true).unwrap();
        // Control: with the attribute inherited the child ignores Ctrl+C.
        assert_eq!(ending_after_ctrl_c(), "SLEPT");
        let diagnostics = Diagnostics::default();
        restore(&diagnostics);
        assert!(diagnostics.snapshot(0).events.is_empty());
        assert_eq!(ending_after_ctrl_c(), "INTERRUPTED");
    }
}
