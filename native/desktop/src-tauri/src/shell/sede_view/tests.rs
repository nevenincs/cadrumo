use super::*;
use cadrumo_application::view_stream::documents::{
    PointerAction, PointerButton, PointerInput, TextInput, ViewImage,
};
use serde_json::{Value, json};
use std::{path::PathBuf, sync::Condvar};
use zeroize::Zeroizing;

const OPERATION: &str = "abababababababababababababababababababababababababababababababab";

/// A view connection that answers from a script and records what it was told.
struct FakeLane {
    events: Mutex<VecDeque<ViewEvent>>,
    wake: Condvar,
    ended: Mutex<Option<ViewEnd>>,
    calls: Mutex<Vec<String>>,
    /// While set, `end_view` leaves the stream open, as a publication in flight does.
    publishing: AtomicBool,
}

impl FakeLane {
    fn new() -> Arc<Self> {
        Arc::new(Self {
            events: Mutex::new(VecDeque::new()),
            wake: Condvar::new(),
            ended: Mutex::new(None),
            calls: Mutex::new(Vec::new()),
            publishing: AtomicBool::new(false),
        })
    }

    fn push(&self, event: ViewEvent) {
        lock(&self.events).push_back(event);
        self.wake.notify_all();
    }

    fn finish(&self, end: ViewEnd) {
        lock(&self.ended).get_or_insert(end);
        self.wake.notify_all();
    }

    fn note(&self, call: String) -> Sent {
        lock(&self.calls).push(call);
        Ok(())
    }

    fn calls(&self) -> Vec<String> {
        lock(&self.calls).clone()
    }
}

impl Lane for FakeLane {
    fn recv(&self, timeout: Duration) -> Option<ViewEvent> {
        let deadline = Instant::now() + timeout;
        let mut events = lock(&self.events);
        loop {
            if let Some(event) = events.pop_front() {
                return Some(event);
            }
            if let Some(end) = *lock(&self.ended) {
                return Some(ViewEvent::Ended(end));
            }
            let remaining = deadline.checked_duration_since(Instant::now())?;
            events = self
                .wake
                .wait_timeout(events, remaining)
                .unwrap_or_else(|poisoned| poisoned.into_inner())
                .0;
        }
    }
    fn credit(&self, images: u8) -> Sent {
        self.note(format!("credit:{images}"))
    }
    fn input(&self, event: ViewInputEvent) -> Sent {
        self.note(match event {
            ViewInputEvent::Pointer(pointer) => {
                format!("pointer:{:?}@{}", pointer.action, pointer.x)
            }
            ViewInputEvent::Text(text) => format!("text:{}", text.text),
            ViewInputEvent::Wheel(_) => "wheel".into(),
            ViewInputEvent::Key(_) => "key".into(),
        })
    }
    fn navigate(&self, verb: ViewNavigateVerb) -> Sent {
        self.note(format!("navigate:{verb:?}"))
    }
    fn resize(&self, css_width: u32, css_height: u32, _scale: f64) -> Sent {
        self.note(format!("resize:{css_width}x{css_height}"))
    }
    fn dialog(&self, dialog_id: u32, accept: bool, prompt_text: Option<String>) -> Sent {
        self.note(format!("dialog:{dialog_id}:{accept}:{prompt_text:?}"))
    }
    fn accept_download(&self, transfer_id: u32, size: Option<u64>) -> Sent {
        self.note(format!("accept_download:{transfer_id}:{size:?}"))
    }
    fn decline_download(&self, transfer_id: u32, outcome: ViewDownloadOutcome) -> Sent {
        self.note(format!("decline_download:{transfer_id}:{outcome:?}"))
    }
    fn download_credit(&self, transfer_id: u32, chunks: u8) -> Sent {
        self.note(format!("download_credit:{transfer_id}:{chunks}"))
    }
    fn cancel_download(&self, transfer_id: u32) -> Sent {
        self.note(format!("cancel_download:{transfer_id}"))
    }
    fn cancel_file_chooser(&self, chooser_id: u32) -> Sent {
        self.note(format!("cancel_chooser:{chooser_id}"))
    }
    fn supply_files(&self, chooser_id: u32, files: Vec<UploadFile>) -> Sent {
        let names: Vec<String> = files
            .iter()
            .map(|file| format!("{}[{}]", file.name, file.size))
            .collect();
        self.note(format!("supply:{chooser_id}:{}", names.join(",")))
    }
    fn end_view(&self) {
        let _ = self.note("end_view".into());
        if !self.publishing.load(Ordering::Acquire) {
            self.finish(ViewEnd::Closed);
        }
    }
    fn close(&self) {
        let _ = self.note("close".into());
        self.finish(ViewEnd::Closed);
    }
}

/// A runtime whose view opens after `waits` refusals.
struct FakeRuntime {
    lane: Arc<FakeLane>,
    waits: AtomicU32,
    fatal: Mutex<Option<&'static str>>,
    attaches: AtomicU32,
    held: AtomicBool,
    running: AtomicBool,
    cancelled: Mutex<Vec<String>>,
    settled: Mutex<Option<Outcome>>,
    settles: AtomicU32,
    /// What happened, in order, across the view and whoever ends the session.
    events: Arc<Mutex<Vec<&'static str>>>,
}

impl FakeRuntime {
    fn new(waits: u32) -> Arc<Self> {
        Arc::new(Self {
            lane: FakeLane::new(),
            waits: AtomicU32::new(waits),
            fatal: Mutex::new(None),
            attaches: AtomicU32::new(0),
            held: AtomicBool::new(true),
            running: AtomicBool::new(true),
            cancelled: Mutex::new(Vec::new()),
            settled: Mutex::new(Some(Outcome {
                condition: Condition::Succeeded,
                end: Some(Finish::Closed),
                publication: Some(Publication::Published),
            })),
            settles: AtomicU32::new(0),
            events: Arc::new(Mutex::new(Vec::new())),
        })
    }

    fn cancelled(&self) -> Vec<String> {
        lock(&self.cancelled).clone()
    }
}

