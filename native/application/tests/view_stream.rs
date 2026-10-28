//! The window's view lane against the runtime's own relay and a worker's view sink, in real
//! processes.
//!
//! A Python peer runs `cadrumo_runtime.host.tests.view_stream_native_peer` through the
//! CMake-configured builder interpreter. It serves a private storage root's runtime pipe
//! with the runtime's handshake, answers `view_attach` and `view_connect` through the
//! runtime's view relay, and holds one running view whose worker sink offers a new
//! synthetic image every few milliseconds. This process is the window: it connects as the
//! desktop does, attaches, opens the lane, and drives credit, input, a download, an upload,
//! the panel's close and a sign-out across the real pipes. The peer reports, one JSON line
//! each, what reached the worker.

#![cfg(all(windows, feature = "platform"))]

use cadrumo_application::runtime_client::{Admitted, Cohort, Connection, Endpoint, Refusal};
use cadrumo_application::value::Sha256Digest;
use cadrumo_application::view_stream::attach::view_attach;
use cadrumo_application::view_stream::chunks::AssembledImage;
use cadrumo_application::view_stream::documents::{
    TextInput, ViewClosedReason, ViewInputEvent, ViewNavigateVerb,
};
use cadrumo_application::view_stream::lane::{
    UploadFile, UploadOutcome, ViewEnd, ViewEvent, ViewLane,
};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::io::{BufRead, BufReader, Cursor, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::mpsc;
use std::thread;
use std::time::{Duration, Instant};

const VERSION: &str = "0.0.0-view-stream-test";
const WAIT: Duration = Duration::from_secs(30);
const TYPED: &str = "tecleado-93b2f6";
const DOWNLOAD_WINDOW: u8 = 32;

fn repository_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("..").join("..")
}

fn deadline() -> Instant {
    Instant::now() + Duration::from_secs(10)
}

/// The synthetic page's image for `sequence`, as the peer makes it.
fn image_bytes(sequence: u32) -> Vec<u8> {
    let mut hasher = Sha256::new();
    hasher.update(b"view-frame");
    hasher.update(u64::from(sequence).to_be_bytes());
    hasher.finalize().as_slice().repeat(6400)
}

/// The runtime and worker side; dropping it ends its input, so it closes the view and exits.
struct Peer {
    child: Child,
    input: Option<ChildStdin>,
    events: mpsc::Receiver<Value>,
    unclaimed: Vec<Value>,
}

impl Peer {
    fn start(root: &Path) -> Self {
        let python = std::env::var_os("CADRUMO_TEST_PYTHON")
            .expect("CMake supplies the configured Python view peer interpreter");
        let mut child = Command::new(python)
            .args([
                "-B",
                "-m",
                "cadrumo_runtime.host.tests.view_stream_native_peer",
            ])
            .arg(root)
            .arg(VERSION)
            .current_dir(repository_root())
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .expect("start the configured Python view peer");
        let input = child.stdin.take();
        let output = BufReader::new(child.stdout.take().expect("peer stdout"));
        let (sender, events) = mpsc::channel();
        thread::spawn(move || {
            for line in output.lines() {
                let Ok(line) = line else { break };
                let event =
                    serde_json::from_str(&line).expect("the peer writes one JSON event a line");
                if sender.send(event).is_err() {
                    break;
                }
            }
        });
        Self {
            child,
            input,
            events,
            unclaimed: Vec::new(),
        }
    }

    /// The first event named `name` the peer reported, waiting for it; the peer's threads
    /// report independently, so events of other names stay for later expectations.
    fn expect(&mut self, name: &str) -> Value {
        if let Some(index) = self
            .unclaimed
            .iter()
            .position(|event| event["event"] == name)
        {
            return self.unclaimed.remove(index);
        }
        let until = Instant::now() + WAIT;
        loop {
            let remaining = until.saturating_duration_since(Instant::now());
            let event = self.events.recv_timeout(remaining).unwrap_or_else(|_| {
                panic!(
                    "the peer reported no {name} event; unclaimed: {:?}",
                    self.unclaimed
                )
            });
            if event["event"] == name {
                return event;
            }
            self.unclaimed.push(event);
        }
    }

    fn send(&mut self, command: &str) {
        let input = self.input.as_mut().expect("peer input");
        writeln!(input, "{command}").expect("send to peer");
        input.flush().expect("flush to peer");
    }
}

