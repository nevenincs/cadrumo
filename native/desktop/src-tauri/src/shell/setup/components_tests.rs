//! The window's engine against a real engine of a throwaway installation: a
//! storage root of its own, the bundled driver's layout, pinned archives and a
//! local TLS publisher the engine's network reaches. Nothing here stands in
//! for the engine; every review, event and report is the engine's own.
use super::super::wire::{Google, Snapshot};
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
    (table, served)
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
        let certificate = TestCertificate::new(&[HOST]);
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
    view.setup.as_ref().map(|run| run.stage)
}

fn compose(view: View, google: Google) -> Option<Snapshot> {
    super::super::compose(view, google)
}

fn review(snapshot: &Snapshot) -> (String, wire::Review) {
    let run = snapshot.setup.as_ref().expect("a setup");
    (
        run.operation_id.clone(),
        run.review.clone().expect("a plan under review"),
    )
}

async fn reviewing(components: &Components) -> (String, wire::Review) {
    components.start(None, false).await.unwrap();
    review(&until(components, |view| stage(view) == Some(RunStage::Review)).await)
}

#[tokio::test]
async fn the_first_read_carries_every_items_codes_and_no_words() {
    let fixture = Fixture::new(Serving::Whole);
    let components = Components::new(fixture.engines());
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
    for word in ["name", "sentence", "action_label", "licence_notice"] {
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
    let components = Components::new(fixture.engines());
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
    let run = settled.setup.unwrap();
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
    let components = Components::new(fixture.engines());
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
    let run = settled.setup.unwrap();
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
    let components = Components::new(fixture.engines());
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
    components.start(None, true).await.unwrap();
    assert_ne!(stage(&components.view()), Some(RunStage::Review));
    let resumed = until(&components, |view| stage(view) == Some(RunStage::Settled)).await;
    let run = resumed.setup.unwrap();
    assert_ne!(run.operation_id, operation);
    assert_eq!(run.outcome, Some(Outcome::Failed));
    assert!(
        run.items[0]
            .result
            .as_ref()
            .is_some_and(|result| result.failure.is_some())
    );
    // A window that approved nothing yet still asks.
    let other = Components::new(fixture.engines());
    other.start(None, true).await.unwrap();
    until(&other, |view| stage(view) == Some(RunStage::Review)).await;
    other.close().await;
}

#[tokio::test]
async fn a_cancel_stops_a_running_setup_at_its_next_chunk() {
    let gate = Arc::new(Released::default());
    let fixture = Fixture::new(Serving::Gated(gate.clone()));
    let components = Components::new(fixture.engines());
    let (operation, plan) = reviewing(&components).await;
    components
        .answer(&operation, &plan.plan_digest, wire::Decision::Apply)
        .await
        .unwrap();
    let running = until(&components, |view| {
        view.setup
            .as_ref()
            .is_some_and(|run| run.items.iter().any(|item| item.completed.is_some()))
    })
    .await;
    let run = running.setup.unwrap();
    assert_eq!(run.stage, RunStage::Running);
    assert!(run.cancellable);
    let progress = &run.items[0];
    assert_eq!(progress.step, Some(wire::Step::Download));
    assert!(progress.completed.unwrap() <= progress.total.unwrap());
    components.cancel(&operation).await.unwrap();
    assert_eq!(
        components.cancel(&operation).await,
        Err(Refusal::NotCancellable)
    );
    let asked = components.view().setup.unwrap();
    assert!(asked.cancel_requested && !asked.cancellable);
    gate.release();
    let settled = until(&components, |view| stage(view) == Some(RunStage::Settled)).await;
    let run = settled.setup.unwrap();
    assert_eq!((run.outcome, run.failure), (Some(Outcome::Cancelled), None));
    assert_eq!(
        run.items[0].result.as_ref().unwrap().failure,
        Some(wire::Failure::Cancelled)
    );
    assert_eq!(
        components.cancel(&operation).await,
        Err(Refusal::NotPending)
    );
}

/// Whether the window shows bytes moving for an item of its setup.
fn moving(view: &View) -> bool {
    view.setup
        .as_ref()
        .is_some_and(|run| run.items.iter().any(|item| item.completed.is_some()))
}

/// A window whose approved setup holds at the gate halfway through its first archive.
async fn running(fixture: &Fixture) -> Components {
    let owner = Components::new(fixture.engines());
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
    let follower = Components::new(fixture.engines());
    follower.start(None, false).await.unwrap();
    let run = until(&follower, moving).await.setup.unwrap();
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
    assert!(leaving.view().setup.is_none());
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
        .setup
        .unwrap();
    let followed = until(&follower, |view| stage(view) == Some(RunStage::Settled)).await;
    let run = followed.setup.unwrap();
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
        follower.cancel(&run.operation_id).await,
        Err(Refusal::NotCancellable)
    );
    let asked = follower.view().setup.unwrap();
    assert!(asked.cancel_requested && !asked.cancellable);
    assert_eq!(
        asked.stage,
        RunStage::Running,
        "it follows until the setup ends"
    );
    gate.release();
    let owned = until(&owner, |view| stage(view) == Some(RunStage::Settled))
        .await
        .setup
        .unwrap();
    assert_eq!(owned.outcome, Some(Outcome::Cancelled));
    let followed = until(&follower, |view| stage(view) == Some(RunStage::Settled))
        .await
        .setup
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
    let components = Components::new(fixture.engines());
    let (operation, _) = reviewing(&components).await;
    components.cancel(&operation).await.unwrap();
    let settled = until(&components, |view| stage(view) == Some(RunStage::Settled)).await;
    assert_eq!(settled.setup.unwrap().outcome, Some(Outcome::Cancelled));
    assert_eq!(fixture.downloads(), 0);
}

