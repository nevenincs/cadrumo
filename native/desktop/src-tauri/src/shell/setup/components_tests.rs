//! The window's engine against a real engine of a throwaway installation: a
//! storage root of its own, the bundled driver's layout, pinned archives and a
//! local TLS publisher the engine's network reaches. Nothing here stands in
//! for the engine; every review, event and report is the engine's own.
use super::super::{
    admission::{
        Admission,
        tests::{ADDED, GB, LOCAL, Replies, TEXT, VISION, cause, declared, refusal, requested},
    },
    wire::{Google, Snapshot},
};
use super::*;
use cadrumo_application::provisioning::{
    browser::DriverManifest,
    connection::{Network, Resolve},
    engine::EngineConfig,
    pins::{ComponentPins, Platform},
    test_servers::{Released, Reply, Request, TestCertificate, TlsServer, response},
    transfer::RetryPolicy,
};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    net::SocketAddr,
    path::{Path, PathBuf},
};

const HOST: &str = "cdn.example.com";
/// The registry the program pulls a model without a host of its own from.
const MODEL_HOST: &str = "registry.ollama.ai";
/// What the pinned local AI program archive is said to weigh.
const PROGRAM_BYTES: u64 = 1000;
const DRIVER: &str = "1.64.0-beta-1791568591000";
const BROWSER_VERSION: &str = "156.0.8078.4";
const GIB: u64 = 1024 * 1024 * 1024;

/// The account before its sign-in has been read.
fn unread() -> Google {
    Google {
        state: None,
        email: None,
        drive_folder_id: None,
        stage: wire::GoogleStage::Idle,
        failure: None,
    }
}

/// A folder of its own under the system's temporary folder, removed when dropped.
struct Scratch(PathBuf);

impl Scratch {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!("cadrumo-setup-{}", operation_id()));
        std::fs::create_dir_all(&path).unwrap();
        Self(path)
    }
}