impl Drop for Peer {
    fn drop(&mut self) {
        drop(self.input.take());
        let _ = self.child.wait();
    }
}

fn member(event: &Value, name: &str) -> String {
    event[name]
        .as_str()
        .unwrap_or_else(|| panic!("the event names {name}"))
        .to_owned()
}

/// A window holding the session the peer's view was submitted from.
struct Window {
    endpoint: Endpoint,
    cohort: Cohort,
    connection: Connection,
    held: Admitted,
    operation_id: String,
}

impl Window {
    fn connect(root: &Path, ready: &Value) -> Self {
        let endpoint = Endpoint::of(root).expect("the storage root names an endpoint");
        let cohort = Cohort {
            product_version: VERSION.to_owned(),
            authority_generation: None,
        };
        let connection =
            Connection::open(&endpoint, &cohort, deadline()).expect("connect to the runtime");
        let held = Admitted {
            profile_id: member(ready, "profile_id"),
            session_id: member(ready, "session_id"),
            connection_id: member(ready, "connection_id"),
            runtime_boot_id: member(ready, "runtime_boot_id"),
            expires_at: None,
            session_persisted: None,
            signed_out_profile_ids: Vec::new(),
        };
        Self {
            endpoint,
            cohort,
            connection,
            held,
            operation_id: member(ready, "operation_id"),
        }
    }

    fn open_lane(&self) -> ViewLane {
        let grant = view_attach(&self.connection, &self.held, &self.operation_id, deadline())
            .expect("the runtime grants the session that submitted the view");
        ViewLane::open(&self.endpoint, &self.cohort, grant, deadline())
            .expect("the runtime binds the view connection")
    }
}

fn next_event(lane: &ViewLane) -> ViewEvent {
    lane.recv(WAIT)
        .expect("the lane delivered an event in time")
}

/// The next image, checked whole against what the page offered under its sequence.
fn next_image(lane: &ViewLane) -> AssembledImage {
    loop {
        match next_event(lane) {
            ViewEvent::Image(image) => {
                assert_eq!(*image.data, image_bytes(image.announcement.sequence));
                return image;
            }
            ViewEvent::State(_) | ViewEvent::Notice(_) => {}
            other => panic!("expected an image, got {other:?}"),
        }
    }
}

fn denied_code(refusal: Result<impl std::fmt::Debug, Refusal>) -> String {
    match refusal {
        Err(Refusal::Denied { code, .. }) => code,
        other => panic!("expected the runtime's refusal, got {other:?}"),
    }
}

