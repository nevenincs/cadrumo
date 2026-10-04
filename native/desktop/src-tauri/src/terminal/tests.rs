use super::*;
#[cfg(feature = "live-package-tests")]
use std::path::PathBuf;

#[cfg(feature = "live-package-tests")]
fn wait_for(session: &mut Session, needle: &str) -> Vec<u8> {
    let deadline = Instant::now() + Duration::from_secs(45);
    let mut bytes = Vec::new();
    while Instant::now() < deadline {
        let output = session.read().unwrap();
        assert!(output.bytes.len() <= 65536, "unbounded PTY response");
        assert!(output.error.is_none(), "PTY read error: {:?}", output.error);
        if output.bytes.windows(4).any(|bytes| bytes == b"\x1b[6n") {
            session.input(b"\x1b[1;1R").unwrap();
        }
        bytes.extend(output.bytes);
        if String::from_utf8_lossy(&bytes).contains(needle) {
            return bytes;
        }
        assert!(
            output.exit_code.is_none(),
            "child exited before {needle}: {}",
            String::from_utf8_lossy(&bytes)
        );
        thread::sleep(Duration::from_millis(10));
    }
    panic!("no {needle}: {}", String::from_utf8_lossy(&bytes));
}

#[test]
fn dimensions_are_bounded() {
    assert!(size(0, 24).is_err());
    assert!(size(80, 1001).is_err());
    assert!(size(132, 40).is_ok());
}

#[test]
fn unfinished_worker_stays_owned_after_deadline_and_can_be_joined_on_retry() {
    let (release, wait) = mpsc::channel();
    let worker = thread::spawn(move || wait.recv().unwrap());
    let mut workers = Workers {
        reader: Some(worker),
        ..Workers::default()
    };
    let error = workers.join_until(Instant::now()).unwrap_err();
    assert_eq!(error.code, ErrorCode::CleanupFailed);
    assert!(workers.reader.is_some(), "timed-out worker was detached");
    release.send(()).unwrap();
    workers
        .join_until(Instant::now() + Duration::from_secs(1))
        .unwrap();
    assert!(workers.reader.is_none());
}

#[test]
fn panicked_worker_is_reported_as_cleanup_failure() {
    let mut workers = Workers {
        writer: Some(thread::spawn(|| panic!("controlled worker failure"))),
        ..Workers::default()
    };
    assert_eq!(
        workers
            .join_until(Instant::now() + Duration::from_secs(1))
            .unwrap_err()
            .code,
        ErrorCode::Panic,
    );
}

#[cfg(feature = "live-package-tests")]
#[tokio::test]
async fn packaged_pty_unicode_input_resize_output_exit_and_cleanup() {
    let root = PathBuf::from(
        std::env::var_os("CADRUMO_DESKTOP_PACKAGE_ROOT").expect("select real package"),
    );
    let launch = crate::environment::resolve(root, Arc::new(Diagnostics::default()))
        .await
        .unwrap();
    assert!(
        !launch
            .child
            .environment()
            .keys()
            .any(|key| key.to_string_lossy().starts_with("PYTHON"))
    );
    let script = "import os,sys,time; print('READY', flush=True); value=input(); print('UNICODE='+value,flush=True); print('SIZE='+str(os.get_terminal_size().columns),flush=True); print('X'*100000,flush=True); print('DONE',flush=True)";
    let mut session = Session::start(&launch, 80, 24, &["-u", "-c", script]).unwrap();
    wait_for(&mut session, "READY");
    session.resize(132, 40).unwrap();
    session.input("á漢字\r".as_bytes()).unwrap();
    let result = wait_for(&mut session, "DONE");
    let result = String::from_utf8_lossy(&result);
    assert!(result.contains("UNICODE=á漢字"));
    assert!(result.contains("SIZE=132"));
    let deadline = Instant::now() + Duration::from_secs(10);
    loop {
        let output = session.read().unwrap();
        if let Some(code) = output.exit_code {
            assert_eq!(code, 0);
            break;
        }
        assert!(Instant::now() < deadline, "child did not exit");
        thread::sleep(Duration::from_millis(10));
    }
    let mut blocked = Session::start(
        &launch,
        80,
        24,
        &[
            "-u",
            "-c",
            "import time; print('WAITING',flush=True); time.sleep(120)",
        ],
    )
    .unwrap();
    wait_for(&mut blocked, "WAITING");
    let began = Instant::now();
    blocked.stop().unwrap();
    assert!(began.elapsed() < Duration::from_secs(5));
    assert!(blocked.child.try_wait().unwrap().is_some());
    assert!(blocked.workers.reap_finished().unwrap());

    let mut flood = Session::start(&launch, 80, 24, &["-u", "-c",
        "import time; print('FLOOD',flush=True); time.sleep(0.2); print('Z'*10000000,flush=True); time.sleep(120)"]).unwrap();
    wait_for(&mut flood, "FLOOD");
    thread::sleep(Duration::from_millis(500));
    let began = Instant::now();
    flood.stop().unwrap();
    assert!(
        began.elapsed() < Duration::from_secs(5),
        "full output queue blocked cleanup"
    );
    assert!(flood.child.try_wait().unwrap().is_some());
    assert!(flood.workers.reap_finished().unwrap());
}

#[cfg(feature = "live-package-tests")]
#[tokio::test]
async fn real_packaged_tui_draws_in_the_pty() {
    let root = PathBuf::from(
        std::env::var_os("CADRUMO_DESKTOP_PACKAGE_ROOT").expect("select real package"),
    );
    let launch = crate::environment::resolve(root, Arc::new(Diagnostics::default()))
        .await
        .unwrap();
    let mut session = Session::start(&launch, 120, 40, &["-m", "cadrumo.entrypoints.tui"]).unwrap();
    let output = wait_for(&mut session, "\u{1b}[?1049h");
    assert!(!output.is_empty());
    session.resize(100, 30).unwrap();
    session.input(b"\x1b[B\t").unwrap();
    session.stop().unwrap();
    assert!(session.child.try_wait().unwrap().is_some());
    assert!(session.workers.reap_finished().unwrap());
}
