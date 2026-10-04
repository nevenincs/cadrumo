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
    let parent = crate::environment::Parent::current().unwrap();
    let launch = crate::environment::resolve(root, &parent, Arc::new(Diagnostics::default()))
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
    let parent = crate::environment::Parent::current().unwrap();
    let launch = crate::environment::resolve(root, &parent, Arc::new(Diagnostics::default()))
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

#[cfg(feature = "live-package-tests")]
mod relocated {
    use super::*;
    use crate::environment::Parent;
    use cadrumo_application::child::ChildConfiguration;
    use std::{
        fs,
        path::{Path, PathBuf},
    };

    // Reports the storage root this process resolves through both owners.
    const PROBE: &str = "import json, os, sys; from cadrumo.core.config import load_settings; from cadrumo.core.storage_environment import configured_storage_root; open(sys.argv[1], 'w', encoding='utf-8').write(json.dumps([str(configured_storage_root()), str(load_settings().cadrumo_local_storage_root), os.getcwd()]))";

    struct Scratch(PathBuf);
    impl Drop for Scratch {
        fn drop(&mut self) {
            if let Err(error) = fs::remove_dir_all(&self.0) {
                eprintln!("relocated package left at {:?}: {error}", self.0);
            }
        }
    }

    fn settings_storage_names() -> Vec<String> {
        let contract: serde_json::Value =
            serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json"))).unwrap();
        serde_json::from_value(contract["storage_environment_allowlist"].clone()).unwrap()
    }

    fn inside_project(path: &Path) -> bool {
        path.ancestors()
            .any(|ancestor| ancestor.join("pyproject.toml").is_file())
    }

    // Hard links keep relocation cheap on one volume; copies cover the rest.
    fn relocate(from: &Path, to: &Path) {
        fs::create_dir_all(to).unwrap();
        for entry in fs::read_dir(from).unwrap() {
            let entry = entry.unwrap();
            let kind = entry.file_type().unwrap();
            let target = to.join(entry.file_name());
            assert!(
                !kind.is_symlink(),
                "package contains a link: {:?}",
                entry.path()
            );
            if kind.is_dir() {
                relocate(&entry.path(), &target);
            } else if fs::hard_link(entry.path(), &target).is_err() {
                fs::copy(entry.path(), &target).unwrap();
            }
        }
    }

    fn read_report(report: &Path) -> Vec<PathBuf> {
        let values: Vec<String> =
            serde_json::from_str(&fs::read_to_string(report).unwrap()).unwrap();
        fs::remove_file(report).unwrap();
        values.into_iter().map(PathBuf::from).collect()
    }

    fn probe(configuration: &ChildConfiguration, report: &Path) -> Vec<PathBuf> {
        let status = configuration
            .command()
            .arg("-c")
            .arg(PROBE)
            .arg(report)
            .status()
            .unwrap();
        assert!(status.success());
        read_report(report)
    }

    fn settle(session: &mut Session) -> Option<u32> {
        let deadline = Instant::now() + Duration::from_secs(60);
        loop {
            let output = session.read().unwrap();
            assert!(output.error.is_none(), "PTY read error: {:?}", output.error);
            if output.bytes.windows(4).any(|bytes| bytes == b"\x1b[6n") {
                session.input(b"\x1b[1;1R").unwrap();
            }
            if output.exit_code.is_some() || Instant::now() >= deadline {
                return output.exit_code;
            }
            thread::sleep(Duration::from_millis(10));
        }
    }

    fn assert_resolves(values: &[PathBuf], storage: &Path, cwd: &Path) {
        assert_eq!(values[0], storage, "configured_storage_root");
        assert_eq!(values[1], storage, "Settings.cadrumo_local_storage_root");
        assert_eq!(values[2], cwd, "child working directory");
    }

    #[tokio::test]
    async fn every_child_kind_resolves_the_projected_storage_root_from_any_directory() {
        let package = PathBuf::from(
            std::env::var_os("CADRUMO_DESKTOP_PACKAGE_ROOT").expect("select real package"),
        );
        let base = std::env::temp_dir().join(format!(
            "cadrumo-relocated-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        assert!(
            !inside_project(&base),
            "the temporary directory must lie outside any project for an installed-mode layout"
        );
        let scratch = Scratch(base);
        let root = scratch.0.join("package");
        relocate(&package, &root);
        let launch_directory = scratch.0.join("launch");
        let outside = scratch.0.join("outside");
        let reports = scratch.0.join("reports");
        for directory in [&launch_directory, &outside, &reports] {
            fs::create_dir_all(directory).unwrap();
        }
        let storage_names = settings_storage_names();
        let parent = Parent {
            environment: std::env::vars_os()
                .filter(|(key, _)| {
                    !storage_names.contains(&key.to_string_lossy().to_ascii_uppercase())
                })
                .collect(),
            working_directory: launch_directory.clone(),
        };
        let launch = crate::environment::resolve(root, &parent, Arc::new(Diagnostics::default()))
            .await
            .unwrap();
        // Installed mode anchors the default root at the launch directory.
        let storage = launch.working_directory.clone();
        assert_eq!(storage, launch_directory.join("var").join("storage"));
        let pinned: Vec<_> = launch
            .child
            .environment()
            .iter()
            .filter(|(key, _)| storage_names.contains(&key.to_string_lossy().to_ascii_uppercase()))
            .map(|(_, value)| PathBuf::from(value))
            .collect();
        assert_eq!(pinned, std::slice::from_ref(&storage));

        // python kind, through the terminal session launch path.
        let report = reports.join("python.json");
        let report_argument = report.to_string_lossy().into_owned();
        let mut python =
            Session::start(&launch, 120, 40, &["-u", "-c", PROBE, &report_argument]).unwrap();
        assert_eq!(settle(&mut python), Some(0));
        python.stop().unwrap();
        assert_resolves(&read_report(&report), &storage, &storage);

        // tui kind: the unchanged module launch through the same session path.
        let mut tui = Session::start(&launch, 120, 40, &["-m", "cadrumo.entrypoints.tui"]).unwrap();
        settle(&mut tui);
        tui.stop().unwrap();

        // A child whose working directory lies outside the storage root.
        let elsewhere = ChildConfiguration::new(
            launch.child.executable().to_owned(),
            outside.clone(),
            launch.child.environment().clone(),
        )
        .unwrap();
        assert_resolves(
            &probe(&elsewhere, &reports.join("outside.json")),
            &storage,
            &outside,
        );

        // The CLI passthrough keeps the caller's directory.
        let passthrough = crate::headless(&launch, launch_directory.clone()).unwrap();
        assert_resolves(
            &probe(&passthrough, &reports.join("passthrough.json")),
            &storage,
            &launch_directory,
        );
        let version = passthrough
            .command()
            .args(["-u", "-c", crate::CLI_ENTRYPOINT, "--version"])
            .output()
            .unwrap();
        assert!(version.status.success());

        for directory in [&storage, &outside] {
            assert!(
                !directory.join("var").exists(),
                "a child re-resolved storage beneath {directory:?}"
            );
        }

        // Without the pin, a child started in the storage root nests a second
        // root beneath it: the defect this regression guards against.
        let mut unpinned = launch.child.environment().clone();
        unpinned
            .retain(|key, _| !storage_names.contains(&key.to_string_lossy().to_ascii_uppercase()));
        let defect = ChildConfiguration::new(
            launch.child.executable().to_owned(),
            storage.clone(),
            unpinned,
        )
        .unwrap();
        let values = probe(&defect, &reports.join("unpinned.json"));
        assert_eq!(values[0], storage.join("var").join("storage"));
    }
}