impl Drop for Scratch {
    fn drop(&mut self) {
        // A folder a test left behind is the system's temporary folder to clear.
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

/// The builds the bundled driver installs on this platform, as its pins name them.
fn builds() -> Vec<(&'static str, &'static str)> {
    let mut builds = vec![
        ("chromium-1248", "chromium"),
        ("chromium_headless_shell-1248", "chromium_headless_shell"),
        ("ffmpeg-1013", "ffmpeg"),
    ];
    if Platform::current() == Some(Platform::WinX64) {
        builds.push(("winldd-1007", "winldd"));
    }
    builds
}

/// The driver package as the bundled one lays it out.
fn driver(folder: &Path) -> DriverManifest {
    std::fs::create_dir_all(folder).unwrap();
    let browsers = serde_json::json!({
        "browsers": [
            {"name": "chromium", "revision": "1248", "installByDefault": true,
             "browserVersion": BROWSER_VERSION},
            {"name": "chromium-headless-shell", "revision": "1248", "installByDefault": true,
             "browserVersion": BROWSER_VERSION},
            {"name": "ffmpeg", "revision": "1013", "installByDefault": true},
            {"name": "winldd", "revision": "1007", "installByDefault": false}
        ]
    });
    std::fs::write(folder.join("browsers.json"), browsers.to_string()).unwrap();
    std::fs::write(
        folder.join("package.json"),
        serde_json::json!({"name": "playwright-core", "version": DRIVER}).to_string(),
    )
    .unwrap();
    DriverManifest::read(folder).unwrap()
}

/// The pin table for one archive of each build, and the bytes each path serves.
fn archives() -> (String, BTreeMap<String, Vec<u8>>) {
    let platform = Platform::current().expect("tests run on a supported platform");
    let mut table = format!("playwright_driver = \"{DRIVER}\"\nhosts = [\"{HOST}\"]\n");
    let mut served = BTreeMap::new();
    for (directory, prefix) in builds() {
        // Bytes that match their pin but are no archive: setup fetches them,
        // then fails to install them.
        let bytes = format!("{directory} pinned bytes ")
            .repeat(4096)
            .into_bytes();
        let path = format!("builds/{directory}/{prefix}.zip");
        let digest: String = Sha256::digest(&bytes)
            .iter()
            .map(|byte| format!("{byte:02x}"))
            .collect();
        table.push_str(&format!(
            "\n[[archives]]\nplatform = \"{}\"\ndirectory_name = \"{directory}\"\npath = \"{path}\"\nurls = [\"https://{HOST}/{path}\"]\ndownload_bytes = {}\nsha256 = \"{digest}\"\n",
            platform.as_str(),
            bytes.len(),
        ));
        served.insert(format!("/{path}"), bytes);
    }
    served.insert(PROGRAM_PATH.to_owned(), program_archive());
    (table, served)
}

/// Where the publisher serves the local AI program archive.
const PROGRAM_PATH: &str = "/program/ollama.zip";

/// Bytes that match the program's pin but are no archive: setup downloads them, then
/// fails to install them.
fn program_archive() -> Vec<u8> {
    vec![b'p'; usize::try_from(PROGRAM_BYTES).unwrap()]
}

/// How the publisher answers the first archive it is asked for.
#[derive(Clone)]
enum Serving {
    Whole,
    /// Its first bytes, then the rest once the gate is released.
    Gated(Arc<Released>),
}

struct Fixture {
    scratch: Scratch,
    server: TlsServer,
    certificate: TestCertificate,
    free_bytes: Option<u64>,
    reachable: bool,
}

impl Fixture {
    fn new(serving: Serving) -> Self {
        let scratch = Scratch::new();
        let (table, served) = archives();
        let pins = scratch.0.join("pins");
        std::fs::create_dir_all(&pins).unwrap();
        std::fs::write(pins.join("browser_archives.toml"), table).unwrap();
        driver(&scratch.0.join("driver"));
        let certificate = TestCertificate::new(&[HOST, MODEL_HOST]);
        let server = TlsServer::start(&certificate, move |request: &Request| {
            let Some(bytes) = served.get(request.target()) else {
                return Reply::Bytes(response(
                    "404 Not Found",
                    &[("Content-Length", "0".into())],
                    b"",
                ));
            };
            let head = response(
                "200 OK",
                &[("Content-Length", bytes.len().to_string())],
                b"",
            );
            match &serving {
                Serving::Gated(gate) => {
                    let split = bytes.len() / 2;
                    let mut first = head;
                    first.extend_from_slice(&bytes[..split]);
                    Reply::Gated {
                        first,
                        rest: bytes[split..].to_vec(),
                        gate: gate.clone(),
                    }
                }
                Serving::Whole => {
                    let mut whole = head;
                    whole.extend_from_slice(bytes);
                    Reply::Bytes(whole)
                }
            }
        });
        Self {
            scratch,
            server,
            certificate,
            free_bytes: Some(512 * GIB),
            reachable: true,
        }
    }

    /// The same installation with the local AI program pinned, as a build that ships it.
    fn with_program(self) -> Self {
        let platform = Platform::current().expect("tests run on a supported platform");
        let table = format!(
            "program = \"ollama\"
version = \"9.9.9\"
hosts = [\"{HOST}\"]

[[archives]]
platform = \"{}\"
url = \"https://{HOST}{PROGRAM_PATH}\"
format = \"zip\"
executable = \"ollama\"
download_bytes = {PROGRAM_BYTES}
sha256 = \"{}\"
",
            platform.as_str(),
            hex(&Sha256::digest(program_archive())),
        );
        std::fs::write(
            self.scratch.0.join("pins").join("local_ai_program.toml"),
            table,
        )
        .unwrap();
        self
    }

    fn root(&self) -> PathBuf {
        self.scratch.0.join("storage")
    }

    /// The engines of this fixture's installation, as the window's own are built.
    fn engines(&self) -> Arc<Engines> {
        let root = self.root();
        let pins = self.scratch.0.join("pins");
        let driver = self.scratch.0.join("driver");
        let roots = self.certificate.roots();
        let address: Option<SocketAddr> = self.reachable.then(|| self.server.address());
        let free_bytes = self.free_bytes;
        Arc::new(move || {
            let resolve: Arc<Resolve> = Arc::new(move |_: &str, _: u16| match address {
                Some(address) => Ok(vec![address]),
                None => Err(std::io::Error::new(
                    std::io::ErrorKind::NotFound,
                    "no such name",
                )),
            });
            let config = EngineConfig {
                storage_root: root.clone(),
                locations: Locations::under(&root),
                pins: ComponentPins::load(&pins)?,
                driver: Some(DriverManifest::read(&driver)?),
                platform: Platform::current(),
                network: Network::with_parts(roots.clone(), resolve, None),
                ambient: Box::new(|_| None),
                local_ai_address: "127.0.0.1:9".parse().expect("an address"),
                browser_environment: BTreeMap::new(),
                scratch: root.join("tmp"),
                free_space: Box::new(move |_| free_bytes),
                hardware: Some(Hardware {
                    total_memory_bytes: Some(64 * GIB),
                    nvidia_vram_bytes: None,
                }),
                policy: RetryPolicy::default(),
            };
            Ok(Installation {
                engine: Engine::new(config)?,
            })
        })
    }

    /// The archive paths the publisher was asked for.
    fn downloads(&self) -> usize {
        self.server
            .targets()
            .iter()
            .filter(|target| target.starts_with("/builds/"))
            .count()
    }
}

/// An admission over a service that answers nothing, as general setup consults none.
fn unconsulted() -> Arc<Admission> {
    Arc::new(Admission::new(Arc::new(Replies::default())))
}

/// The window's component engine over `fixture`, with no download asked for.
fn window(fixture: &Fixture) -> Components {
    Components::new(fixture.engines(), unconsulted(), Arc::default())
}

/// The window's engine over `fixture`, admitting downloads from `replies`, which the
/// caller keeps to ask what the engine read.
fn serving(fixture: &Fixture, replies: Replies) -> (Components, Arc<Replies>) {
    let (components, replies, _) = watching(fixture, replies);
    (components, replies)
}

/// As [`serving`], with the diagnostics the engine records its failures in.
fn watching(fixture: &Fixture, replies: Replies) -> (Components, Arc<Replies>, Arc<Diagnostics>) {
    let replies = Arc::new(replies);
    let admission = Arc::new(Admission::new(replies.clone()));
    let diagnostics = Arc::new(Diagnostics::default());
    let components = Components::new(fixture.engines(), admission, diagnostics.clone());
    (components, replies, diagnostics)
}

/// The failures diagnostics hold, oldest first.
fn recorded(diagnostics: &Diagnostics) -> Vec<ApplicationError> {
    diagnostics
        .snapshot(u64::MAX)
        .events
        .into_iter()
        .filter_map(|event| event.failure)
        .collect()
}

/// A setting the engine cannot use: the installation's engine cannot be built, and the
/// error carries the category the engine classified it under.
fn blocked() -> Error {
    Error::Download(
        cadrumo_application::provisioning::failure::TransferFailure::final_(
            FailureCategory::BlockedByNetwork,
        ),
    )
}

/// The engine's part of the snapshot once `done` holds, composed as the
/// window receives it.
async fn until(components: &Components, done: impl Fn(&View) -> bool) -> Snapshot {
    let mut changes = components.changes();
    loop {
        let view = components.view();
        if done(&view) {
            return compose(view, unread()).expect("a snapshot inside its closed sets");
        }
        changes.changed().await.expect("the engine is alive");
    }
}

fn stage(view: &View) -> Option<RunStage> {
    view.runs.first().map(|run| run.stage)
}

fn compose(view: View, google: Google) -> Option<Snapshot> {
    super::super::compose(view, google)
}

fn review(snapshot: &Snapshot) -> (String, wire::Review) {
    let run = snapshot.runs.first().expect("a setup");
    (
        run.operation_id.clone(),
        run.review.clone().expect("a plan under review"),
    )
}

async fn reviewing(components: &Components) -> (String, wire::Review) {
    components
        .start(ItemId::Browser, false, None)
        .await
        .unwrap();
    review(&until(components, |view| stage(view) == Some(RunStage::Review)).await)
}

#[tokio::test]
async fn the_first_read_carries_every_items_codes_and_no_words() {
    let fixture = Fixture::new(Serving::Whole);
    let components = window(&fixture);
    components.observe();
    let snapshot = until(&components, |view| {
        view.check
            .as_ref()
            .is_some_and(|check| check.stage == CheckStage::Done)
    })
    .await;
    assert_eq!(snapshot.rows_mode, Some(wire::CheckMode::Quick));
    assert_eq!(
        (snapshot.complete, snapshot.hardware_limited),
        (Some(false), Some(false))
    );
    let browser = &snapshot.rows[0];
    assert_eq!(
        (browser.item.as_str(), browser.state, browser.recovery),
        ("browser", wire::State::Absent, Some(wire::Recovery::SetUp))
    );
    assert_eq!(
        browser.recovery_action_id.as_deref(),
        Some("operator.provision.browser")
    );
    assert!(browser.size_bytes.is_some_and(|size| size > 0));
    // This build pins no local AI, so nothing can set it up.
    let local_ai = &snapshot.rows[1];
    assert_eq!(
        (local_ai.state, local_ai.blocked_reason, local_ai.recovery),
        (
            wire::State::Blocked,
            Some(wire::BlockedReason::NotInThisBuild),
            None
        )
    );
    assert!(
        snapshot
            .details
            .contains("item: browser; state: absent; check: quick")
    );
    let shown = serde_json::to_value(&snapshot).unwrap();
    for word in ["name", "sentence", "action_label"] {
        assert!(shown["rows"][0].get(word).is_none(), "{word}");
    }
    // Rows already read are not read again on the next observation.
    let check = snapshot.check.unwrap().operation_id;
    components.observe();
    assert_eq!(
        components.view().check.unwrap().operation_id,
        check,
        "a second observation reads nothing again"
    );
}

#[tokio::test]
async fn the_plan_waits_for_the_window_and_a_rejection_downloads_nothing() {
    let fixture = Fixture::new(Serving::Whole);
    let components = window(&fixture);
    let (operation, plan) = reviewing(&components).await;
    assert!(wire::is_hex64(&operation) && wire::is_hex64(&plan.plan_digest));
    let entry = &plan.entries[0];
    assert_eq!(
        (entry.item.as_str(), entry.source_hosts.as_slice()),
        ("browser", [HOST.to_owned()].as_slice())
    );
    let destination = PathBuf::from(entry.destination.as_deref().unwrap());
    assert_eq!(
        destination,
        fixture.root().join("components").join("playwright")
    );
    assert!(plan.space_sufficient && plan.known_download_bytes > 0);
    assert_eq!(fixture.downloads(), 0, "nothing moves before the answer");
    components
        .answer(&operation, &plan.plan_digest, wire::Decision::Reject)
        .await
        .unwrap();
    let settled = until(&components, |view| stage(view) == Some(RunStage::Settled)).await;
    let run = settled.runs.into_iter().next().unwrap();
    assert_eq!((run.outcome, run.failure), (Some(Outcome::Rejected), None));
    assert_eq!(fixture.downloads(), 0);
    // A settled setup has no plan pending.
    assert_eq!(
        components
            .answer(&operation, &plan.plan_digest, wire::Decision::Apply)
            .await,
        Err(Refusal::NotPending)
    );
}

#[tokio::test]
async fn an_approval_binds_the_digest_shown_and_the_setup_runs_until_it_fails() {
    let fixture = Fixture::new(Serving::Whole);
    let components = window(&fixture);
    let (operation, plan) = reviewing(&components).await;
    assert_eq!(
        components
            .answer(&operation, &"0".repeat(64), wire::Decision::Apply)
            .await,
        Err(Refusal::PlanChanged)
    );
    assert_eq!(
        components
            .answer(&"1".repeat(64), &plan.plan_digest, wire::Decision::Apply)
            .await,
        Err(Refusal::NotPending)
    );
    assert_eq!(stage(&components.view()), Some(RunStage::Review));
    components
        .answer(&operation, &plan.plan_digest, wire::Decision::Apply)
        .await
        .unwrap();
    let settled = until(&components, |view| stage(view) == Some(RunStage::Settled)).await;
    let run = settled.runs.into_iter().next().unwrap();
    // The bytes matched their pin but were no archive, so the install did not finish.
    assert_eq!(run.outcome, Some(Outcome::Failed));
    let failure = run.failure.expect("the category the setup failed with");
    let browser = &run.items[0];
    assert_eq!(browser.item, "browser");
    let result = browser.result.as_ref().unwrap();
    assert_eq!((result.changed, result.failure), (false, Some(failure)));
    assert!(fixture.downloads() >= 1);
    assert!(settled.details.contains(&format!("operation: {operation}")));
    assert!(
        settled
            .details
            .contains("dependencies.setup.browser.download")
    );
    assert!(settled.details.contains(&format!("hosts: {HOST}")));
    // The rows were read again after the setup.
    assert_eq!(settled.rows[0].state, wire::State::Failed);
}

#[tokio::test]
async fn resume_applies_a_plan_this_window_approved_without_a_second_review() {
    let fixture = Fixture::new(Serving::Whole);
    let components = window(&fixture);
    let (operation, plan) = reviewing(&components).await;
    components
        .answer(&operation, &plan.plan_digest, wire::Decision::Apply)
        .await
        .unwrap();
    until(&components, |view| stage(view) == Some(RunStage::Settled)).await;
    // Without Resume the same plan is shown again.
    let (again, shown) = reviewing(&components).await;
    assert_eq!(shown.plan_digest, plan.plan_digest);
    components
        .answer(&again, &shown.plan_digest, wire::Decision::Reject)
        .await
        .unwrap();
    until(&components, |view| stage(view) == Some(RunStage::Settled)).await;
    // Resume of the approved plan runs at once: the start comes back running,
    // or already settled, never waiting on a review.
    components.start(ItemId::Browser, true, None).await.unwrap();
    assert_ne!(stage(&components.view()), Some(RunStage::Review));
    let resumed = until(&components, |view| stage(view) == Some(RunStage::Settled)).await;
    let run = resumed.runs.into_iter().next().unwrap();
    assert_ne!(run.operation_id, operation);
    assert_eq!(run.outcome, Some(Outcome::Failed));
    assert!(
        run.items[0]
            .result
            .as_ref()
            .is_some_and(|result| result.failure.is_some())
    );
    // A window that approved nothing yet still asks.
    let other = window(&fixture);
    other.start(ItemId::Browser, true, None).await.unwrap();
    until(&other, |view| stage(view) == Some(RunStage::Review)).await;
    other.close().await;
}

#[tokio::test]
async fn a_cancel_stops_a_running_setup_at_its_next_chunk() {
    let gate = Arc::new(Released::default());
    let fixture = Fixture::new(Serving::Gated(gate.clone()));
    let components = window(&fixture);
    let (operation, plan) = reviewing(&components).await;
    components
        .answer(&operation, &plan.plan_digest, wire::Decision::Apply)
        .await
        .unwrap();
    let running = until(&components, |view| {
        view.runs
            .first()
            .is_some_and(|run| run.items.iter().any(|item| item.completed.is_some()))
    })
    .await;
    let run = running.runs.into_iter().next().unwrap();
    assert_eq!(run.stage, RunStage::Running);
    assert!(run.cancellable);
    let progress = &run.items[0];
    assert_eq!(progress.step, Some(wire::Step::Download));
    assert!(progress.completed.unwrap() <= progress.total.unwrap());
    components.cancel(&operation).await.unwrap();
    assert_eq!(
        refusal(components.cancel(&operation).await),
        Err(Refusal::NotCancellable)
    );
    let asked = components.view().runs.into_iter().next().unwrap();
    assert!(asked.cancel_requested && !asked.cancellable);
    gate.release();
    let settled = until(&components, |view| stage(view) == Some(RunStage::Settled)).await;
    let run = settled.runs.into_iter().next().unwrap();
    assert_eq!((run.outcome, run.failure), (Some(Outcome::Cancelled), None));
    assert_eq!(
        run.items[0].result.as_ref().unwrap().failure,
        Some(wire::Failure::Cancelled)
    );
    assert_eq!(
        refusal(components.cancel(&operation).await),
        Err(Refusal::NotPending)
    );
}

/// Whether the window shows bytes moving for an item of its setup.
fn moving(view: &View) -> bool {
    view.runs
        .first()
        .is_some_and(|run| run.items.iter().any(|item| item.completed.is_some()))
}

/// A window whose approved setup holds at the gate halfway through its first archive.
async fn running(fixture: &Fixture) -> Components {
    let owner = window(fixture);
    let (operation, plan) = reviewing(&owner).await;
    owner
        .answer(&operation, &plan.plan_digest, wire::Decision::Apply)
        .await
        .unwrap();
    until(&owner, moving).await;
    owner
}

/// A second window of the same installation, following the setup the first runs.
async fn following(fixture: &Fixture) -> (Components, wire::Run) {
    let follower = window(fixture);
    follower.start(ItemId::Browser, false, None).await.unwrap();
    let run = until(&follower, moving)
        .await
        .runs
        .into_iter()
        .next()
        .unwrap();
    (follower, run)
}

#[tokio::test]
async fn a_second_window_follows_the_running_setup_to_its_result_without_a_review() {
    let gate = Arc::new(Released::default());
    let fixture = Fixture::new(Serving::Gated(gate.clone()));
    let owner = running(&fixture).await;

    // A window that closes while it follows leaves the setup running.
    let (leaving, _) = following(&fixture).await;
    leaving.close().await;
    assert!(leaving.view().runs.is_empty());
    assert_eq!(stage(&owner.view()), Some(RunStage::Running));

    let (follower, run) = following(&fixture).await;
    assert_eq!(run.stage, RunStage::Running);
    assert!(run.review.is_none() && run.cancellable);
    let browser = &run.items[0];
    assert_eq!(
        (browser.item.as_str(), browser.step),
        ("browser", Some(wire::Step::Download))
    );
    assert!(browser.completed.unwrap() <= browser.total.unwrap());
    gate.release();
    let owned = until(&owner, |view| stage(view) == Some(RunStage::Settled))
        .await
        .runs
        .into_iter()
        .next()
        .unwrap();
    let followed = until(&follower, |view| stage(view) == Some(RunStage::Settled)).await;
    let run = followed.runs.into_iter().next().unwrap();
    // The bytes matched their pin but were no archive, so the owner's install failed.
    assert_eq!(owned.outcome, Some(Outcome::Failed));
    assert_eq!((run.outcome, run.failure), (owned.outcome, owned.failure));
    assert_eq!(
        run.items[0].result.as_ref().unwrap().failure,
        owned.failure,
        "the item the run stopped at carries its failure"
    );
    assert_eq!(fixture.downloads(), 1, "only the owner downloaded");
    assert_eq!(followed.rows[0].state, wire::State::Failed);
}

#[tokio::test]
async fn a_following_window_cancels_the_setup_it_follows_as_the_persons_act() {
    let gate = Arc::new(Released::default());
    let fixture = Fixture::new(Serving::Gated(gate.clone()));
    let owner = running(&fixture).await;
    let (follower, run) = following(&fixture).await;
    follower.cancel(&run.operation_id).await.unwrap();
    assert_eq!(
        refusal(follower.cancel(&run.operation_id).await),
        Err(Refusal::NotCancellable)
    );
    let asked = follower.view().runs.into_iter().next().unwrap();
    assert!(asked.cancel_requested && !asked.cancellable);
    assert_eq!(
        asked.stage,
        RunStage::Running,
        "it follows until the setup ends"
    );
    gate.release();
    let owned = until(&owner, |view| stage(view) == Some(RunStage::Settled))
        .await
        .runs
        .into_iter()
        .next()
        .unwrap();
    assert_eq!(owned.outcome, Some(Outcome::Cancelled));
    let followed = until(&follower, |view| stage(view) == Some(RunStage::Settled))
        .await
        .runs
        .into_iter()
        .next()
        .unwrap();
    assert_eq!(
        (followed.outcome, followed.failure),
        (Some(Outcome::Cancelled), None)
    );
    assert_eq!(
        followed.items[0].result.as_ref().unwrap().failure,
        Some(wire::Failure::Cancelled)
    );
}

#[tokio::test]
async fn a_cancel_declines_the_plan_a_setup_waits_on() {
    let fixture = Fixture::new(Serving::Whole);
    let components = window(&fixture);
    let (operation, _) = reviewing(&components).await;
    components.cancel(&operation).await.unwrap();
    let settled = until(&components, |view| stage(view) == Some(RunStage::Settled)).await;
    assert_eq!(
        settled.runs.into_iter().next().unwrap().outcome,
        Some(Outcome::Cancelled)
    );
    assert_eq!(fixture.downloads(), 0);
}

#[tokio::test]
async fn a_second_start_joins_the_setup_that_waits() {
    let fixture = Fixture::new(Serving::Whole);
    let components = window(&fixture);
    let (operation, _) = reviewing(&components).await;
    components
        .start(ItemId::Browser, false, None)
        .await
        .unwrap();
    assert_eq!(
        components
            .view()
            .runs
            .into_iter()
            .next()
            .unwrap()
            .operation_id,
        operation
    );
    components.close().await;
    // Closing the window declines the plan and waits for its worker.
    let run = components.view().runs.into_iter().next().unwrap();
    assert_eq!(run.outcome, Some(Outcome::Cancelled));
    let closed = components.start(ItemId::Browser, false, None).await;
    assert_eq!(
        closed.as_ref().err().and_then(Stop::refusal),
        Some(Refusal::Unavailable)
    );
    assert_eq!(
        cause(closed).reason.as_deref(),
        Some("setup_window_closed"),
        "the closed window is named, not left to read as a service that is silent"
    );
}

#[tokio::test]
async fn too_little_space_and_no_network_refuse_before_anything_is_asked() {
    let mut fixture = Fixture::new(Serving::Whole);
    fixture.free_bytes = Some(1);
    let components = window(&fixture);
    components
        .start(ItemId::Browser, false, None)
        .await
        .unwrap();
    let full = until(&components, |view| stage(view) == Some(RunStage::Settled)).await;
    assert_eq!(
        full.runs.into_iter().next().unwrap().outcome,
        Some(Outcome::NotEnoughSpace)
    );

    fixture.free_bytes = Some(512 * GIB);
    fixture.reachable = false;
    let components = window(&fixture);
    components
        .start(ItemId::Browser, false, None)
        .await
        .unwrap();
    let offline = until(&components, |view| stage(view) == Some(RunStage::Settled)).await;
    let run = offline.runs.into_iter().next().unwrap();
    assert_eq!(
        (run.outcome, run.failure),
        (Some(Outcome::Failed), Some(wire::Failure::Offline))
    );
    assert_eq!(
        run.items[0].result.as_ref().unwrap().failure,
        Some(wire::Failure::Offline)
    );
    assert_eq!(fixture.downloads(), 0);
}

#[tokio::test]
async fn an_item_this_build_cannot_set_up_settles_with_its_refusal() {
    let fixture = Fixture::new(Serving::Whole);
    let components = window(&fixture);
    components
        .start(ItemId::LocalAi, false, None)
        .await
        .unwrap();
    let settled = until(&components, |view| stage(view) == Some(RunStage::Settled)).await;
    let run = settled.runs.into_iter().next().unwrap();
    assert_eq!(
        (run.outcome, run.failure),
        (Some(Outcome::Failed), Some(wire::Failure::NotInThisBuild))
    );
}

#[tokio::test]
async fn a_setting_the_engine_cannot_use_gives_the_check_its_category() {
    // What a refused setting looks like to the window: the installation's engine cannot
    // be built, and the error carries the category the engine classified it under.
    let engines: Arc<Engines> = Arc::new(|| Err(blocked()));
    let diagnostics = Arc::new(Diagnostics::default());
    let components = Components::new(engines, unconsulted(), diagnostics.clone());

    components.check(wire::CheckMode::Quick);

    let checked = until(&components, |view| {
        view.check
            .as_ref()
            .is_some_and(|check| check.stage != CheckStage::Running)
    })
    .await;
    let check = checked.check.unwrap();
    assert_eq!(
        (check.stage, check.failure),
        (CheckStage::Failed, Some(wire::Failure::BlockedByNetwork)),
        "the window words the category, as the role's other clients do"
    );
    assert!(checked.rows.is_empty());
    let [error] = &recorded(&diagnostics)[..] else {
        panic!("one failure is recorded for the check");
    };
    assert_eq!(error.reason.as_deref(), Some("setup_engine_unavailable"));
    assert_eq!(error.code, ErrorCode::SessionUnavailable);
}

#[tokio::test]
async fn a_setting_the_engine_cannot_use_fails_the_setup_with_its_category_and_records_why() {
    let engines: Arc<Engines> = Arc::new(|| Err(blocked()));
    let diagnostics = Arc::new(Diagnostics::default());
    let components = Components::new(engines, unconsulted(), diagnostics.clone());

    components
        .start(ItemId::Browser, false, None)
        .await
        .unwrap();

    let settled = until(&components, |view| stage(view) == Some(RunStage::Settled)).await;
    let run = settled.runs.into_iter().next().unwrap();
    assert_eq!(
        (run.outcome, run.failure),
        (Some(Outcome::Failed), Some(wire::Failure::BlockedByNetwork))
    );
    let [error] = &recorded(&diagnostics)[..] else {
        panic!("one failure is recorded for the setup");
    };
    assert_eq!(error.reason.as_deref(), Some("setup_engine_unavailable"));
}

#[tokio::test]
async fn no_check_verify_or_general_setup_consults_the_agent_service() {
    let fixture = Fixture::new(Serving::Whole);
    let (components, replies, diagnostics) = watching(&fixture, Replies::default());
    let finished = |after: Option<String>| {
        move |view: &View| {
            view.check.as_ref().is_some_and(|check| {
                check.stage != CheckStage::Running && Some(&check.operation_id) != after.as_ref()
            })
        }
    };
    components.check(wire::CheckMode::Quick);
    let first = until(&components, finished(None)).await.check.unwrap();
    assert_eq!(first.stage, CheckStage::Done);
    components.verify(vec![ItemId::Browser]);
    until(&components, finished(Some(first.operation_id.clone()))).await;
    let (operation, plan) = reviewing(&components).await;
    decline(&components, &operation, &plan).await;
    assert!(replies.asked().is_empty(), "{:?}", replies.asked());
    assert!(recorded(&diagnostics).is_empty());
}

#[tokio::test]
async fn a_start_returns_the_cause_of_its_refusal_and_leaves_recording_it_to_the_host() {
    let fixture = Fixture::new(Serving::Whole);
    let cases = [
        (
            "a service that does not answer",
            Replies::default(),
            "setup_provider_status_unanswered",
            Some(Refusal::Unavailable),
        ),
        (
            "a list outside the contract",
            Replies::serving(&[], &[], &[])
                .answering("local_models", serde_json::json!({"models": "none"})),
            "setup_local_models_contract",
            None,
        ),
    ];
    for (name, replies, reason, refusal) in cases {
        let (components, _, diagnostics) = watching(&fixture, replies);
        let stopped = components
            .start(ItemId::LocalAi, false, Some(requested(LOCAL, ADDED)))
            .await;
        assert_eq!(
            stopped.as_ref().err().and_then(Stop::refusal),
            refusal,
            "{name}"
        );
        assert_eq!(cause(stopped).reason.as_deref(), Some(reason), "{name}");
        assert!(
            recorded(&diagnostics).is_empty(),
            "{name}: the host that answers the window records it once"
        );
        assert!(components.view().runs.is_empty(), "{name}");
    }
}

#[tokio::test]
async fn a_cancel_that_cannot_reach_the_followed_setup_says_why_and_may_be_asked_again() {
    let gate = Arc::new(Released::default());
    let fixture = Fixture::new(Serving::Gated(gate.clone()));
    let owner = running(&fixture).await;
    let real = fixture.engines();
    let lost = Arc::new(std::sync::atomic::AtomicBool::new(false));
    let switch = lost.clone();
    let engines: Arc<Engines> = Arc::new(move || {
        if switch.load(std::sync::atomic::Ordering::Acquire) {
            Err(blocked())
        } else {
            real()
        }
    });
    let follower = Components::new(engines, unconsulted(), Arc::default());
    follower.start(ItemId::Browser, false, None).await.unwrap();
    let run = until(&follower, moving)
        .await
        .runs
        .into_iter()
        .next()
        .unwrap();

    lost.store(true, std::sync::atomic::Ordering::Release);
    let stopped = follower.cancel(&run.operation_id).await;
    assert_eq!(
        stopped.as_ref().err().and_then(Stop::refusal),
        Some(Refusal::Unavailable)
    );
    assert_eq!(
        cause(stopped).reason.as_deref(),
        Some("setup_engine_unavailable")
    );
    let shown = follower.view().runs.into_iter().next().unwrap();
    assert!(
        shown.cancellable && !shown.cancel_requested,
        "nothing was asked of the followed setup"
    );
    gate.release();
    until(&owner, |view| stage(view) == Some(RunStage::Settled)).await;
    until(&follower, |view| stage(view) == Some(RunStage::Settled)).await;
}

#[tokio::test]
async fn a_removal_the_engine_could_not_make_ready_says_why() {
    let engines: Arc<Engines> = Arc::new(|| Err(blocked()));
    let components = Components::new(engines, unconsulted(), Arc::default());
    let stopped = components.remove_model(TEXT).await;
    assert_eq!(
        stopped.as_ref().err().and_then(Stop::refusal),
        Some(Refusal::Unavailable)
    );
    assert_eq!(
        cause(stopped).reason.as_deref(),
        Some("setup_engine_unavailable")
    );
}

#[tokio::test]
async fn a_full_check_replaces_the_rows_it_read() {
    let fixture = Fixture::new(Serving::Whole);
    let components = window(&fixture);
    components.verify(vec![ItemId::Browser]);
    let checked = until(&components, |view| {
        view.check
            .as_ref()
            .is_some_and(|check| check.stage != CheckStage::Running)
    })
    .await;
    let check = checked.check.unwrap();
    assert_eq!(
        (check.kind, check.stage),
        (CheckKind::Verify, CheckStage::Done)
    );
    assert_eq!(checked.rows_mode, Some(wire::CheckMode::Full));
    assert_eq!(checked.rows.len(), 1);
}

#[test]
fn a_download_two_roles_share_is_counted_once_in_the_review() {
    use cadrumo_application::{
        provisioning::plan::{PlanEntry, PlanPart},
        value::HostName,
    };
    let part = |role: &str, model: &str| PlanPart {
        part_id: role.into(),
        download_bytes: Some(100),
        source_hosts: vec![HostName::new(MODEL_HOST).unwrap()],
        destination: Some(Destination::OllamaModels),
        installs_outside_program: false,
        target_version: Some(model.into()),
    };
    let entry = PlanEntry::of_parts(
        ItemId::LocalAi,
        vec![
            part("text_extraction", TEXT),
            part("column_role_mapping", TEXT),
        ],
        Destination::OllamaModels,
    )
    .unwrap();
    let plan = SetupPlan::new(vec![entry], Some(512 * GIB)).unwrap();
    let shown = review_view(&plan, &Locations::under(Path::new("/state")));
    assert_eq!(
        shown.entries[0]
            .parts
            .iter()
            .map(|part| part.download_bytes)
            .collect::<Vec<_>>(),
        [Some(100), Some(0)]
    );
}

/// The plan a start of the local AI alone puts under review, downloading `download` when
/// one is asked for, with the window that asked for it and the operation it belongs to.
async fn local_ai_plan(
    fixture: &Fixture,
    replies: Replies,
    download: Option<wire::ModelDownload>,
) -> (Components, String, wire::Review) {
    let (components, _) = serving(fixture, replies);
    components
        .start(ItemId::LocalAi, false, download)
        .await
        .unwrap();
    let asked = until(&components, |view| {
        matches!(stage(view), Some(RunStage::Review | RunStage::Settled))
    })
    .await;
    let run = asked.runs.first().expect("a setup");
    assert_eq!(
        run.stage,
        RunStage::Review,
        "the plan waits for the window, but the setup ended {:?} {:?}",
        run.outcome,
        run.failure
    );
    let (operation, plan) = review(&asked);
    (components, operation, plan)
}

/// Declines the plan under review, so nothing is set up.
async fn decline(components: &Components, operation: &str, plan: &wire::Review) {
    components
        .answer(operation, &plan.plan_digest, wire::Decision::Reject)
        .await
        .unwrap();
    until(components, |view| stage(view) == Some(RunStage::Settled)).await;
}

#[tokio::test]
async fn general_setup_plans_the_local_ai_program_alone() {
    let fixture = Fixture::new(Serving::Whole).with_program();
    let (components, operation, plan) = local_ai_plan(&fixture, Replies::default(), None).await;
    let entry = &plan.entries[0];
    assert_eq!(entry.item, "local_ai");
    assert_eq!(
        entry
            .parts
            .iter()
            .map(|part| (part.part.as_str(), part.download_bytes))
            .collect::<Vec<_>>(),
        [("program", Some(PROGRAM_BYTES))]
    );
    assert_eq!(fixture.downloads(), 0, "nothing moves before the answer");
    decline(&components, &operation, &plan).await;
}

#[tokio::test]
async fn an_added_model_no_catalogue_sizes_is_planned_with_an_unknown_download() {
    let fixture = Fixture::new(Serving::Whole).with_program();
    let replies = Replies::serving(&[TEXT], &[ADDED], &[(TEXT, Some(2 * GB))]);
    let (components, operation, plan) =
        local_ai_plan(&fixture, replies, Some(requested(LOCAL, ADDED))).await;
    let entry = &plan.entries[0];
    assert_eq!(
        entry
            .parts
            .iter()
            .map(|part| (part.part.as_str(), part.download_bytes))
            .collect::<Vec<_>>(),
        [("program", Some(PROGRAM_BYTES)), ("download", None)]
    );
    assert_eq!(entry.parts[1].model.as_deref(), Some(ADDED));
    // The entry totals what is known; the unsized part says the rest is not.
    assert_eq!(entry.download_bytes, Some(PROGRAM_BYTES));
    assert!(plan.has_unknown_size);
    assert_eq!(fixture.downloads(), 0, "nothing moves before the answer");
    decline(&components, &operation, &plan).await;
    // The row the declined plan read says its size is unknown rather than what is known.
    let local_ai = components
        .view()
        .rows
        .into_iter()
        .find(|row| row.item == "local_ai")
        .expect("the local AI's row");
    assert_eq!(local_ai.size_bytes, None);
}

#[tokio::test]
async fn a_size_the_catalogue_states_differently_is_a_plan_the_person_approves_anew() {
    let mut digests = Vec::new();
    for size in [2 * GB, 2 * GB + 1] {
        let fixture = Fixture::new(Serving::Whole).with_program();
        let replies = Replies::serving(&[TEXT], &[], &[(TEXT, Some(size))]);
        let (components, operation, plan) =
            local_ai_plan(&fixture, replies, Some(requested(LOCAL, TEXT))).await;
        digests.push(plan.plan_digest.clone());
        decline(&components, &operation, &plan).await;
    }
    assert_ne!(digests[0], digests[1]);
}

#[tokio::test]
async fn a_download_that_cannot_be_admitted_refuses_the_start_and_runs_nothing() {
    let unreadable = serde_json::json!({
        "unreadable": true, "models": [], "reading": null, "local_lanes": [], "revision": "a".repeat(64),
    });
    let cases = [
        (
            "a model on no list",
            Replies::serving(&[TEXT], &[], &[(VISION, Some(GB))]),
            Refusal::ModelSelectionUnusable,
        ),
        (
            "an unreadable list",
            Replies::serving(&[TEXT], &[], &[]).answering("local_models", unreadable),
            Refusal::ModelSelectionUnusable,
        ),
        (
            "a service that does not answer",
            Replies::default(),
            Refusal::Unavailable,
        ),
    ];
    for (name, replies, expected) in cases {
        let fixture = Fixture::new(Serving::Whole);
        let (components, _) = serving(&fixture, replies);
        let start = || components.start(ItemId::LocalAi, false, Some(requested(LOCAL, VISION)));
        assert_eq!(refusal(start().await), Err(expected), "{name}");
        assert!(components.view().runs.is_empty(), "{name}: no run is shown");
        // The refusal is the start's own: asking again is refused the same way.
        assert_eq!(refusal(start().await), Err(expected), "{name}");
        assert_eq!(fixture.downloads(), 0, "{name}");
    }
}

#[tokio::test]
async fn stopping_a_setup_another_window_runs_consults_no_service() {
    let gate = Arc::new(Released::default());
    let fixture = Fixture::new(Serving::Gated(gate.clone()));
    let owner = running(&fixture).await;
    let (follower, replies) = serving(&fixture, Replies::default());
    follower.start(ItemId::Browser, false, None).await.unwrap();
    let run = until(&follower, moving)
        .await
        .runs
        .into_iter()
        .next()
        .unwrap();
    let before = replies.asked();
    // Asking another setup to stop builds an engine for nothing but that request.
    follower.cancel(&run.operation_id).await.unwrap();
    assert_eq!(replies.asked(), before);
    gate.release();
    until(&owner, |view| stage(view) == Some(RunStage::Settled)).await;
    until(&follower, |view| stage(view) == Some(RunStage::Settled)).await;
}

/// Stores `model` (`name:tag` on the default registry) in the fixture's models folder
/// as the program would, with one layer of its own, and returns its manifest.
fn stored_model(fixture: &Fixture, model: &str) -> PathBuf {
    let (name, tag) = model.split_once(':').expect("a tagged model");
    let manifest = Locations::under(&fixture.root())
        .models
        .join("manifests")
        .join(MODEL_HOST)
        .join("library")
        .join(name)
        .join(tag);
    std::fs::create_dir_all(manifest.parent().unwrap()).unwrap();
    let digest = |seed: &str| format!("sha256:{}", hex(&Sha256::digest(seed.as_bytes())));
    let layer = |seed: &str| serde_json::json!({"digest": digest(seed), "size": 1});
    std::fs::write(
        &manifest,
        serde_json::json!({"config": layer(&format!("{model} config")),
                           "layers": [layer(&format!("{model} weights"))]})
        .to_string(),
    )
    .unwrap();
    manifest
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

#[tokio::test]
async fn removing_a_model_deletes_it_alone_and_reads_the_rows_after() {
    let fixture = Fixture::new(Serving::Whole);
    let removed = stored_model(&fixture, TEXT);
    let kept = stored_model(&fixture, VISION);
    let (components, replies) = serving(&fixture, Replies::default());
    assert_eq!(refusal(components.remove_model(TEXT).await), Ok(()));
    assert!(!removed.exists());
    assert!(kept.exists());
    assert!(!components.view().rows.is_empty());
    assert!(replies.asked().is_empty(), "a removal consults no service");
}

#[tokio::test]
async fn a_name_the_engine_cannot_pull_is_refused_before_any_engine_runs() {
    let fixture = Fixture::new(Serving::Whole);
    let (components, replies) = serving(&fixture, Replies::default());
    assert_eq!(
        refusal(components.remove_model("not a model").await),
        Err(Refusal::ModelSelectionUnusable)
    );
    assert!(replies.asked().is_empty());
}

#[tokio::test]
async fn explicit_download_plans_only_that_model_and_a_resume_keeps_it() {
    let fixture = Fixture::new(Serving::Whole).with_program();
    let replies = Replies::serving(
        &[VISION, TEXT],
        &[],
        &[(TEXT, Some(2 * GB)), (VISION, Some(3 * GB))],
    )
    .answering(
        "catalog",
        declared(
            &[VISION, TEXT],
            &[(TEXT, Some(2 * GB)), (VISION, Some(3 * GB))],
        ),
    );
    let (components, replies) = serving(&fixture, replies);
    components
        .start(ItemId::LocalAi, false, Some(requested(LOCAL, VISION)))
        .await
        .unwrap();
    let asked = until(&components, |view| stage(view) == Some(RunStage::Review)).await;
    let (operation, plan) = review(&asked);
    assert_eq!(plan.entries.len(), 1);
    let parts = &plan.entries[0].parts;
    assert!(asked.valid());
    assert_eq!(parts[1].model.as_deref(), Some(VISION));
    assert_eq!(
        parts
            .iter()
            .map(|part| (part.part.as_str(), part.download_bytes))
            .collect::<Vec<_>>(),
        [("program", Some(PROGRAM_BYTES)), ("download", Some(3 * GB))]
    );
    assert_eq!(plan.entries[0].download_bytes, Some(PROGRAM_BYTES + 3 * GB));
    assert_eq!(fixture.downloads(), 0);
    assert_eq!(replies.asked(), vec!["status", "catalog"]);
    decline(&components, &operation, &plan).await;
    // A resumed request uses the same download and digest, without substituting TEXT.
    components.start(ItemId::LocalAi, true, None).await.unwrap();
    let asked = until(&components, |view| stage(view) == Some(RunStage::Review)).await;
    let (operation, resumed) = review(&asked);
    assert_eq!(resumed.plan_digest, plan.plan_digest);
    decline(&components, &operation, &resumed).await;
}

/// The setup of `item` the window shows, if any.
fn run_of(view: &View, item: ItemId) -> Option<&wire::Run> {
    view.runs.iter().find(|run| run.item == item.as_str())
}

fn stage_of(view: &View, item: ItemId) -> Option<RunStage> {
    run_of(view, item).map(|run| run.stage)
}

/// The progress of the one item a setup sets up.
fn progress(run: &wire::Run) -> &wire::ItemProgress {
    let [item] = run.items.as_slice() else {
        panic!("a setup sets up one item: {:?}", run.items);
    };
    item
}

/// Starts `item` in `components`, approves the plan it shows, and returns its operation.
async fn approved(components: &Components, item: ItemId) -> String {
    components.start(item, false, None).await.unwrap();
    let asked = until(components, |view| {
        stage_of(view, item) == Some(RunStage::Review)
    })
    .await;
    let run = asked
        .runs
        .iter()
        .find(|run| run.item == item.as_str())
        .expect("the item's setup");
    let plan = run.review.clone().expect("a plan under review");
    assert!(
        plan.entries.iter().all(|entry| entry.item == item.as_str()),
        "a setup plans its own item alone"
    );
    let operation = run.operation_id.clone();
    components
        .answer(&operation, &plan.plan_digest, wire::Decision::Apply)
        .await
        .unwrap();
    operation
}

#[tokio::test]
async fn the_browser_and_the_local_ai_set_up_at_the_same_time_each_on_its_own() {
    let gate = Arc::new(Released::default());
    let fixture = Fixture::new(Serving::Gated(gate.clone())).with_program();
    let components = window(&fixture);

    let browser = approved(&components, ItemId::Browser).await;
    until(&components, |view| {
        run_of(view, ItemId::Browser).is_some_and(|run| progress(run).completed.is_some())
    })
    .await;
    // The browser's setup holds its own lock alone: the local AI is planned beside it.
    let local_ai = approved(&components, ItemId::LocalAi).await;
    assert_ne!(browser, local_ai);
    let both = until(&components, |view| {
        run_of(view, ItemId::LocalAi).is_some_and(|run| {
            progress(run)
                .parts
                .iter()
                .any(|part| part.completed.is_some())
        })
    })
    .await;
    assert_eq!(
        both.runs
            .iter()
            .map(|run| (run.item.as_str(), run.stage))
            .collect::<Vec<_>>(),
        [
            ("browser", RunStage::Running),
            ("local_ai", RunStage::Running)
        ],
        "both run at once, in the engine's item order"
    );
    let program = &progress(&both.runs[1]).parts[0];
    assert_eq!(
        (
            program.part.as_str(),
            program.model.as_deref(),
            program.step
        ),
        ("program", None, Some(wire::Step::Download))
    );
    assert!(program.completed.unwrap() <= program.total.unwrap());
    assert_eq!(program.total, Some(PROGRAM_BYTES));
    assert!(
        progress(&both.runs[0]).parts.is_empty(),
        "the browser has no parts"
    );
    assert!(both.details.contains(&format!("operation: {browser}")));
    assert!(both.details.contains(&format!("operation: {local_ai}")));

    // A second start of a running item joins it.
    components
        .start(ItemId::LocalAi, false, None)
        .await
        .unwrap();
    assert_eq!(
        run_of(&components.view(), ItemId::LocalAi)
            .unwrap()
            .operation_id,
        local_ai
    );
    // The local AI's setup holds its writer lock, so no model is removed meanwhile.
    assert_eq!(
        refusal(components.remove_model(TEXT).await),
        Err(Refusal::Busy)
    );
    // A cancel names its setup: the local AI's goes on.
    components.cancel(&browser).await.unwrap();
    let view = components.view();
    assert!(run_of(&view, ItemId::Browser).unwrap().cancel_requested);
    let other = run_of(&view, ItemId::LocalAi).unwrap();
    assert!(other.cancellable && !other.cancel_requested);

    gate.release();
    let settled = until(&components, |view| {
        stage_of(view, ItemId::Browser) == Some(RunStage::Settled)
            && stage_of(view, ItemId::LocalAi) == Some(RunStage::Settled)
    })
    .await;
    assert_eq!(settled.runs[0].outcome, Some(Outcome::Cancelled));
    let local_ai_run = &settled.runs[1];
    // The bytes matched their pin but were no archive, so the program did not install.
    assert_eq!(local_ai_run.outcome, Some(Outcome::Failed));
    let program = &progress(local_ai_run).parts[0];
    assert_eq!(
        (program.completed, program.total),
        (Some(PROGRAM_BYTES), Some(PROGRAM_BYTES))
    );
    let result = program.result.as_ref().expect("the program part's result");
    assert_eq!(
        (result.changed, result.failure, result.transferred_bytes),
        (false, local_ai_run.failure, PROGRAM_BYTES)
    );
}

#[tokio::test]
async fn an_answer_and_a_cancel_reach_the_setup_they_name_among_several() {
    let fixture = Fixture::new(Serving::Whole).with_program();
    let components = window(&fixture);
    components
        .start(ItemId::Browser, false, None)
        .await
        .unwrap();
    components
        .start(ItemId::LocalAi, false, None)
        .await
        .unwrap();
    let asked = until(&components, |view| {
        stage_of(view, ItemId::Browser) == Some(RunStage::Review)
            && stage_of(view, ItemId::LocalAi) == Some(RunStage::Review)
    })
    .await;
    let [browser, local_ai] = asked.runs.as_slice() else {
        panic!("one setup per item: {:?}", asked.runs);
    };
    let local_ai_digest = local_ai.review.as_ref().unwrap().plan_digest.clone();
    // Each setup waits on the digest of its own plan alone.
    assert_eq!(
        components
            .answer(
                &browser.operation_id,
                &local_ai_digest,
                wire::Decision::Apply
            )
            .await,
        Err(Refusal::PlanChanged)
    );
    components
        .answer(
            &local_ai.operation_id,
            &local_ai_digest,
            wire::Decision::Reject,
        )
        .await
        .unwrap();
    let view = until(&components, |view| {
        stage_of(view, ItemId::LocalAi) == Some(RunStage::Settled)
    })
    .await;
    assert_eq!(
        view.runs[1].outcome,
        Some(Outcome::Rejected),
        "the rejection reached the local AI's setup"
    );
    assert_eq!(
        view.runs[0].stage,
        RunStage::Review,
        "the browser's setup still waits"
    );
    components.cancel(&browser.operation_id).await.unwrap();
    let view = until(&components, |view| {
        stage_of(view, ItemId::Browser) == Some(RunStage::Settled)
    })
    .await;
    assert_eq!(view.runs[0].outcome, Some(Outcome::Cancelled));
    assert_eq!(view.runs[1].outcome, Some(Outcome::Rejected));
    assert_eq!(fixture.downloads(), 0);
}

/// A plan of the local AI's program and two roles that read with one model.
fn local_ai_entry() -> PlanEntry {
    use cadrumo_application::{provisioning::plan::PlanPart, value::HostName};
    let part = |id: &str, version: &str, bytes: u64| PlanPart {
        part_id: id.into(),
        download_bytes: Some(bytes),
        source_hosts: vec![HostName::new(MODEL_HOST).unwrap()],
        destination: Some(Destination::OllamaModels),
        installs_outside_program: false,
        target_version: Some(version.into()),
    };
    PlanEntry::of_parts(
        ItemId::LocalAi,
        vec![
            part(PROGRAM_PART, "9.9.9", 100),
            part("text_extraction", TEXT, 300),
            part("column_role_mapping", TEXT, 300),
        ],
        Destination::OllamaModels,
    )
    .unwrap()
}

fn local_ai_track() -> SetupTrack {
    let mut track = SetupTrack {
        item: ItemId::LocalAi,
        operation_id: "a".repeat(64),
        download: None,
        stage: RunStage::Planning,
        review: None,
        answers: None,
        answered: true,
        following: false,
        items: Vec::new(),
        phases: Vec::new(),
        hosts: BTreeSet::new(),
        cancellation: Arc::default(),
        cancel_requested: false,
        outcome: None,
        failure: None,
    };
    track.planned(&local_ai_entry());
    track
}

/// The events the engine reports as the program downloads and installs and the model
/// begins downloading.
fn program_then_model() -> Vec<Event> {
    let item = ItemId::LocalAi;
    let part = |part: &str, model: Option<&str>, step| Event::Part {
        item,
        part: part.into(),
        model: model.map(str::to_owned),
        step,
    };
    let bytes = |part: &str, completed, total| Event::PartProgress {
        item,
        part: part.into(),
        completed,
        total,
    };
    vec![
        Event::Phase {
            item,
            step: SetupStep::Download,
        },
        part(PROGRAM_PART, None, SetupStep::Download),
        Event::Progress {
            item,
            completed: 100,
            total: 400,
        },
        bytes(PROGRAM_PART, 100, 100),
        part(PROGRAM_PART, None, SetupStep::Install),
        part("text_extraction", Some(TEXT), SetupStep::Download),
        Event::Progress {
            item,
            completed: 250,
            total: 400,
        },
        bytes("text_extraction", 150, 300),
    ]
}

/// What the window shows of each part: id, model, step and bytes.
type PartRow<'a> = (
    &'a str,
    Option<&'a str>,
    Option<wire::Step>,
    Option<u64>,
    Option<u64>,
);

#[test]
fn the_local_ais_parts_carry_their_own_steps_and_bytes() {
    let mut track = local_ai_track();
    for event in program_then_model() {
        take_event(&mut track, event);
    }
    let shown = run(&track);
    assert_eq!(shown.item, "local_ai");
    let item = progress(&shown);
    assert_eq!((item.completed, item.total), (Some(250), Some(400)));
    let parts: Vec<PartRow<'_>> = item
        .parts
        .iter()
        .map(|part| {
            (
                part.part.as_str(),
                part.model.as_deref(),
                part.step,
                part.completed,
                part.total,
            )
        })
        .collect();
    let expected: [PartRow<'_>; 3] = [
        (
            "program",
            None,
            Some(wire::Step::Install),
            Some(100),
            Some(100),
        ),
        (
            "text_extraction",
            Some(TEXT),
            Some(wire::Step::Download),
            Some(150),
            Some(300),
        ),
        // The second role reads with the model the first pulls.
        ("column_role_mapping", Some(TEXT), None, None, None),
    ];
    assert_eq!(parts, expected);
    assert!(item.parts.iter().all(|part| part.result.is_none()));
}

/// How the engine ends a setup that stopped at `item`, if at one.
fn ended(outcome: Ended, item: Option<ItemId>, failure: Option<FailureCategory>) -> Report {
    Report {
        outcome,
        mode: CheckMode::Quick,
        rows: Vec::new(),
        plan: None,
        item,
        failure,
        items: Vec::new(),
    }
}

#[test]
fn a_setup_that_stops_in_a_part_fails_that_part_alone() {
    let mut track = local_ai_track();
    for event in program_then_model() {
        take_event(&mut track, event);
    }
    settle(
        &mut track,
        &ended(
            Ended::Failed,
            Some(ItemId::LocalAi),
            Some(FailureCategory::HostUnreachable),
        ),
    );
    let shown = run(&track);
    let results: Vec<_> = progress(&shown)
        .parts
        .iter()
        .map(|part| {
            part.result
                .as_ref()
                .map(|result| (result.changed, result.failure, result.transferred_bytes))
        })
        .collect();
    assert_eq!(
        results,
        [
            Some((true, None, 100)),
            Some((false, Some(wire::Failure::HostUnreachable), 150)),
            None,
        ]
    );

    let mut completed = local_ai_track();
    for event in program_then_model() {
        take_event(&mut completed, event);
    }
    settle(&mut completed, &ended(Ended::Completed, None, None));
    let shown = run(&completed);
    assert!(
        progress(&shown)
            .parts
            .iter()
            .all(|part| part.result.as_ref().is_some_and(|result| result.changed)),
        "a completed setup set up every part, including one sharing a model"
    );
}