#[test]
fn the_lane_streams_latest_images_carries_transfers_and_closes_the_view() {
    std::fs::create_dir_all(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let root = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let mut peer = Peer::start(root.path());
    let ready = peer.expect("ready");
    let window = Window::connect(root.path(), &ready);

    // Attach binds to the exact session that submitted the view; another is refused.
    let mut stranger = window.held.clone();
    stranger.session_id = "00000000-0000-4000-8000-000000000001".to_owned();
    let refused = view_attach(
        &window.connection,
        &stranger,
        &window.operation_id,
        deadline(),
    );
    assert_eq!(denied_code(refused), "operation_unavailable");
    let lane = window.open_lane();

    // With no credit no image arrives; each credit then draws the newest, skipping replaced ones.
    while let Some(event) = lane.recv(Duration::from_millis(500)) {
        assert!(
            !matches!(event, ViewEvent::Image(_)),
            "an image arrived without credit"
        );
    }
    lane.credit(1).unwrap();
    let first = next_image(&lane).announcement.sequence;
    thread::sleep(Duration::from_millis(400));
    lane.credit(1).unwrap();
    let second = next_image(&lane).announcement.sequence;
    assert!(
        second > first + 1,
        "the page's newer images replaced the pending one: {first} then {second}"
    );

    // Input and navigation reach the page; nothing is held back.
    lane.input(ViewInputEvent::Text(TextInput {
        text: TYPED.to_owned(),
    }))
    .unwrap();
    let typed = peer.expect("input");
    assert_eq!(typed["text"], TYPED);
    lane.navigate(ViewNavigateVerb::Reload).unwrap();
    let navigated = peer.expect("navigate");
    assert_eq!(navigated["verb"], "reload");

    // A download the page offers arrives whole, under the window's chunk credit.
    peer.send("download");
    let offer = loop {
        match next_event(&lane) {
            ViewEvent::Download(offer) => break offer,
            ViewEvent::State(_) | ViewEvent::Notice(_) => {}
            other => panic!("expected the download offer, got {other:?}"),
        }
    };
    assert_eq!(offer.size, ready["download_size"].as_u64());
    lane.accept_download(offer.transfer_id, offer.size).unwrap();
    lane.download_credit(offer.transfer_id, DOWNLOAD_WINDOW)
        .unwrap();
    let mut downloaded = Vec::new();
    let complete = loop {
        match next_event(&lane) {
            ViewEvent::DownloadChunk(chunk) => {
                assert_eq!(chunk.offset, downloaded.len() as u64);
                downloaded.extend_from_slice(&chunk.data);
                if !chunk.last {
                    lane.download_credit(offer.transfer_id, 1).unwrap();
                }
            }
            ViewEvent::DownloadComplete(complete) => break complete,
            other => panic!("expected the download's bytes, got {other:?}"),
        }
    };
    let download_sha256 = member(&ready, "download_sha256");
    assert_eq!(Sha256Digest::of(&downloaded).to_string(), download_sha256);
    assert_eq!(complete.sha256, download_sha256);
    let sent = peer.expect("downloaded");
    assert_eq!(sent["delivered"], true);

    // A file the person supplies to the page's chooser reaches the worker with its digest.
    let upload: Vec<u8> = (0..300_000u32)
        .map(|index| (index * 7 % 251) as u8)
        .collect();
    peer.send("choose");
    let chooser = loop {
        match next_event(&lane) {
            ViewEvent::FileChooser(chooser) => break chooser,
            ViewEvent::State(_) | ViewEvent::Notice(_) => {}
            other => panic!("expected the file chooser, got {other:?}"),
        }
    };
    assert!(!chooser.multiple);
    lane.supply_files(
        chooser.chooser_id,
        vec![UploadFile {
            name: "aportacion.bin".to_owned(),
            mime: None,
            size: upload.len() as u64,
            source: Box::new(Cursor::new(upload.clone())),
        }],
    )
    .unwrap();
    loop {
        match next_event(&lane) {
            ViewEvent::UploadEnded { outcome, .. } => {
                assert_eq!(outcome, UploadOutcome::Sent);
                break;
            }
            ViewEvent::State(_) | ViewEvent::Notice(_) => {}
            other => panic!("expected the upload's end, got {other:?}"),
        }
    }
    let uploaded = peer.expect("uploaded");
    assert_eq!(uploaded["name"], "aportacion.bin");
    assert_eq!(uploaded["size"], upload.len() as u64);
    assert_eq!(uploaded["sha256"], Sha256Digest::of(&upload).to_string());

    // Closing the panel asks the view to close, and the runtime then unbinds its worker.
    lane.end_view();
    assert!(lane.is_closed());
    peer.expect("close");
    peer.expect("ended");
}

#[test]
fn signing_out_retires_the_view_and_refuses_a_new_attach() {
    std::fs::create_dir_all(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let root = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let mut peer = Peer::start(root.path());
    let ready = peer.expect("ready");
    let window = Window::connect(root.path(), &ready);
    let lane = window.open_lane();
    lane.credit(2).unwrap();
    next_image(&lane);

    peer.send("sign_out");
    let signed_out = peer.expect("signed_out");
    assert_eq!(signed_out["worker_bound"], false);
    let reason = loop {
        match next_event(&lane) {
            ViewEvent::Closed(reason) => break reason,
            ViewEvent::Image(_) | ViewEvent::State(_) | ViewEvent::Notice(_) => {}
            other => panic!("expected the view's close, got {other:?}"),
        }
    };
    assert_eq!(reason, ViewClosedReason::SessionRetired);
    match next_event(&lane) {
        ViewEvent::Ended(end) => assert_eq!(end, ViewEnd::Disconnected),
        other => panic!("expected the lane's end, got {other:?}"),
    }
    peer.expect("ended");

    let refused = view_attach(
        &window.connection,
        &window.held,
        &window.operation_id,
        deadline(),
    );
    assert_eq!(denied_code(refused), "operation_unavailable");
}