impl ViewRuntime for FakeRuntime {
    fn attach(&self, operation: &str) -> std::result::Result<Arc<dyn Lane>, Refusal> {
        assert_eq!(operation, OPERATION);
        self.attaches.fetch_add(1, Ordering::AcqRel);
        if let Some(code) = *lock(&self.fatal) {
            return Err(Refusal::denied(code));
        }
        if self
            .waits
            .try_update(Ordering::AcqRel, Ordering::Acquire, |waits| {
                waits.checked_sub(1)
            })
            .is_ok()
        {
            return Err(Refusal::denied(NOT_YET));
        }
        Ok(self.lane.clone())
    }
    fn running(&self, _: &str) -> Option<bool> {
        Some(self.running.load(Ordering::Acquire))
    }
    fn cancel(&self, operation: &str) {
        lock(&self.cancelled).push(operation.to_owned());
    }
    fn settled(&self, _: &str) -> Option<Outcome> {
        self.settles.fetch_add(1, Ordering::AcqRel);
        lock(&self.events).push("settled");
        *lock(&self.settled)
    }
    fn held(&self) -> bool {
        self.held.load(Ordering::Acquire)
    }
}

/// The window's end of the channel.
#[derive(Default)]
struct Window {
    bodies: Mutex<Vec<InvokeResponseBody>>,
    gone: AtomicBool,
}

impl Window {
    fn sink(self: &Arc<Self>) -> Sink {
        let window = self.clone();
        Arc::new(move |body| {
            if window.gone.load(Ordering::Acquire) {
                return false;
            }
            lock(&window.bodies).push(body);
            true
        })
    }

    /// Every message in arrival order; a raw one shows as its bytes.
    fn messages(&self) -> Vec<Value> {
        lock(&self.bodies)
            .iter()
            .map(|body| match body {
                InvokeResponseBody::Json(text) => serde_json::from_str(text).unwrap(),
                InvokeResponseBody::Raw(bytes) => json!({"kind": "raw", "bytes": bytes}),
            })
            .collect()
    }

    fn kinds(&self) -> Vec<String> {
        self.messages()
            .iter()
            .map(|message| message["kind"].as_str().unwrap().to_owned())
            .collect()
    }

    fn last(&self, kind: &str) -> Option<Value> {
        self.messages()
            .into_iter()
            .rev()
            .find(|message| message["kind"] == kind)
    }
}

/// Opens links into a list instead of a browser.
#[derive(Default)]
struct Browser(Arc<Mutex<Vec<String>>>);

impl Opener for Browser {
    fn open(&self, url: &Url) -> Result<()> {
        lock(&self.0).push(url.as_str().to_owned());
        Ok(())
    }
}

/// Native dialogs that answer from a script and record that they were asked.
#[derive(Default)]
struct Dialogue {
    save: Mutex<Option<PathBuf>>,
    open: Mutex<Vec<PathBuf>>,
    asked: Mutex<Vec<String>>,
}

impl Dialogs for Dialogue {
    fn save(&self, suggested: &str) -> Option<PathBuf> {
        lock(&self.asked).push(format!("save:{suggested}"));
        lock(&self.save).clone()
    }
    fn open(&self, multiple: bool) -> Vec<PathBuf> {
        lock(&self.asked).push(format!("open:{multiple}"));
        lock(&self.open).clone()
    }
}

struct Rig {
    host: Arc<SedeViewHost>,
    runtime: Arc<FakeRuntime>,
    window: Arc<Window>,
    opened: Arc<Mutex<Vec<String>>>,
    id: u32,
}

impl Rig {
    fn lane(&self) -> &Arc<FakeLane> {
        &self.runtime.lane
    }

    fn calls(&self) -> Vec<String> {
        self.runtime.lane.calls()
    }

    fn wait_for_call(&self, call: &str) {
        wait_until(call, || self.calls().iter().any(|made| made == call));
    }

    fn wait_for_message(&self, kind: &str) {
        wait_until(kind, || self.window.last(kind).is_some());
    }

    fn wait_until_offered(&self, transfer_id: u32) {
        wait_until("the offer", || {
            lock(&self.host.current)
                .as_ref()
                .is_some_and(|view| lock(&view.held).downloads.contains_key(&transfer_id))
        });
    }
}

fn wait_until(what: &str, mut condition: impl FnMut() -> bool) {
    let deadline = Instant::now() + Duration::from_secs(10);
    while !condition() {
        assert!(Instant::now() < deadline, "timed out waiting for {what}");
        thread::sleep(Duration::from_millis(10));
    }
}

fn host() -> (Arc<SedeViewHost>, Arc<Mutex<Vec<String>>>) {
    let browser = Browser::default();
    let opened = browser.0.clone();
    (
        Arc::new(SedeViewHost::with_opener(Box::new(browser))),
        opened,
    )
}

fn started(runtime: &Arc<FakeRuntime>) -> Started {
    Started {
        operation: OPERATION.to_owned(),
        runtime: runtime.clone(),
    }
}

/// A view that has opened its connection.
fn rig() -> Rig {
    let (host, opened) = host();
    let runtime = FakeRuntime::new(0);
    let window = Arc::new(Window::default());
    let id = host.open_with(started(&runtime), window.sink()).unwrap();
    let rig = Rig {
        host,
        runtime,
        window,
        opened,
        id,
    };
    rig.wait_for_message("opened");
    rig
}

