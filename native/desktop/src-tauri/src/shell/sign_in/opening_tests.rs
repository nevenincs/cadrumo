//! Real pipe barriers for window cancellation before a runtime hello exists.
use super::*;
use std::{
    io::{BufRead, BufReader, Write},
    os::windows::process::CommandExt,
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::mpsc,
    time::Duration,
};

struct StalledHello {
    root: PathBuf,
    child: Child,
    hello: mpsc::Receiver<()>,
    reader: Option<std::thread::JoinHandle<()>>,
}

impl StalledHello {
    fn new() -> Self {
        let root = std::env::temp_dir().join(format!(
            "cadrumo-open-{}",
            cadrumo_application::runtime_client::request_id()
        ));
        std::fs::create_dir_all(&root).unwrap();
        let endpoint = cadrumo_application::runtime_client::Endpoint::of(&root).unwrap();
        let name = endpoint.pipe_name.strip_prefix(r"\\.\pipe\").unwrap();
        let script = format!(
            r#"
$pipe = [System.IO.Pipes.NamedPipeServerStream]::new('{name}', [System.IO.Pipes.PipeDirection]::InOut, 1, [System.IO.Pipes.PipeTransmissionMode]::Byte, [System.IO.Pipes.PipeOptions]::Asynchronous)
[Console]::Out.WriteLine('listening'); [Console]::Out.Flush()
$pipe.WaitForConnection()
$header = [byte[]]::new(5); $at = 0
while ($at -lt 5) {{ $got = $pipe.Read($header, $at, 5-$at); if ($got -eq 0) {{ exit 2 }}; $at += $got }}
$length = ([int]$header[1] -shl 24) -bor ([int]$header[2] -shl 16) -bor ([int]$header[3] -shl 8) -bor [int]$header[4]
$body = [byte[]]::new($length); $at = 0
while ($at -lt $length) {{ $got = $pipe.Read($body, $at, $length-$at); if ($got -eq 0) {{ exit 3 }}; $at += $got }}
[Console]::Out.WriteLine('hello'); [Console]::Out.Flush()
$null = [Console]::In.ReadLine(); $pipe.Dispose()
"#
        );
        let mut child = Command::new("powershell.exe")
            .args([
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                &script,
            ])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .creation_flags(0x08000000)
            .spawn()
            .unwrap();
        let mut output = BufReader::new(child.stdout.take().unwrap());
        let (listening, listened) = mpsc::channel();
        let (hello, heard) = mpsc::channel();
        let reader = std::thread::spawn(move || {
            let mut line = String::new();
            output.read_line(&mut line).unwrap();
            if line.trim() == "listening" {
                let _ = listening.send(());
            }
            line.clear();
            output.read_line(&mut line).unwrap();
            if line.trim() == "hello" {
                let _ = hello.send(());
            }
        });
        let server = Self {
            root,
            child,
            hello: heard,
            reader: Some(reader),
        };
        listened.recv_timeout(Duration::from_secs(10)).unwrap();
        server
    }
    fn native(&self) -> watch::Native {
        watch::Native {
            storage_root: self.root.clone(),
            product_version: "synthetic".into(),
        }
    }
    fn reached(&self) {
        self.hello.recv_timeout(Duration::from_secs(10)).unwrap();
    }
}
impl Drop for StalledHello {
    fn drop(&mut self) {
        if let Some(mut input) = self.child.stdin.take() {
            let _ = input.write_all(b"done\n");
        }
        let _ = self.child.kill();
        let _ = self.child.wait();
        if let Some(reader) = self.reader.take() {
            let _ = reader.join();
        }
        let _ = std::fs::remove_dir(&self.root);
    }
}

fn window(native: watch::Native) -> Arc<SignIn> {
    let absent = || Err(failure(ErrorCode::PackageUnavailable));
    Arc::new(SignIn {
        child: absent(),
        runtime: absent(),
        service: absent(),
        native: Ok(native.clone()),
        watch: watch::Watch::new(Ok(native)),
        children: Arc::new(Children::new(Arc::new(
            cadrumo_application::diagnostics::Diagnostics::default(),
        ))),
        observation: observation::Observer::default(),
        person: std::sync::Mutex::new(std::sync::Weak::new()),
        signed_in: std::sync::Mutex::new(None),
        person_events: tokio::sync::broadcast::channel(16).0,
        custody: Custody::default(),
        closed: std::sync::atomic::AtomicBool::new(false),
        lifecycle: std::sync::Mutex::new(()),
        signing_in: std::sync::Mutex::new(None),
        openings: std::sync::Mutex::new(Vec::new()),
    })
}

#[tokio::test(flavor = "multi_thread")]
async fn watch_close_cancels_a_stalled_hello_and_cannot_publish_late() {
    let server = StalledHello::new();
    let watch = watch::Watch::new(Ok(server.native()));
    let watching = watch.clone();
    let read = tokio::spawn(async move { watching.current().await });
    tokio::task::block_in_place(|| server.reached());
    let closing = watch.clone();
    tokio::time::timeout(
        Duration::from_secs(5),
        tokio::task::spawn_blocking(move || closing.close()),
    )
    .await
    .unwrap()
    .unwrap();
    assert!(
        tokio::time::timeout(Duration::from_secs(5), read)
            .await
            .unwrap()
            .unwrap()
            .is_err()
    );
    assert!(watch.latest().is_err());
}

#[tokio::test(flavor = "multi_thread")]
async fn window_stop_cancels_a_stalled_login_open_and_wipes_its_password() {
    let server = StalledHello::new();
    let window = window(server.native());
    let signing = window.clone();
    let login = tokio::task::spawn_blocking(move || {
        signing.sign_in(Some("synthetic"), Zeroizing::new(b"one-proof".to_vec()))
    });
    tokio::task::block_in_place(|| server.reached());
    let pending = window.signing_in.lock().unwrap().as_ref().unwrap().clone();
    tokio::time::timeout(Duration::from_secs(5), window.stop())
        .await
        .unwrap()
        .unwrap();
    assert!(pending.password.lock().unwrap().is_empty());
    assert!(!matches!(
        tokio::time::timeout(Duration::from_secs(5), login)
            .await
            .unwrap()
            .unwrap(),
        Ok(SignInResult::SignedIn { .. })
    ));
    assert!(window.signed_in.lock().unwrap().is_none());
}

#[tokio::test(flavor = "multi_thread")]
async fn window_stop_cancels_a_person_preparation_open_before_supervisor_join() {
    let server = StalledHello::new();
    let window = window(server.native());
    let preparing = window.clone();
    let prepare = tokio::task::spawn_blocking(move || {
        preparing.connect(cadrumo_application::runtime_client::TimeoutWait::new().deadline())
    });
    tokio::task::block_in_place(|| server.reached());
    window.request_stop();
    assert!(
        tokio::time::timeout(Duration::from_secs(5), prepare)
            .await
            .unwrap()
            .unwrap()
            .is_err()
    );
    window.stop().await.unwrap();
}