#[tokio::test]
async fn a_second_start_joins_the_setup_that_waits() {
    let fixture = Fixture::new(Serving::Whole);
    let components = Components::new(fixture.engines());
    let (operation, _) = reviewing(&components).await;
    components.start(None, false).await.unwrap();
    assert_eq!(components.view().setup.unwrap().operation_id, operation);
    components.close().await;
    // Closing the window declines the plan and waits for its worker.
    let run = components.view().setup.unwrap();
    assert_eq!(run.outcome, Some(Outcome::Cancelled));
    assert_eq!(
        components.start(None, false).await,
        Err(Refusal::Unavailable)
    );
}

#[tokio::test]
async fn too_little_space_and_no_network_refuse_before_anything_is_asked() {
    let mut fixture = Fixture::new(Serving::Whole);
    fixture.free_bytes = Some(1);
    let components = Components::new(fixture.engines());
    components.start(None, false).await.unwrap();
    let full = until(&components, |view| stage(view) == Some(RunStage::Settled)).await;
    assert_eq!(full.setup.unwrap().outcome, Some(Outcome::NotEnoughSpace));

    fixture.free_bytes = Some(512 * GIB);
    fixture.reachable = false;
    let components = Components::new(fixture.engines());
    components
        .start(Some(vec![ItemId::Browser]), false)
        .await
        .unwrap();
    let offline = until(&components, |view| stage(view) == Some(RunStage::Settled)).await;
    let run = offline.setup.unwrap();
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
    let components = Components::new(fixture.engines());
    components
        .start(Some(vec![ItemId::LocalAi]), false)
        .await
        .unwrap();
    let settled = until(&components, |view| stage(view) == Some(RunStage::Settled)).await;
    let run = settled.setup.unwrap();
    assert_eq!(
        (run.outcome, run.failure),
        (Some(Outcome::Failed), Some(wire::Failure::NotInThisBuild))
    );
}

#[tokio::test]
async fn a_full_check_replaces_the_rows_it_read() {
    let fixture = Fixture::new(Serving::Whole);
    let components = Components::new(fixture.engines());
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
fn a_shared_download_is_counted_once_and_a_barred_licence_is_named() {
    use cadrumo_application::{
        provisioning::plan::{PartLicence, PlanEntry, PlanPart},
        value::HostName,
    };
    let host = || vec![HostName::new("registry.ollama.ai").unwrap()];
    let part = |role: &str, model: &str, advisories: Vec<Advisory>| PlanPart {
        part_id: role.into(),
        download_bytes: Some(100),
        source_hosts: host(),
        destination: Some(Destination::OllamaModels),
        installs_outside_program: false,
        target_version: Some(format!("{model}@{}", "a".repeat(64))),
        advisories,
        licence: Some(PartLicence {
            spdx_id: "LicenseRef-Qwen-Research".into(),
            name: "Qwen RESEARCH LICENSE AGREEMENT".into(),
        }),
    };
    let entry = PlanEntry::of_parts(
        ItemId::LocalAi,
        vec![
            part(
                "text_extraction",
                "qwen2.5:3b",
                vec![Advisory::LicenceCommercialUseBarred],
            ),
            part(
                "column_role_mapping",
                "qwen2.5:3b",
                vec![Advisory::LicenceCommercialUseBarred],
            ),
        ],
        Destination::OllamaModels,
    )
    .unwrap();
    let plan = SetupPlan::new(vec![entry], Some(512 * GIB)).unwrap();
    let shown = review_view(&plan, &Locations::under(Path::new("/state")));
    let entry = &shown.entries[0];
    assert_eq!(
        entry
            .parts
            .iter()
            .map(|part| part.download_bytes)
            .collect::<Vec<_>>(),
        [Some(100), Some(0)]
    );
    assert_eq!(
        entry.licences,
        [wire::Licence {
            model: "qwen2.5:3b".into(),
            licence: "Qwen RESEARCH LICENSE AGREEMENT".into(),
        }]
    );
    assert_eq!(
        entry.advisories,
        [wire::Advisory::LicenceCommercialUseBarred]
    );
}