fn scratch(name: &str) -> PathBuf {
    let root =
        std::env::temp_dir().join(format!("cadrumo-sede-host-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&root);
    std::fs::create_dir_all(&root).unwrap();
    root
}

/// The names in `root` other than `except`.
fn others(root: &std::path::Path, except: &str) -> Vec<String> {
    let mut names: Vec<String> = std::fs::read_dir(root)
        .unwrap()
        .map(|entry| entry.unwrap().file_name().to_string_lossy().into_owned())
        .filter(|name| name != except)
        .collect();
    names.sort();
    names
}

fn pointer(action: PointerAction, x: u32) -> ViewInputEvent {
    let press = action != PointerAction::Move;
    ViewInputEvent::Pointer(PointerInput {
        action,
        x,
        y: 3,
        button: if press {
            PointerButton::Left
        } else {
            PointerButton::None
        },
        click_count: u8::from(press),
        modifiers: 0,
    })
}

const ADDRESS: &str = "https://sede.example/Sede/inicio.html?ejercicio=2025&modelo=303";

fn page() -> ViewEvent {
    ViewEvent::State(ViewState {
        security: ViewPageSecurity::Secure,
        origin: Some("https://sede.example".into()),
        path: Some("/Sede/inicio.html".into()),
        address: Some(ADDRESS.into()),
        title: "Inicio".into(),
        can_go_back: false,
        can_go_forward: true,
        loading: false,
        phase: ViewPhase::Browsing,
    })
}

fn download(transfer_id: u32, filename: &str, size: Option<u64>) -> ViewEvent {
    ViewEvent::Download(ViewDownload {
        transfer_id,
        filename: filename.into(),
        size,
        mime: None,
    })
}

fn chunk(transfer_id: u32, offset: u64, bytes: &[u8], last: bool) -> ViewEvent {
    ViewEvent::DownloadChunk(TransferChunk {
        transfer_id,
        offset,
        data: Zeroizing::new(bytes.to_vec()),
        last,
    })
}

fn complete(transfer_id: u32, size: u64) -> ViewEvent {
    ViewEvent::DownloadComplete(ViewTransferComplete {
        transfer_id,
        size,
        sha256: "0".repeat(64),
    })
}

fn code(result: Result<impl std::fmt::Debug>) -> &'static str {
    result.unwrap_err().code
}

#[test]
fn the_window_receives_closed_documents_with_stable_names() {
    let image = Message::Image {
        view: 3,
        sequence: 9,
        byte_length: 4,
        pixel_width: 200,
        pixel_height: 100,
        css_width: 100,
        css_height: 50,
        scale: 2.0,
    };
    assert_eq!(
        serde_json::to_value(image).unwrap(),
        json!({"kind":"image","view":3,"sequence":9,"byte_length":4,"pixel_width":200,
            "pixel_height":100,"css_width":100,"css_height":50,"scale":2.0})
    );
    let state = Message::Page {
        view: 3,
        security: ViewPageSecurity::Secure,
        origin: Some("https://sede.example".into()),
        path: Some("/a".into()),
        title: "T".into(),
        can_go_back: true,
        can_go_forward: false,
        loading: true,
        phase: ViewPhase::Closing,
        external: true,
    };
    assert_eq!(
        serde_json::to_value(state).unwrap(),
        json!({"kind":"state","view":3,"security":"secure","origin":"https://sede.example",
            "path":"/a","title":"T","can_go_back":true,"can_go_forward":false,"loading":true,
            "phase":"closing","external":true})
    );
    let notice = Message::Notice {
        view: 3,
        code: ViewNoticeCode::DialogOpened,
        dialog: Some(Dialog {
            dialog_id: 7,
            dialog_kind: ViewDialogKind::Beforeunload,
            message: "m".into(),
            default_prompt: None,
        }),
    };
    assert_eq!(
        serde_json::to_value(notice).unwrap(),
        json!({"kind":"notice","view":3,"code":"dialog_opened",
            "dialog":{"dialog_id":7,"dialog_kind":"beforeunload","message":"m","default_prompt":null}})
    );
    let ended = Message::Ended {
        view: 3,
        reason: Reason::SessionLost,
        code: None,
        outcome: Some(Outcome {
            condition: Condition::Succeeded,
            end: Some(Finish::PageLost),
            publication: Some(Publication::KeptNewer),
        }),
    };
    assert_eq!(
        serde_json::to_value(ended).unwrap(),
        json!({"kind":"ended","view":3,"reason":"session_lost","code":null,
            "outcome":{"condition":"succeeded","end":"page_lost","publication":"kept-newer"}})
    );
    let transfer = Message::DownloadEnded {
        view: 3,
        transfer_id: 1,
        outcome: Transferred::Done,
    };
    assert_eq!(
        serde_json::to_value(transfer).unwrap(),
        json!({"kind":"download_ended","view":3,"transfer_id":1,"outcome":"done"})
    );
}

#[test]
fn the_view_request_names_only_the_profile_and_the_panel_size() {
    let size = Size::admit(800, 600, 1.5).unwrap();
    assert_eq!(
        request("00000000-0000-4000-8000-000000000000", &size),
        json!({"profile_id":"00000000-0000-4000-8000-000000000000",
            "css_width":800, "css_height":600, "scale":1.5})
    );
    for (width, height, scale) in [
        (0, 600, 1.0),
        (800, 0, 1.0),
        (4097, 600, 1.0),
        (800, 600, 0.1),
    ] {
        assert_eq!(code(Size::admit(width, height, scale)), "invalid");
    }
    assert_eq!(code(Size::admit(800, 600, f64::NAN)), "invalid");
}

#[test]
fn a_view_binds_when_its_browser_opens_and_credits_the_first_two_images() {
    let (host, _) = host();
    let runtime = FakeRuntime::new(2);
    let window = Arc::new(Window::default());
    host.open_with(started(&runtime), window.sink()).unwrap();
    wait_until("opened", || window.last("opened").is_some());
    assert_eq!(runtime.attaches.load(Ordering::Acquire), 3);
    assert_eq!(runtime.lane.calls(), ["credit:2"]);
    assert_eq!(window.messages()[0], json!({"kind":"opened","view":1}));
    assert!(runtime.cancelled().is_empty());
}

#[test]
fn images_arrive_as_an_announcement_and_then_the_raw_jpeg() {
    let rig = rig();
    rig.lane().push(ViewEvent::Image(AssembledImage {
        announcement: ViewImage {
            sequence: 4,
            byte_length: 3,
            pixel_width: 100,
            pixel_height: 50,
            css_width: 100,
            css_height: 50,
            scale: 1.0,
        },
        data: Zeroizing::new(vec![0xff, 0xd8, 0xff]),
    }));
    wait_until("raw", || rig.window.last("raw").is_some());
    let messages = rig.window.messages();
    let announced = messages.len() - 2;
    assert_eq!(
        messages[announced],
        json!({"kind":"image","view":rig.id,"sequence":4,"byte_length":3,"pixel_width":100,
            "pixel_height":50,"css_width":100,"css_height":50,"scale":1.0})
    );
    assert_eq!(
        messages[announced + 1],
        json!({"kind":"raw","bytes":[255, 216, 255]})
    );
}

#[test]
fn the_window_credits_one_image_at_a_time_and_the_page_gets_them_in_order() {
    let rig = rig();
    rig.host.credit(rig.id).unwrap();
    rig.host
        .input(rig.id, pointer(PointerAction::Down, 1))
        .unwrap();
    rig.host
        .input(rig.id, ViewInputEvent::Text(TextInput { text: "a".into() }))
        .unwrap();
    rig.host
        .input(rig.id, pointer(PointerAction::Up, 1))
        .unwrap();
    rig.host.navigate(rig.id, ViewNavigateVerb::Back).unwrap();
    rig.host.resize(rig.id, 640, 480, 2.0).unwrap();
    rig.wait_for_call("resize:640x480");
    assert_eq!(
        rig.calls(),
        [
            "credit:2",
            "credit:1",
            "pointer:Down@1",
            "text:a",
            "pointer:Up@1",
            "navigate:Back",
            "resize:640x480"
        ]
    );
}

#[test]
fn input_the_contract_refuses_never_reaches_the_queue() {
    let rig = rig();
    assert_eq!(
        code(rig.host.input(rig.id, pointer(PointerAction::Down, 5000))),
        "invalid"
    );
    assert_eq!(code(rig.host.resize(rig.id, 0, 480, 1.0)), "invalid");
    assert_eq!(code(rig.host.resize(rig.id, 640, 480, 9.0)), "invalid");
    assert_eq!(rig.calls(), ["credit:2"]);
}

#[test]
fn a_command_for_a_view_the_host_did_not_issue_is_refused() {
    let rig = rig();
    let other = rig.id + 1;
    assert_eq!(
        code(rig.host.input(other, pointer(PointerAction::Move, 1))),
        "not_admitted"
    );
    assert_eq!(
        code(rig.host.navigate(other, ViewNavigateVerb::Home)),
        "not_admitted"
    );
    assert_eq!(code(rig.host.resize(other, 10, 10, 1.0)), "not_admitted");
    assert_eq!(code(rig.host.credit(other)), "not_admitted");
    assert_eq!(code(rig.host.dialog(other, 1, true, None)), "not_admitted");
    assert_eq!(code(rig.host.close_view(other)), "not_admitted");
    assert_eq!(code(rig.host.open_external(other)), "not_admitted");
    let dialogs = Dialogue::default();
    assert_eq!(
        code(rig.host.download_answer(other, 1, true, &dialogs)),
        "not_admitted"
    );
    assert_eq!(
        code(rig.host.chooser_answer(other, 1, true, &dialogs)),
        "not_admitted"
    );
    assert!(lock(&dialogs.asked).is_empty());
    assert_eq!(rig.calls(), ["credit:2"]);
}

#[test]
fn an_identifier_the_host_never_issued_is_refused_and_asks_no_dialog() {
    let rig = rig();
    let dialogs = Dialogue::default();
    assert_eq!(code(rig.host.dialog(rig.id, 7, true, None)), "invalid");
    assert_eq!(
        code(rig.host.download_answer(rig.id, 5, true, &dialogs)),
        "invalid"
    );
    assert_eq!(
        code(rig.host.chooser_answer(rig.id, 3, true, &dialogs)),
        "invalid"
    );
    assert!(lock(&dialogs.asked).is_empty());
    assert!(lock(&rig.opened).is_empty());
    assert_eq!(rig.calls(), ["credit:2"]);
}

#[test]
fn a_sign_in_as_another_taxpayer_reaches_the_window_as_its_notice_and_its_end() {
    let rig = rig();
    rig.lane().push(ViewEvent::Notice(ViewNotice {
        code: ViewNoticeCode::IdentityMismatch,
        dialog: None,
    }));
    rig.wait_for_message("notice");
    let notice = rig.window.last("notice").unwrap();
    assert_eq!(notice["code"], "identity_mismatch");
    assert_eq!(notice["dialog"], Value::Null);
    let report: Report =
        serde_json::from_value(json!({"end": "closed", "publication": "identity-mismatch"}))
            .unwrap();
    assert_eq!(report.publication, Some(Publication::IdentityMismatch));
    assert_eq!(
        serde_json::to_value(Publication::IdentityMismatch).unwrap(),
        "identity-mismatch"
    );
}

#[test]
fn a_page_dialog_is_answered_once_and_only_as_the_page_asked() {
    let rig = rig();
    rig.lane().push(ViewEvent::Notice(ViewNotice {
        code: ViewNoticeCode::DialogOpened,
        dialog: Some(ViewDialogPrompt {
            dialog_id: 7,
            dialog_kind: ViewDialogKind::Prompt,
            message: "Name?".into(),
            default_prompt: Some("x".into()),
        }),
    }));
    rig.wait_for_message("notice");
    let notice = rig.window.last("notice").unwrap();
    assert_eq!(notice["dialog"]["dialog_id"], 7);
    assert_eq!(notice["dialog"]["dialog_kind"], "prompt");
    // A dismissal carries no text.
    assert_eq!(
        code(rig.host.dialog(rig.id, 7, false, Some("t".into()))),
        "invalid"
    );
    rig.host
        .dialog(rig.id, 7, true, Some("Ana".into()))
        .unwrap();
    rig.wait_for_call("dialog:7:true:Some(\"Ana\")");
    assert_eq!(code(rig.host.dialog(rig.id, 7, true, None)), "invalid");
}

#[test]
fn the_current_page_opens_from_the_hosts_own_address_and_the_window_sends_none() {
    let rig = rig();
    assert_eq!(
        code(rig.host.open_external(rig.id)),
        "unavailable",
        "no page yet"
    );
    rig.lane().push(page());
    rig.wait_for_message("state");
    let shown = rig.window.last("state").unwrap();
    assert_eq!(shown["origin"], "https://sede.example");
    assert_eq!(shown["path"], "/Sede/inicio.html");
    assert_eq!(shown["can_go_forward"], true);
    let relayed = serde_json::to_string(&shown).unwrap();
    assert!(
        !relayed.contains("ejercicio") && !relayed.contains("address"),
        "the window gets no query: {relayed}"
    );
    rig.host.open_external(rig.id).unwrap();
    assert_eq!(
        *lock(&rig.opened),
        [ADDRESS],
        "the exact page, query included"
    );
}

#[test]
fn a_page_whose_address_was_not_stated_opens_no_earlier_page() {
    let rig = rig();
    rig.lane().push(page());
    rig.wait_for_message("state");
    rig.lane().push(ViewEvent::State(ViewState {
        security: ViewPageSecurity::Secure,
        origin: Some("https://sede.example".into()),
        path: Some("/otra".into()),
        address: None,
        title: "Otra".into(),
        can_go_back: true,
        can_go_forward: false,
        loading: false,
        phase: ViewPhase::Browsing,
    }));
    wait_until("the second page", || {
        rig.window
            .last("state")
            .is_some_and(|shown| shown["path"] == "/otra")
    });
    assert_eq!(rig.window.last("state").unwrap()["external"], false);
    assert_eq!(code(rig.host.open_external(rig.id)), "unavailable");
    assert!(lock(&rig.opened).is_empty());
}

#[test]
fn a_page_off_https_clears_the_address_and_shows_only_its_marker() {
    for security in [ViewPageSecurity::Insecure, ViewPageSecurity::Unknown] {
        let rig = rig();
        rig.lane().push(page());
        rig.wait_for_message("state");
        assert_eq!(rig.window.last("state").unwrap()["external"], true);
        rig.lane().push(ViewEvent::State(ViewState {
            security,
            origin: None,
            path: None,
            address: None,
            title: "Fuera".into(),
            can_go_back: true,
            can_go_forward: false,
            loading: false,
            phase: ViewPhase::Browsing,
        }));
        wait_until("the page off https", || {
            rig.window
                .last("state")
                .is_some_and(|shown| shown["title"] == "Fuera")
        });
        let shown = rig.window.last("state").unwrap();
        assert_eq!(shown["security"], serde_json::to_value(security).unwrap());
        assert_eq!(shown["origin"], Value::Null);
        assert_eq!(shown["path"], Value::Null);
        assert_eq!(shown["external"], false);
        let relayed = serde_json::to_string(&shown).unwrap();
        assert!(!relayed.contains("sede.example"), "{relayed}");
        // The earlier Sede page is no longer the host's to open.
        assert_eq!(code(rig.host.open_external(rig.id)), "unavailable");
        assert!(lock(&rig.opened).is_empty());
    }
}

#[test]
fn closing_the_page_publishes_the_session_and_reports_how() {
    let rig = rig();
    rig.host.close_view(rig.id).unwrap();
    rig.wait_for_message("ended");
    let calls = rig.calls();
    assert!(calls.contains(&"end_view".to_owned()), "{calls:?}");
    assert!(!calls.contains(&"close".to_owned()), "{calls:?}");
    assert!(
        rig.runtime.cancelled().is_empty(),
        "closing is not a cancellation"
    );
    let kinds = rig.window.kinds();
    assert_eq!(&kinds[kinds.len() - 2..], ["closing", "ended"], "{kinds:?}");
    let ended = rig.window.last("ended").unwrap();
    assert_eq!(ended["reason"], "closed");
    assert_eq!(ended["outcome"]["condition"], "succeeded");
    assert_eq!(ended["outcome"]["end"], "closed");
    assert_eq!(ended["outcome"]["publication"], "published");
    assert_eq!(
        code(rig.host.input(rig.id, pointer(PointerAction::Move, 1))),
        "not_admitted"
    );
    wait_until("the place is free", || lock(&rig.host.current).is_none());
}

#[test]
fn closing_the_window_ends_an_open_view_the_same_way_and_admits_no_new_one() {
    let rig = rig();
    rig.host.close();
    rig.wait_for_message("ended");
    let calls = rig.calls();
    assert!(calls.contains(&"end_view".to_owned()), "{calls:?}");
    assert!(!calls.contains(&"close".to_owned()), "{calls:?}");
    assert!(rig.runtime.cancelled().is_empty());
    assert_eq!(rig.window.last("ended").unwrap()["reason"], "closed");
    assert_eq!(code(rig.host.admit_open()), "unavailable");
    let runtime = FakeRuntime::new(0);
    let refused = rig
        .host
        .open_with(started(&runtime), Arc::new(Window::default()).sink());
    assert_eq!(code(refused), "unavailable");
    assert_eq!(
        runtime.cancelled(),
        [OPERATION],
        "a view that cannot be kept is cancelled"
    );
}

#[test]
fn closing_the_window_returns_only_after_the_view_published_and_ended() {
    let rig = rig();
    rig.lane().publishing.store(true, Ordering::Release);
    let lane = rig.lane().clone();
    let publication = thread::spawn(move || {
        wait_until("the close", || lane.calls().iter().any(|c| c == "end_view"));
        thread::sleep(Duration::from_millis(300));
        lane.finish(ViewEnd::Closed);
    });
    rig.host.close();
    // What the window's close does next: sign-in ends the person's session.
    lock(&rig.runtime.events).push("session_stopped");
    publication.join().unwrap();
    assert_eq!(*lock(&rig.runtime.events), ["settled", "session_stopped"]);
    rig.wait_for_message("ended");
    assert_eq!(rig.window.last("ended").unwrap()["reason"], "closed");
    assert!(
        rig.runtime.cancelled().is_empty(),
        "closing is not a cancellation"
    );
}

#[test]
fn closing_the_window_stops_waiting_for_a_view_that_never_ends() {
    let rig = rig();
    rig.lane().publishing.store(true, Ordering::Release);
    let started = Instant::now();
    rig.host.close_within(Duration::from_millis(300));
    assert!(started.elapsed() < Duration::from_secs(5));
    assert!(
        rig.window.last("ended").is_none(),
        "the view is still publishing"
    );
    rig.lane().finish(ViewEnd::Closed);
    rig.wait_for_message("ended");
}

#[test]
fn closing_the_window_cancels_a_view_whose_browser_is_not_open_yet() {
    let (host, _) = host();
    let runtime = FakeRuntime::new(u32::MAX);
    let window = Arc::new(Window::default());
    host.open_with(started(&runtime), window.sink()).unwrap();
    wait_until("a first try", || {
        runtime.attaches.load(Ordering::Acquire) > 0
    });
    host.close();
    assert_eq!(
        runtime.cancelled()[0],
        OPERATION,
        "cancelled at once, not after the next try"
    );
    wait_until("ended", || window.last("ended").is_some());
    assert_eq!(window.last("ended").unwrap()["reason"], "closed");
    assert!(
        runtime.lane.calls().is_empty(),
        "no connection was ever bound"
    );
}

#[test]
fn closing_the_page_before_the_browser_opens_cancels_the_view() {
    let (host, _) = host();
    let runtime = FakeRuntime::new(u32::MAX);
    let window = Arc::new(Window::default());
    let id = host.open_with(started(&runtime), window.sink()).unwrap();
    host.close_view(id).unwrap();
    wait_until("ended", || window.last("ended").is_some());
    assert_eq!(runtime.cancelled(), [OPERATION]);
    assert!(runtime.lane.calls().is_empty());
}

#[test]
fn losing_the_session_cancels_the_view_without_publishing_and_drops_the_connection() {
    let rig = rig();
    rig.runtime.held.store(false, Ordering::Release);
    rig.wait_for_message("ended");
    let calls = rig.calls();
    assert!(calls.contains(&"close".to_owned()), "{calls:?}");
    assert!(!calls.contains(&"end_view".to_owned()), "{calls:?}");
    assert_eq!(rig.runtime.cancelled(), [OPERATION]);
    assert_eq!(
        rig.runtime.settles.load(Ordering::Acquire),
        0,
        "nothing was waited for"
    );
    let ended = rig.window.last("ended").unwrap();
    assert_eq!(ended["reason"], "session_lost");
    assert_eq!(ended["outcome"], Value::Null);
}

#[test]
fn a_session_lost_while_the_browser_opens_cancels_the_view_too() {
    let (host, _) = host();
    let runtime = FakeRuntime::new(u32::MAX);
    runtime.held.store(false, Ordering::Release);
    let window = Arc::new(Window::default());
    host.open_with(started(&runtime), window.sink()).unwrap();
    wait_until("ended", || window.last("ended").is_some());
    assert_eq!(window.last("ended").unwrap()["reason"], "session_lost");
    assert_eq!(runtime.cancelled(), [OPERATION]);
}

#[test]
fn the_runtime_retiring_the_session_is_session_loss_without_publication() {
    let rig = rig();
    rig.lane()
        .push(ViewEvent::Closed(ViewClosedReason::SessionRetired));
    rig.wait_for_message("ended");
    let calls = rig.calls();
    assert!(calls.contains(&"close".to_owned()), "{calls:?}");
    assert!(!calls.contains(&"end_view".to_owned()), "{calls:?}");
    assert_eq!(rig.runtime.cancelled(), [OPERATION]);
    assert_eq!(rig.window.last("ended").unwrap()["reason"], "session_lost");
    assert_eq!(rig.runtime.settles.load(Ordering::Acquire), 0);
}

#[test]
fn a_stream_the_runtime_ends_for_another_reason_still_waits_for_the_receipt() {
    let rig = rig();
    rig.lane()
        .push(ViewEvent::Closed(ViewClosedReason::OperationEnded));
    rig.lane().finish(ViewEnd::Disconnected);
    rig.wait_for_message("ended");
    assert_eq!(
        rig.window.last("ended").unwrap()["reason"],
        "operation_ended"
    );
    assert_eq!(rig.runtime.settles.load(Ordering::Acquire), 1);
    assert!(rig.runtime.cancelled().is_empty());
}

#[test]
fn a_connection_that_drops_without_a_word_is_unavailable() {
    let rig = rig();
    rig.lane().finish(ViewEnd::Disconnected);
    rig.wait_for_message("ended");
    assert_eq!(rig.window.last("ended").unwrap()["reason"], "unavailable");
}

#[test]
fn a_refusal_that_is_not_a_wait_ends_the_view_and_cancels_it() {
    let (host, _) = host();
    let runtime = FakeRuntime::new(0);
    *lock(&runtime.fatal) = Some("frontend_denied");
    let window = Arc::new(Window::default());
    host.open_with(started(&runtime), window.sink()).unwrap();
    wait_until("ended", || window.last("ended").is_some());
    let ended = window.last("ended").unwrap();
    assert_eq!(ended["reason"], "refused");
    assert_eq!(ended["code"], "frontend_denied");
    assert_eq!(runtime.cancelled(), [OPERATION]);
    assert_eq!(runtime.settles.load(Ordering::Acquire), 0);
}

#[test]
fn a_view_whose_operation_already_ended_while_waiting_is_reported() {
    let (host, _) = host();
    let runtime = FakeRuntime::new(u32::MAX);
    runtime.running.store(false, Ordering::Release);
    *lock(&runtime.settled) = Some(Outcome {
        condition: Condition::Failed,
        end: None,
        publication: None,
    });
    let window = Arc::new(Window::default());
    host.open_with(started(&runtime), window.sink()).unwrap();
    wait_until("ended", || window.last("ended").is_some());
    let ended = window.last("ended").unwrap();
    assert_eq!(ended["reason"], "operation_ended");
    assert_eq!(ended["outcome"]["condition"], "failed");
}

#[test]
fn a_page_that_can_no_longer_receive_closes_the_view() {
    let rig = rig();
    rig.window.gone.store(true, Ordering::Release);
    rig.lane().push(page());
    rig.wait_for_call("end_view");
    assert!(
        rig.runtime.cancelled().is_empty(),
        "the person's page closed: publish"
    );
}

#[test]
fn replacing_the_top_document_closes_the_view() {
    let rig = rig();
    rig.host.page_replaced();
    rig.wait_for_call("end_view");
}

#[test]
fn a_second_view_waits_for_the_first_to_end_and_is_cancelled_if_it_cannot() {
    let rig = rig();
    assert_eq!(code(rig.host.admit_open()), "conflict");
    let second = FakeRuntime::new(0);
    let refused = rig
        .host
        .open_with(started(&second), Arc::new(Window::default()).sink());
    assert_eq!(code(refused), "conflict");
    assert_eq!(second.cancelled(), [OPERATION]);
    rig.host.close_view(rig.id).unwrap();
    wait_until("the place is free", || lock(&rig.host.current).is_none());
    rig.host.admit_open().unwrap();
}

#[test]
fn a_download_is_written_where_the_person_chose_and_nowhere_else() {
    let rig = rig();
    let root = scratch("download");
    let target = root.join("saved.pdf");
    rig.lane().push(download(1, "report.pdf", Some(5)));
    rig.wait_for_message("download");
    let offered = rig.window.last("download").unwrap();
    assert_eq!(offered["transfer_id"], 1);
    assert_eq!(offered["filename"], "report.pdf");
    let dialogs = Dialogue::default();
    *lock(&dialogs.save) = Some(target.clone());
    let answered = rig.host.download_answer(rig.id, 1, true, &dialogs).unwrap();
    assert!(answered.saving);
    assert_eq!(*lock(&dialogs.asked), ["save:report.pdf"]);
    assert_eq!(
        &rig.calls()[1..],
        ["accept_download:1:Some(5)", "download_credit:1:32"]
    );
    rig.lane().push(chunk(1, 0, b"abc", false));
    rig.wait_for_call("download_credit:1:1");
    assert!(
        !target.exists(),
        "the file appears only when the transfer is whole"
    );
    rig.lane().push(chunk(1, 3, b"de", true));
    rig.lane().push(complete(1, 5));
    rig.wait_for_message("download_ended");
    assert_eq!(
        rig.window.last("download_ended").unwrap()["outcome"],
        "done"
    );
    assert_eq!(std::fs::read(&target).unwrap(), b"abcde");
    let mut names: Vec<_> = std::fs::read_dir(&root)
        .unwrap()
        .map(|entry| entry.unwrap().file_name())
        .collect();
    names.sort();
    assert_eq!(names, ["saved.pdf"], "no other file was written");
    assert_eq!(
        rig.calls()
            .iter()
            .filter(|call| call.starts_with("download_credit:1:1"))
            .count(),
        1,
        "the last chunk is not credited"
    );
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn a_download_the_person_declines_or_leaves_unchosen_writes_nothing() {
    let rig = rig();
    let root = scratch("declined");
    rig.lane().push(download(1, "a.pdf", None));
    rig.lane().push(download(2, "b.pdf", None));
    rig.wait_until_offered(2);
    let dialogs = Dialogue::default();
    // A dialog closed without a choice.
    let answered = rig.host.download_answer(rig.id, 1, true, &dialogs).unwrap();
    assert!(!answered.saving);
    // No dialog at all when the person declines.
    let answered = rig
        .host
        .download_answer(rig.id, 2, false, &dialogs)
        .unwrap();
    assert!(!answered.saving);
    assert_eq!(*lock(&dialogs.asked), ["save:a.pdf"]);
    assert_eq!(
        &rig.calls()[1..],
        [
            "decline_download:1:Cancelled",
            "decline_download:2:Cancelled"
        ]
    );
    assert_eq!(std::fs::read_dir(&root).unwrap().count(), 0);
    assert_eq!(
        code(rig.host.download_answer(rig.id, 1, true, &dialogs)),
        "invalid",
        "answered once"
    );
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn a_save_path_that_cannot_be_written_declines_the_download() {
    let rig = rig();
    let root = scratch("unwritable");
    rig.lane().push(download(1, "a.pdf", None));
    rig.wait_until_offered(1);
    let dialogs = Dialogue::default();
    *lock(&dialogs.save) = Some(root.join("missing").join("a.pdf"));
    assert_eq!(
        code(rig.host.download_answer(rig.id, 1, true, &dialogs)),
        "file_unavailable"
    );
    assert_eq!(&rig.calls()[1..], ["decline_download:1:Refused"]);
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn a_download_the_page_stops_leaves_the_chosen_file_as_it_was() {
    let rig = rig();
    let root = scratch("stopped");
    let target = root.join("saved.pdf");
    std::fs::write(&target, b"before").unwrap();
    rig.lane().push(download(1, "report.pdf", None));
    rig.wait_until_offered(1);
    let dialogs = Dialogue::default();
    *lock(&dialogs.save) = Some(target.clone());
    rig.host.download_answer(rig.id, 1, true, &dialogs).unwrap();
    rig.lane().push(chunk(1, 0, b"abc", false));
    rig.wait_for_call("download_credit:1:1");
    assert_eq!(others(&root, "saved.pdf").len(), 1, "the partial file");
    rig.lane()
        .push(ViewEvent::DownloadCancelled { transfer_id: 1 });
    rig.wait_for_message("download_ended");
    assert_eq!(
        rig.window.last("download_ended").unwrap()["outcome"],
        "cancelled"
    );
    assert_eq!(std::fs::read(&target).unwrap(), b"before");
    assert!(others(&root, "saved.pdf").is_empty());
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn a_download_that_ends_with_the_view_leaves_no_partial_file() {
    let rig = rig();
    let root = scratch("ended");
    rig.lane().push(download(1, "report.pdf", None));
    rig.wait_until_offered(1);
    let dialogs = Dialogue::default();
    *lock(&dialogs.save) = Some(root.join("saved.pdf"));
    rig.host.download_answer(rig.id, 1, true, &dialogs).unwrap();
    rig.lane().push(chunk(1, 0, b"abc", false));
    rig.wait_for_call("download_credit:1:1");
    rig.host.close_view(rig.id).unwrap();
    rig.wait_for_message("ended");
    assert_eq!(std::fs::read_dir(&root).unwrap().count(), 0);
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn more_offers_than_the_window_can_answer_decline_the_oldest() {
    let rig = rig();
    for id in 1..=u32::try_from(PENDING_LIMIT).unwrap() + 1 {
        rig.lane().push(download(id, "a.pdf", None));
    }
    rig.wait_for_call("decline_download:1:Refused");
    let dialogs = Dialogue::default();
    assert_eq!(
        code(rig.host.download_answer(rig.id, 1, false, &dialogs)),
        "invalid"
    );
    rig.host
        .download_answer(rig.id, 2, false, &dialogs)
        .unwrap();
}

#[test]
fn a_file_chooser_sends_only_the_file_the_person_chose() {
    let rig = rig();
    let root = scratch("chooser");
    let first = root.join("one.pdf");
    let second = root.join("two.pdf");
    std::fs::write(&first, b"12345").unwrap();
    std::fs::write(&second, b"x").unwrap();
    rig.lane().push(ViewEvent::FileChooser(ViewFileChooser {
        chooser_id: 2,
        accept: vec![".pdf".into()],
        multiple: false,
    }));
    rig.wait_for_message("file_chooser");
    assert_eq!(
        rig.window.last("file_chooser").unwrap()["accept"],
        json!([".pdf"])
    );
    let dialogs = Dialogue::default();
    // A dialog that offers more than the page allowed is held to one.
    *lock(&dialogs.open) = vec![first.clone(), second.clone()];
    let answered = rig.host.chooser_answer(rig.id, 2, true, &dialogs).unwrap();
    assert_eq!(answered.supplied, 1);
    assert_eq!(*lock(&dialogs.asked), ["open:false"]);
    assert_eq!(&rig.calls()[1..], ["supply:2:one.pdf[5]"]);
    assert_eq!(
        code(rig.host.chooser_answer(rig.id, 2, true, &dialogs)),
        "invalid",
        "answered once"
    );
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn a_chooser_may_take_several_files_when_the_page_allows_it() {
    let rig = rig();
    let root = scratch("several");
    let (first, second) = (root.join("a.xml"), root.join("b.xml"));
    std::fs::write(&first, b"1").unwrap();
    std::fs::write(&second, b"22").unwrap();
    rig.lane().push(ViewEvent::FileChooser(ViewFileChooser {
        chooser_id: 4,
        accept: vec![],
        multiple: true,
    }));
    rig.wait_for_message("file_chooser");
    let dialogs = Dialogue::default();
    *lock(&dialogs.open) = vec![first, second];
    assert_eq!(
        rig.host
            .chooser_answer(rig.id, 4, true, &dialogs)
            .unwrap()
            .supplied,
        2
    );
    assert_eq!(*lock(&dialogs.asked), ["open:true"]);
    assert_eq!(&rig.calls()[1..], ["supply:4:a.xml[1],b.xml[2]"]);
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn a_chooser_the_person_declines_or_leaves_unchosen_is_cancelled() {
    let rig = rig();
    for id in [1, 2] {
        rig.lane().push(ViewEvent::FileChooser(ViewFileChooser {
            chooser_id: id,
            accept: vec![],
            multiple: false,
        }));
    }
    wait_until("both choosers", || {
        lock(&rig.host.current)
            .as_ref()
            .is_some_and(|view| lock(&view.held).choosers.len() == 2)
    });
    let dialogs = Dialogue::default();
    assert_eq!(
        rig.host
            .chooser_answer(rig.id, 1, true, &dialogs)
            .unwrap()
            .supplied,
        0
    );
    assert_eq!(
        rig.host
            .chooser_answer(rig.id, 2, false, &dialogs)
            .unwrap()
            .supplied,
        0
    );
    assert_eq!(
        *lock(&dialogs.asked),
        ["open:false"],
        "declining asks no dialog"
    );
    assert_eq!(&rig.calls()[1..], ["cancel_chooser:1", "cancel_chooser:2"]);
}

#[test]
fn a_file_that_cannot_be_read_cancels_the_chooser() {
    let rig = rig();
    rig.lane().push(ViewEvent::FileChooser(ViewFileChooser {
        chooser_id: 1,
        accept: vec![],
        multiple: false,
    }));
    rig.wait_for_message("file_chooser");
    let root = scratch("unreadable");
    let dialogs = Dialogue::default();
    *lock(&dialogs.open) = vec![root.join("missing.pdf")];
    assert_eq!(
        code(rig.host.chooser_answer(rig.id, 1, true, &dialogs)),
        "file_unavailable"
    );
    assert_eq!(&rig.calls()[1..], ["cancel_chooser:1"]);
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn an_upload_that_ends_is_reported_to_the_window() {
    let rig = rig();
    for outcome in [
        UploadOutcome::Sent,
        UploadOutcome::Cancelled,
        UploadOutcome::Failed,
    ] {
        rig.lane().push(ViewEvent::UploadEnded {
            chooser_id: 2,
            transfer_id: 1,
            outcome,
        });
    }
    wait_until("three", || {
        rig.window
            .kinds()
            .iter()
            .filter(|kind| *kind == "upload_ended")
            .count()
            == 3
    });
    let outcomes: Vec<_> = rig
        .window
        .messages()
        .iter()
        .filter(|message| message["kind"] == "upload_ended")
        .map(|message| message["outcome"].as_str().unwrap().to_owned())
        .collect();
    assert_eq!(outcomes, ["done", "cancelled", "failed"]);
}

#[test]
fn a_frame_the_shell_could_not_deliver_ends_the_window_sink() {
    use crate::shell::channel::Deliveries;
    use std::str::FromStr;
    use tauri::{
        Manager, WebviewWindowBuilder,
        ipc::JavaScriptChannelId,
        test::{MockRuntime, mock_builder, mock_context, noop_assets},
    };
    let app = mock_builder().build(mock_context(noop_assets())).unwrap();
    app.manage(Deliveries::default());
    let window = WebviewWindowBuilder::new(&app, "main", Default::default())
        .build()
        .unwrap();
    let webview: &Webview<MockRuntime> = window.as_ref();
    let channel = JavaScriptChannelId::from_str("__CHANNEL__:7")
        .unwrap()
        .channel_on::<MockRuntime, InvokeResponseBody>(webview.clone());
    let sink = channel_sink(webview.clone(), channel);
    let body = || InvokeResponseBody::Json("{}".into());
    assert!(sink(body()));
    app.state::<Deliveries>().record("main", 7);
    assert!(
        !sink(body()),
        "the shell reported a frame of this channel undelivered"
    );
}

#[test]
fn input_reaches_the_page_while_a_login_runs_in_the_view() {
    let rig = rig();
    rig.lane().push(ViewEvent::State(ViewState {
        security: ViewPageSecurity::Secure,
        origin: Some("https://sede.example".into()),
        path: Some("/login".into()),
        address: None,
        title: String::new(),
        can_go_back: false,
        can_go_forward: false,
        loading: true,
        phase: ViewPhase::Acquiring,
    }));
    rig.wait_for_message("state");
    assert_eq!(rig.window.last("state").unwrap()["phase"], "acquiring");
    rig.host
        .input(rig.id, pointer(PointerAction::Down, 1))
        .unwrap();
    rig.host
        .input(rig.id, ViewInputEvent::Text(TextInput { text: "a".into() }))
        .unwrap();
    rig.host.navigate(rig.id, ViewNavigateVerb::Home).unwrap();
    rig.wait_for_call("navigate:Home");
    assert_eq!(
        &rig.calls()[1..],
        ["pointer:Down@1", "text:a", "navigate:Home"]
    );
}
