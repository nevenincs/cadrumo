//! A process that contains itself takes everything it started down with it.
#![cfg(windows)]

use cadrumo_manager::process_job::ProcessJob;
use std::{
    io::{BufRead, BufReader},
    os::windows::process::CommandExt,
    process::{Command, Stdio},
    time::{Duration, Instant},
};

const HELPER: &str = "CADRUMO_APPLICATION_JOB_HELPER";
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

fn powershell() -> Command {
    let root = std::env::var_os("SystemRoot").expect("SystemRoot");
    let mut command = Command::new(
        std::path::Path::new(&root).join(r"System32\WindowsPowerShell\v1.0\powershell.exe"),
    );
    command.creation_flags(CREATE_NO_WINDOW);
    command
}

fn alive(pid: u32) -> bool {
    let script = format!("if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ 'alive' }}");
    let output = powershell()
        .args(["-NoProfile", "-NonInteractive", "-Command", &script])
        .output()
        .expect("process query");
    String::from_utf8_lossy(&output.stdout).contains("alive")
}

/// Run only as the child of the test below: contain itself, start a child that
/// would otherwise run for minutes, report it, and end without any cleanup.
#[test]
fn helper() {
    if std::env::var_os(HELPER).is_none() {
        return;
    }
    let job = ProcessJob::new().expect("job");
    job.contain_current().expect("contain the current process");
    let child = powershell()
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Start-Sleep -Seconds 300",
        ])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .expect("long-lived child");
    println!("CHILD={}", child.id());
    std::mem::forget(job);
    std::process::exit(0);
}

#[test]
fn ending_the_contained_process_ends_what_it_started() {
    let mut helper = Command::new(std::env::current_exe().unwrap())
        .args(["--exact", "helper", "--nocapture", "--test-threads=1"])
        .env(HELPER, "1")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .creation_flags(CREATE_NO_WINDOW)
        .spawn()
        .unwrap();
    let child = BufReader::new(helper.stdout.take().unwrap())
        .lines()
        .map_while(Result::ok)
        .find_map(|line| {
            line.rsplit_once("CHILD=")
                .and_then(|(_, pid)| pid.trim().parse::<u32>().ok())
        })
        .expect("the helper reports its child");
    assert!(helper.wait().unwrap().success());
    let deadline = Instant::now() + Duration::from_secs(10);
    while alive(child) {
        assert!(
            Instant::now() < deadline,
            "the child outlived its contained parent"
        );
        std::thread::sleep(Duration::from_millis(100));
    }
}
