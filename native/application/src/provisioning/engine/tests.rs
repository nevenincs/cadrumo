//! The engine driven end to end the way the desktop drives it: engines built over a
//! storage root, the publisher's archives served over TLS, the stand-in browser, and the
//! stand-in local AI server. Everything after the configuration is the production code
//! path; the tests assert what the engines report, record and leave on disk.

use super::*;
use crate::provisioning::{
    browser::tests::{
        Archives, BROWSER_VERSION, HOST, driver_package, fake_environment, fake_leading,
        launchable_archives,
    },
    local_ai::{
        fake_ollama::FakeOllama,
        models::SelectedModel,
        program::{SERVER_RECORD, SERVER_RECORD_SCHEMA, ServerRecord},
    },
    state::RecoveryAction,
    test_servers::{Released, Reply, Request, TestCertificate, TlsServer, network_to, response},
};
use serde_json::{Value, json};
use std::{
    collections::VecDeque,
    io::{Cursor, Write},
    sync::{Mutex, mpsc},
};

const GIB: u64 = 1024 * 1024 * 1024;
/// Obviously synthetic names: the engine knows no model, so its tests name none.
const TEXT: &str = "synthetic-text:test";
const VISION: &str = "synthetic-vision:test";
const KEPT: &str = "synthetic-kept:test";
const PROGRAM_VERSION: &str = "9.9.9";
const PROGRAM_PATH: &str = "/ollama/ollama/releases/download/v9.9.9/ollama.zip";
const EXECUTABLE: &str = if cfg!(windows) {
    "ollama.exe"
} else {
    "bin/ollama"
};

/// A gate a test holds a served archive at; dropping it lets the archive finish.
struct Gate(Arc<Released>);

impl Gate {
    fn open(self) {}
}

impl Drop for Gate {
    fn drop(&mut self) {
        self.0.release();
    }
}

/// Serves `served` by path, from a `Range` request's start byte, holding the first
/// unranged answer of each queued gate halfway through its body.
fn publisher(
    certificate: &TestCertificate,
    served: BTreeMap<String, Vec<u8>>,
    gates: Arc<Mutex<VecDeque<Arc<Released>>>>,
) -> TlsServer {
    TlsServer::start(certificate, move |request: &Request| {
        let Some(bytes) = served.get(request.target()) else {
            return Reply::Bytes(response(
                "404 Not Found",
                &[("Content-Length", "0".into())],
                b"",
            ));
        };
        let start = request
            .header("range")
            .and_then(|range| range.strip_prefix("bytes="))
            .and_then(|range| range.strip_suffix('-'))
            .and_then(|start| start.parse::<usize>().ok())
            .unwrap_or(0);
        let status = if start > 0 { "206 Partial" } else { "200 OK" };
        let head = response(
            status,
            &[
                ("Content-Length", (bytes.len() - start).to_string()),
                (
                    "Content-Range",
                    format!("bytes {start}-{}/{}", bytes.len() - 1, bytes.len()),
                ),
            ],
            b"",
        );
        let gate = (start == 0)
            .then(|| gates.lock().unwrap().pop_front())
            .flatten();
        match gate {
            Some(gate) => {
                let half = bytes.len() / 2;
                Reply::Gated {
                    first: [head, bytes[..half].to_vec()].concat(),
                    rest: bytes[half..].to_vec(),
                    gate,
                }
            }
            None => Reply::Bytes([head, bytes[start..].to_vec()].concat()),
        }
    })
}

/// One model as the program stores it: its manifest and each layer by digest.
struct StoredModel {
    manifest: Vec<u8>,
    blobs: Vec<(String, Vec<u8>)>,
}

impl StoredModel {
    fn new(seed: u8) -> Self {
        let blobs: Vec<(String, Vec<u8>)> = [vec![seed; 5], vec![seed.wrapping_add(1); 300]]
            .into_iter()
            .map(|bytes| (format!("sha256:{}", Sha256Digest::of(&bytes)), bytes))
            .collect();
        let layer =
            |(digest, bytes): &(String, Vec<u8>)| json!({"digest": digest, "size": bytes.len()});
        let manifest = json!({
            "schemaVersion": 2,
            "config": layer(&blobs[0]),
            "layers": [layer(&blobs[1])],
        })
        .to_string()
        .into_bytes();
        Self { manifest, blobs }
    }

    fn size(&self) -> u64 {
        self.blobs.iter().map(|(_, bytes)| bytes.len() as u64).sum()
    }

    fn files(&self, models: &Path, name: &str) -> Vec<(PathBuf, Vec<u8>)> {
        let (model, tag) = name.split_once(':').unwrap();
        let mut files = vec![(
            models
                .join("manifests/registry.ollama.ai/library")
                .join(model)
                .join(tag),
            self.manifest.clone(),
        )];
        for (digest, bytes) in &self.blobs {
            let hex = digest.strip_prefix("sha256:").unwrap();
            files.push((models.join(format!("blobs/sha256-{hex}")), bytes.clone()));
        }
        files
    }

    /// Stores the model in `models`, as the program does once a pull succeeds.
    fn store(&self, models: &Path, name: &str) {
        for (path, bytes) in self.files(models, name) {
            fs::create_dir_all(path.parent().unwrap()).unwrap();
            fs::write(path, bytes).unwrap();
        }
    }

    fn stored(&self, models: &Path, name: &str) -> usize {
        self.files(models, name)
            .iter()
            .filter(|(path, _)| path.exists())
            .count()
    }

    /// What the program answers while it pulls this model, ending in success.
    fn pull_lines(&self) -> Vec<Value> {
        let mut lines = vec![json!({"status": "pulling manifest"})];
        for (digest, bytes) in &self.blobs {
            lines.push(json!({"status": "pulling", "digest": digest, "total": bytes.len(), "completed": bytes.len()}));
        }
        lines.push(json!({"status": "success"}));
        lines
    }
}

/// A local AI archive for this platform: the program's layout in miniature, stored
/// uncompressed so it stays inside the program's unpacked-size bound.
fn program_archive() -> Vec<u8> {
    let mut zip = zip::ZipWriter::new(Cursor::new(Vec::new()));
    let options = zip::write::SimpleFileOptions::default()
        .compression_method(zip::CompressionMethod::Stored)
        .unix_permissions(0o755);
    zip.start_file(EXECUTABLE, options).unwrap();
    zip.write_all(b"the local AI program").unwrap();
    zip.start_file("lib/ollama/runner", options.unix_permissions(0o644))
        .unwrap();
    zip.write_all(&[7u8; 4000]).unwrap();
    zip.finish().unwrap().into_inner()
}

/// What one setup reported and the events it sent while it ran.
struct Run {
    report: Report,
    events: Vec<Event>,
}

/// Everything one test's engines share: the folders, the pins, the publisher's server.
struct World {
    directory: tempfile::TempDir,
    certificate: TestCertificate,
    gates: Arc<Mutex<VecDeque<Arc<Released>>>>,
    server: TlsServer,
    ollama: Option<FakeOllama>,
    driver: bool,
    /// The local models the engines are given, as role, name and size.
    selection: Vec<(String, String, u64)>,
    /// The fixture computer's memory, with no NVIDIA card.
    memory_bytes: u64,
    /// Measure this computer as the installation does, instead of a fixture.
    measure_hardware: bool,
}

impl World {
    /// A world whose build carries the browser driver and its pinned archives.
    fn browser() -> Self {
        let directory = tempfile::tempdir().unwrap();
        driver_package(&directory.path().join("driver"));
        let Archives { table, served } = launchable_archives("engine");
        fs::create_dir_all(directory.path().join("pins")).unwrap();
        fs::write(directory.path().join("pins/browser_archives.toml"), table).unwrap();
        Self::serving(directory, served, true, None)
    }

    /// A world whose build carries only the local AI, its server played by the test, with
    /// a model selected for each role.
    fn local_ai(text: &StoredModel, vision: &StoredModel) -> Self {
        let directory = tempfile::tempdir().unwrap();
        let archive = program_archive();
        let pins = directory.path().join("pins");
        fs::create_dir_all(&pins).unwrap();
        fs::write(
            pins.join("local_ai_program.toml"),
            format!(
                "program = \"ollama\"\nversion = \"{PROGRAM_VERSION}\"\nhosts = [\"github.com\"]\n\n\
                 [[archives]]\nplatform = \"{}\"\nurl = \"https://github.com{PROGRAM_PATH}\"\n\
                 format = \"zip\"\nexecutable = \"{EXECUTABLE}\"\ndownload_bytes = {}\nsha256 = \"{}\"\n",
                Platform::current().unwrap().as_str(),
                archive.len(),
                Sha256Digest::of(&archive),
            ),
        )
        .unwrap();
        let models = directory.path().join("storage/models/ollama");
        let fake = FakeOllama::start(PROGRAM_VERSION);
        {
            let mut state = fake.state.lock().unwrap();
            // Roles pull in role order: the text model once, then the vision model.
            state.pulls = VecDeque::from([text.pull_lines(), vision.pull_lines()]);
            for (name, model) in [(VISION, vision), (TEXT, text)] {
                state
                    .installs
                    .insert(name.into(), model.files(&models, name));
                state.tags.insert(name.into());
            }
        }
        let mut world = Self::serving(
            directory,
            [(PROGRAM_PATH.to_owned(), archive)].into(),
            false,
            Some(fake),
        );
        world.selection = [
            ("vision_transcription", VISION, vision.size()),
            ("text_extraction", TEXT, text.size()),
            ("column_role_mapping", TEXT, text.size()),
            ("supply_nature_proposal", TEXT, text.size()),
        ]
        .into_iter()
        .map(|(role, name, size)| (role.to_owned(), name.to_owned(), size))
        .collect();
        world
    }

    fn serving(
        directory: tempfile::TempDir,
        served: BTreeMap<String, Vec<u8>>,
        driver: bool,
        ollama: Option<FakeOllama>,
    ) -> Self {
        let certificate = TestCertificate::new(&[HOST, "github.com", "registry.ollama.ai"]);
        let gates = Arc::new(Mutex::new(VecDeque::new()));
        let server = publisher(&certificate, served, gates.clone());
        Self {
            directory,
            certificate,
            gates,
            server,
            ollama,
            driver,
            selection: Vec::new(),
            memory_bytes: 64 * GIB,
            measure_hardware: false,
        }
    }

    fn root(&self) -> PathBuf {
        self.directory.path().join("storage")
    }

    fn models(&self) -> PathBuf {
        self.root().join("models/ollama")
    }

    fn programs(&self) -> PathBuf {
        self.root().join("components/ollama")
    }

    fn receipt(&self, file: &str) -> PathBuf {
        self.root().join("components/receipts").join(file)
    }

    /// A new engine of this installation, as the desktop builds one per command.
    fn engine(&self) -> Engine {
        let root = self.root();
        let measured = (!self.measure_hardware).then_some(Hardware {
            total_memory_bytes: Some(self.memory_bytes),
            nvidia_vram_bytes: None,
        });
        let mut engine = Engine::new(EngineConfig {
            storage_root: root.clone(),
            locations: Locations::under(&root),
            pins: ComponentPins::load(&self.directory.path().join("pins")).unwrap(),
            driver: self
                .driver
                .then(|| DriverManifest::read(&self.directory.path().join("driver")).unwrap()),
            platform: Platform::current(),
            network: network_to(self.certificate.roots(), self.server.address(), None),
            ambient: Box::new(|name| std::env::var_os(name)),
            local_ai_address: self
                .ollama
                .as_ref()
                .map_or_else(|| "127.0.0.1:23743".parse().unwrap(), FakeOllama::address),
            browser_environment: fake_environment(&format!("version={BROWSER_VERSION}")),
            scratch: root.join("tmp"),
            free_space: Box::new(|_| Some(1024 * GIB)),
            hardware: measured,
            policy: RetryPolicy::default(),
        })
        .unwrap();
        engine.browser_leading = fake_leading();
        let selected = self
            .selection
            .iter()
            .map(|(role, name, size)| SelectedModel::new(role, name, Some(*size)))
            .collect::<Result<_, _>>()
            .unwrap();
        engine.select_local_models(LocalModels::new(selected).unwrap());
        engine
    }

    /// The quick rows of every item.
    fn status(&self) -> Report {
        self.engine().status(
            CheckMode::Quick,
            &ItemId::ALL,
            &mut |_| {},
            &Cancellation::default(),
        )
    }

    /// The full check of `items`.
    fn verify(&self, items: &[ItemId]) -> Report {
        self.engine()
            .verify(items, &mut |_| {}, &Cancellation::default())
    }

    /// One setup of `request` on a new engine, `review` answering the person's review.
    fn run_setup(
        &self,
        request: &SetupRequest,
        review: &mut dyn FnMut(&SetupPlan) -> Answer,
        observe: &mut dyn FnMut(&Event),
        cancellation: &Cancellation,
    ) -> Run {
        let mut events = Vec::new();
        let report = self.engine().setup(
            request,
            review,
            &mut |event| {
                observe(&event);
                events.push(event);
            },
            cancellation,
        );
        Run { report, events }
    }

    /// The plan a setup of `items` asks the person to approve; the person declines it.
    fn plan(&self, items: Option<Vec<ItemId>>) -> Report {
        let request = SetupRequest {
            items,
            approved: None,
        };
        self.run_setup(
            &request,
            &mut |_| Answer::Decline,
            &mut |_| {},
            &Cancellation::default(),
        )
        .report
    }

    /// A setup of every item the person already approved under `digest`.
    fn setup_under(&self, digest: &Sha256Digest) -> Run {
        let request = SetupRequest {
            items: None,
            approved: Some(digest.clone()),
        };
        self.run_setup(
            &request,
            &mut |_| Answer::Decline,
            &mut |_| {},
            &Cancellation::default(),
        )
    }

    /// A setup of the local AI the person approves as reviewed, whose server the manager
    /// starts, under the proxy setting whose digest is `proxy`, once the program waits
    /// for it.
    fn set_up_local_ai_serving(&self, proxy: Option<&str>) -> Run {
        let request = SetupRequest {
            items: Some(vec![ItemId::LocalAi]),
            approved: None,
        };
        self.run_setup(
            &request,
            &mut |plan| Answer::Approve(plan.digest()),
            &mut |event| {
                if matches!(event, Event::WaitingForServer { .. }) {
                    self.serve_local_ai_under(proxy);
                }
            },
            &Cancellation::default(),
        )
    }

    /// Holds the next unranged archive answer halfway until the gate is dropped.
    fn gate(&self) -> Gate {
        let gate = Arc::new(Released::default());
        self.gates.lock().unwrap().push_back(gate.clone());
        Gate(gate)
    }

    /// Plays the manager starting its server: records the test's server as the running
    /// one, as the supervisor does once it answers.
    fn serve_local_ai(&self) {
        self.serve_local_ai_under(None);
    }

    /// The same, for a server the supervisor started under the proxy setting whose
    /// digest is `proxy`.
    fn serve_local_ai_under(&self, proxy: Option<&str>) {
        let ollama = self.ollama.as_ref().unwrap();
        let record = ServerRecord {
            schema: SERVER_RECORD_SCHEMA,
            address: ollama.address().to_string(),
            version: PROGRAM_VERSION.into(),
            executable: self.programs().join(EXECUTABLE),
            models: self.models(),
            process_id: std::process::id(),
            proxy: proxy.map(str::to_owned),
        };
        fs::write(
            self.programs().join(SERVER_RECORD),
            serde_json::to_vec(&record).unwrap(),
        )
        .unwrap();
    }

    /// Plays the manager stopping its server.
    fn stop_local_ai(&self) {
        fs::remove_file(self.programs().join(SERVER_RECORD)).unwrap();
    }

    /// Every request line the stand-in local AI server was sent.
    fn ollama_requests(&self) -> Vec<String> {
        self.ollama
            .as_ref()
            .unwrap()
            .state
            .lock()
            .unwrap()
            .requests
            .clone()
    }

    fn archive_requests(&self) -> usize {
        self.server
            .targets()
            .iter()
            .filter(|target| target.as_str() != "/")
            .count()
    }
}

fn row(report: &Report, item: ItemId) -> &StatusRow {
    report
        .rows
        .iter()
        .find(|row| row.item == item)
        .expect("every item has a row")
}

fn phases(events: &[Event], item: ItemId) -> Vec<SetupStep> {
    events
        .iter()
        .filter_map(|event| match event {
            Event::Phase { item: of, step } if *of == item => Some(*step),
            _ => None,
        })
        .collect()
}

fn last_progress(events: &[Event]) -> (u64, u64) {
    let progress: Vec<(u64, u64)> = events
        .iter()
        .filter_map(|event| match event {
            Event::Progress {
                completed, total, ..
            } => Some((*completed, *total)),
            _ => None,
        })
        .collect();
    assert!(
        progress.windows(2).all(|pair| pair[0].0 <= pair[1].0),
        "{progress:?}"
    );
    *progress.last().expect("progress was reported")
}

fn parts(plan: &SetupPlan) -> Vec<&str> {
    plan.entries[0]
        .parts
        .iter()
        .map(|part| part.part_id.as_str())
        .collect()
}

#[test]
fn builds_already_in_place_are_adopted_by_an_approved_setup_that_downloads_nothing() {
    let world = World::browser();
    let digest = world.plan(None).plan_digest().unwrap();
    let installed = world.setup_under(&digest);
    assert_eq!(installed.report.outcome, Outcome::Completed);
    // The builds stay and only their record is gone, as an earlier installer leaves them.
    let record = world.receipt("browser.json");
    fs::remove_file(&record).unwrap();

    let status = world.status();
    let browser = row(&status, ItemId::Browser);
    assert_eq!(
        browser.state,
        ItemState::Unknown,
        "builds no record describes are not believed"
    );
    assert_eq!(browser.recovery, Some(RecoveryAction::CheckAgain));
    assert_eq!(
        browser.size_estimate_bytes, None,
        "a check states no download: {browser:?}"
    );
    let plan = world.plan(None);
    assert_eq!(
        plan.plan.as_ref().unwrap().entries[0].download_bytes,
        Some(0)
    );
    let digest = plan.plan_digest().unwrap();

    let requests = world.server.targets().len();
    let adopted = world.setup_under(&digest);
    assert_eq!(
        adopted.report.outcome,
        Outcome::Completed,
        "{:?}",
        adopted.report
    );
    assert_eq!(
        world.server.targets().len(),
        requests,
        "adoption neither preflights nor downloads"
    );
    assert_eq!(
        phases(&adopted.events, ItemId::Browser),
        [SetupStep::Plan, SetupStep::Verify, SetupStep::Cleanup]
    );
    assert!(
        adopted
            .events
            .iter()
            .all(|event| !matches!(event, Event::Progress { .. }))
    );
    assert!(record.is_file(), "the passing check recorded the builds");
    assert_eq!(
        row(&adopted.report, ItemId::Browser).state,
        ItemState::Ready
    );
    assert_eq!(
        row(&world.status(), ItemId::Browser).state,
        ItemState::Ready
    );

    // A build the driver would not read as installed is fetched again, and only it.
    fs::remove_file(&record).unwrap();
    fs::remove_file(
        world
            .root()
            .join("components/playwright/chromium-1248")
            .join(browser::COMPLETION_MARKER),
    )
    .unwrap();
    let plan = world.plan(None);
    assert!(plan.plan.as_ref().unwrap().entries[0].download_bytes > Some(0));
    let digest = plan.plan_digest().unwrap();
    let archives = world.archive_requests();
    let repaired = world.setup_under(&digest);
    assert_eq!(
        repaired.report.outcome,
        Outcome::Completed,
        "{:?}",
        repaired.report
    );
    assert_eq!(world.archive_requests(), archives + 1);
    assert_eq!(
        row(&repaired.report, ItemId::Browser).state,
        ItemState::Ready
    );
}

#[test]
fn a_full_check_records_builds_an_earlier_installer_recorded_without_their_location() {
    let world = World::browser();
    let digest = world.plan(None).plan_digest().unwrap();
    let installed = world.setup_under(&digest);
    assert_eq!(installed.report.outcome, Outcome::Completed);
    // The earlier installer's record: the same files, its fractional time, no location.
    let record = world.receipt("browser.json");
    let mut earlier: Value = serde_json::from_slice(&fs::read(&record).unwrap()).unwrap();
    earlier.as_object_mut().unwrap().remove("location");
    earlier["verified_at"] = json!("2026-10-22T07:34:53.797382Z");
    fs::write(&record, serde_json::to_vec(&earlier).unwrap()).unwrap();

    let status = world.status();
    let browser = row(&status, ItemId::Browser);
    assert_eq!(
        (browser.state, browser.recovery),
        (ItemState::Unknown, Some(RecoveryAction::CheckAgain)),
        "a record that does not say where the builds are proves nothing: {browser:?}"
    );
    assert_eq!(browser.size_estimate_bytes, None, "{browser:?}");

    let archives = world.archive_requests();
    let verified = world.verify(&[ItemId::Browser]);
    assert_eq!(verified.outcome, Outcome::Ok, "{verified:?}");
    assert_eq!(row(&verified, ItemId::Browser).state, ItemState::Ready);
    assert_eq!(world.archive_requests(), archives, "nothing is downloaded");
    let current: Value = serde_json::from_slice(&fs::read(&record).unwrap()).unwrap();
    assert_eq!(
        current["location"]["root"].as_str().map(PathBuf::from),
        Some(world.root().join("components").join("playwright")),
        "the passing launch recorded where the builds are"
    );
    assert_eq!(
        row(&world.status(), ItemId::Browser).state,
        ItemState::Ready,
        "the quick check reads the current receipt"
    );
}

#[test]
fn a_cancel_stops_a_setup_at_its_next_chunk_from_its_owner_or_another_engine() {
    let world = World::browser();
    let digest = world.plan(None).plan_digest().unwrap();
    let request = SetupRequest {
        items: None,
        approved: Some(digest.clone()),
    };

    // The owner cancels the setup it runs once its first chunk arrived.
    let gate = world.gate();
    let cancellation = Cancellation::default();
    let cancelled = std::thread::scope(|scope| {
        let (progressed, progress) = mpsc::channel();
        let owner = scope.spawn(|| {
            world.run_setup(
                &request,
                &mut |_| Answer::Decline,
                &mut move |event| {
                    if matches!(event, Event::Progress { .. }) {
                        let _ = progressed.send(());
                    }
                },
                &cancellation,
            )
        });
        progress.recv().unwrap();
        cancellation.cancel();
        gate.open();
        owner.join().unwrap()
    });
    assert_eq!(cancelled.report.outcome, Outcome::Cancelled);
    assert_eq!(cancelled.report.item, Some(ItemId::Browser));
    assert_eq!(cancelled.report.failure, Some(FailureCategory::Cancelled));
    let browser = row(&cancelled.report, ItemId::Browser);
    assert_eq!(
        (browser.state, browser.recovery),
        (
            ItemState::Failed(FailureCategory::Cancelled),
            Some(RecoveryAction::TryAgain)
        )
    );
    assert!(
        world.engine().ask_to_stop(&ItemId::ALL).is_empty(),
        "no setup runs to be asked"
    );

    // Without the partial download the next setup asks for the first archive from its
    // start again, so the gate holds it there while another engine asks it to stop.
    fs::remove_dir_all(world.root().join("components/playwright/.cadrumo-staging")).unwrap();
    let gate = world.gate();
    let never = Cancellation::default();
    let cancelled = std::thread::scope(|scope| {
        let (progressed, progress) = mpsc::channel();
        let owner = scope.spawn(|| {
            world.run_setup(
                &request,
                &mut |_| Answer::Decline,
                &mut move |event| {
                    if matches!(event, Event::Progress { .. }) {
                        let _ = progressed.send(());
                    }
                },
                &never,
            )
        });
        progress.recv().unwrap();
        assert_eq!(world.engine().ask_to_stop(&ItemId::ALL), [ItemId::Browser]);
        assert_eq!(
            row(&world.status(), ItemId::Browser).state,
            ItemState::Provisioning
        );
        gate.open();
        owner.join().unwrap()
    });
    assert_eq!(cancelled.report.outcome, Outcome::Cancelled);
    assert_eq!(cancelled.report.failure, Some(FailureCategory::Cancelled));

    let resumed = world.setup_under(&digest);
    assert_eq!(
        resumed.report.outcome,
        Outcome::Completed,
        "a cancel request is withdrawn once its setup ends: {:?}",
        resumed.report
    );
    assert_eq!(
        row(&resumed.report, ItemId::Browser).state,
        ItemState::Ready
    );
}

#[test]
fn a_server_started_under_another_proxy_setting_is_never_pulled_through() {
    let text = StoredModel::new(1);
    let vision = StoredModel::new(9);
    let world = World::local_ai(&text, &vision);

    // The supervisor's server is recorded as started under a setting that is not this
    // engine's. Its environment is its own and this engine cannot change it, so the
    // refusal names the restart that can instead of asking for one.
    let done =
        world.set_up_local_ai_serving(Some(&Sha256Digest::of(b"another setting").to_string()));

    assert_eq!(
        (done.report.outcome, done.report.failure),
        (Outcome::Failed, Some(FailureCategory::ProgramProxyDiffers)),
        "{:?}",
        done.report
    );
    let requests = world.ollama_requests();
    assert!(
        !requests
            .iter()
            .any(|line| line.starts_with("POST /api/pull")),
        "no model is pulled through it: {requests:?}"
    );
}

#[test]
fn a_tag_the_registry_moved_is_the_model_the_program_verified() {
    let text = StoredModel::new(1);
    let vision = StoredModel::new(9);
    let world = World::local_ai(&text, &vision);
    // The registry answers with a manifest other than the one it served before, which is
    // what a moved tag looks like. The program verified what it pulled, and the engine
    // pins no digest, so the setup completes with it.
    let moved = StoredModel::new(5);
    {
        let mut state = world.ollama.as_ref().unwrap().state.lock().unwrap();
        state
            .installs
            .insert(VISION.into(), moved.files(&world.models(), VISION));
        state.tags.insert(VISION.into());
    }

    let done = world.set_up_local_ai_serving(None);

    assert_eq!(done.report.outcome, Outcome::Completed, "{:?}", done.report);
    assert_eq!(row(&done.report, ItemId::LocalAi).state, ItemState::Ready);
    let requests = world.ollama_requests();
    assert_eq!(
        requests
            .iter()
            .filter(|line| line.starts_with("POST /api/pull"))
            .count(),
        2,
        "each model is pulled once: {requests:?}"
    );
}

#[test]
fn the_local_ai_installs_its_program_pulls_each_model_once_and_checks_every_role() {
    let text = StoredModel::new(1);
    let vision = StoredModel::new(9);
    let kept = StoredModel::new(5);
    let mut world = World::local_ai(&text, &vision);
    let status = world.status();
    let local_ai = row(&status, ItemId::LocalAi);
    assert_eq!(local_ai.state, ItemState::Absent);
    assert_eq!(local_ai.version.as_deref(), Some(PROGRAM_VERSION));
    assert_eq!(
        row(&status, ItemId::Browser).state,
        ItemState::Blocked(BlockedReason::NotInThisBuild)
    );

    let request = SetupRequest {
        items: Some(vec![ItemId::LocalAi]),
        approved: None,
    };
    let mut reviewed = None;
    let done = world.run_setup(
        &request,
        &mut |plan| {
            reviewed = Some(plan.clone());
            Answer::Approve(plan.digest())
        },
        &mut |event| {
            if let Event::WaitingForServer { item } = event {
                assert_eq!(*item, ItemId::LocalAi);
                // The program is in place and recorded; the manager starts the server only
                // now.
                let receipt: Value =
                    serde_json::from_slice(&fs::read(world.receipt("local_ai.json")).unwrap())
                        .unwrap();
                assert_eq!(
                    receipt["location"]["facts"]["address"],
                    world.ollama.as_ref().unwrap().address().to_string()
                );
                world.serve_local_ai();
            }
        },
        &Cancellation::default(),
    );
    let plan = reviewed.expect("the setup asked for a review");
    assert_eq!(
        parts(&plan),
        [
            "program",
            "column_role_mapping",
            "supply_nature_proposal",
            "text_extraction",
            "vision_transcription"
        ]
    );
    let document = plan.digest_document();
    assert_eq!(document["contract_version"], 3);
    let keys = |value: &Value| {
        let mut keys: Vec<String> = value.as_object().unwrap().keys().cloned().collect();
        keys.sort_unstable();
        keys
    };
    assert_eq!(
        keys(&document["entries"][0]),
        [
            "destination",
            "download_bytes",
            "installs_outside_program",
            "item_id",
            "parts",
            "source_hosts",
            "target_version"
        ],
        "a plan entry carries no licence or fit notice"
    );
    for part in document["entries"][0]["parts"].as_array().unwrap() {
        assert_eq!(
            keys(part),
            [
                "destination",
                "download_bytes",
                "installs_outside_program",
                "part_id",
                "source_hosts",
                "target_version"
            ],
            "a plan part carries no licence or fit notice"
        );
    }
    assert_eq!(
        plan.entries[0].parts[1..]
            .iter()
            .map(|part| part.target_version.as_deref().unwrap())
            .collect::<Vec<_>>(),
        [TEXT, TEXT, TEXT, VISION]
    );
    let total = plan.entries[0].download_bytes.unwrap();
    assert_eq!(
        total,
        program_archive().len() as u64 + text.size() + vision.size(),
        "roles that share a model count its download once"
    );

    assert_eq!(done.report.outcome, Outcome::Completed, "{:?}", done.report);
    assert_eq!(
        phases(&done.events, ItemId::LocalAi),
        [
            SetupStep::Plan,
            SetupStep::Preflight,
            SetupStep::Download,
            SetupStep::Install,
            SetupStep::Download,
            SetupStep::Verify,
            SetupStep::Cleanup
        ]
    );
    assert_eq!(last_progress(&done.events), (total, total));
    assert_eq!(row(&done.report, ItemId::LocalAi).state, ItemState::Ready);
    let requests = world.ollama_requests();
    let count = |prefix: &str| {
        requests
            .iter()
            .filter(|line| line.starts_with(prefix))
            .count()
    };
    assert_eq!(count("POST /api/pull"), 2, "{requests:?}");
    assert_eq!(count("POST /api/generate"), 4, "one token for each role");

    // The quick check of an installation that measures this computer itself. How long
    // that takes depends on the machine, so only what it does and does not do is
    // asserted: it answers from the receipts, and loads and asks for nothing.
    world.measure_hardware = true;
    assert_eq!(
        row(&world.status(), ItemId::LocalAi).state,
        ItemState::Ready
    );
    assert_eq!(
        world.ollama_requests().len(),
        requests.len(),
        "a quick check loads no model and asks the server nothing"
    );
    assert_eq!(world.archive_requests(), 1, "nor does it reach the network");
    world.measure_hardware = false;

    let verified = world.verify(&[ItemId::LocalAi]);
    assert_eq!(row(&verified, ItemId::LocalAi).state, ItemState::Ready);
    world.stop_local_ai();
    let stopped = world.verify(&[ItemId::LocalAi]);
    assert_eq!(
        row(&stopped, ItemId::LocalAi).state,
        ItemState::Failed(FailureCategory::ProgramNotRunning),
        "without the manager's server the full check cannot pass"
    );

    // A model the person keeps beside the selected ones stays with its layers.
    kept.store(&world.models(), KEPT);
    let mut engine = world.engine();
    assert_eq!(
        engine
            .activity
            .ended(ItemId::LocalAi)
            .map(|ended| ended.outcome),
        Some(EndedOutcome::Completed)
    );
    let mut removing = Vec::new();
    let removed = engine.remove(&[ItemId::LocalAi], &mut |event| removing.push(event));
    assert_eq!(removed.outcome, Outcome::Removed, "{removed:?}");
    assert_eq!(removed.items, [ItemId::LocalAi]);
    assert_eq!(row(&removed, ItemId::LocalAi).state, ItemState::Absent);
    assert!(!world.receipt("local_ai.json").exists());
    assert_eq!(engine.activity.ended(ItemId::LocalAi), None);
    assert_eq!(engine.activity.last_failure(ItemId::LocalAi), None);
    assert!(phases(&removing, ItemId::LocalAi).contains(&SetupStep::Cleanup));
    assert_eq!(text.stored(&world.models(), TEXT), 0);
    assert_eq!(vision.stored(&world.models(), VISION), 0);
    assert_eq!(
        kept.stored(&world.models(), KEPT),
        3,
        "the kept model stays"
    );
}

#[test]
fn removing_the_program_alone_keeps_every_model_and_records_the_removal() {
    let text = StoredModel::new(1);
    let vision = StoredModel::new(9);
    let world = World::local_ai(&text, &vision);
    let installed = world.set_up_local_ai_serving(None);
    assert_eq!(installed.report.outcome, Outcome::Completed);
    world.stop_local_ai();
    let mut engine = world.engine();
    assert_eq!(
        engine
            .activity
            .ended(ItemId::LocalAi)
            .map(|ended| ended.outcome),
        Some(EndedOutcome::Completed)
    );

    let mut removing = Vec::new();
    let removed = engine.remove_program(&mut |event| removing.push(event));
    assert_eq!(removed.outcome, Outcome::Removed, "{removed:?}");
    assert_eq!(removed.items, [ItemId::LocalAi]);
    assert_eq!(row(&removed, ItemId::LocalAi).state, ItemState::Absent);
    assert!(!world.receipt("local_ai.json").exists());
    assert_eq!(engine.activity.ended(ItemId::LocalAi), None);
    assert_eq!(engine.activity.last_failure(ItemId::LocalAi), None);
    assert!(phases(&removing, ItemId::LocalAi).contains(&SetupStep::Cleanup));
    assert_eq!(text.stored(&world.models(), TEXT), 3, "the models stay");
    assert_eq!(vision.stored(&world.models(), VISION), 3);
    assert_eq!(
        parts(&world.plan(Some(vec![ItemId::LocalAi])).plan.unwrap()),
        ["program"],
        "a setup after the removal installs the program alone"
    );
}

#[test]
fn a_local_ai_a_setup_holds_is_not_removed() {
    let text = StoredModel::new(1);
    let vision = StoredModel::new(9);
    let world = World::local_ai(&text, &vision);
    text.store(&world.models(), TEXT);
    fs::create_dir_all(world.receipt("local_ai.json").parent().unwrap()).unwrap();
    fs::write(world.receipt("local_ai.json"), b"{}").unwrap();
    let holder = world.engine();
    let setup = holder
        .activity
        .begin(ItemId::LocalAi, SetupStep::Download)
        .unwrap();

    let mut engine = world.engine();
    let program = engine.remove_program(&mut |_| {});
    let whole = engine.remove(&[ItemId::LocalAi], &mut |_| {});

    for refused in [&program, &whole] {
        assert_eq!(refused.outcome, Outcome::Busy, "{refused:?}");
        assert_eq!(refused.item, Some(ItemId::LocalAi));
        assert!(refused.items.is_empty());
        assert_eq!(row(refused, ItemId::LocalAi).state, ItemState::Provisioning);
    }
    assert!(world.receipt("local_ai.json").is_file());
    assert_eq!(text.stored(&world.models(), TEXT), 3);
    drop(setup);
}

#[test]
fn the_hardware_floor_is_the_selected_models_size_and_no_selection_is_never_held_back() {
    let text = StoredModel::new(1);
    let vision = StoredModel::new(9);
    let mut world = World::local_ai(&text, &vision);
    world.memory_bytes = GIB;
    let fits = world.status();
    assert_eq!(
        row(&fits, ItemId::LocalAi).state,
        ItemState::Absent,
        "models of a few hundred bytes fit in any memory"
    );

    world.selection[0].2 = GIB + 1;
    let held = world.status();
    assert_eq!(
        row(&held, ItemId::LocalAi).state,
        ItemState::Blocked(BlockedReason::Hardware)
    );
    let refused = world.plan(Some(vec![ItemId::LocalAi]));
    assert_eq!(
        (refused.outcome, refused.failure),
        (Outcome::Refused, Some(FailureCategory::NotEnoughMemory)),
        "{refused:?}"
    );
    world.memory_bytes = 64 * GIB;
    assert_eq!(
        row(&world.status(), ItemId::LocalAi).state,
        ItemState::Absent
    );

    world.memory_bytes = GIB;
    world.selection.clear();
    let alone = world.plan(Some(vec![ItemId::LocalAi]));
    assert_eq!(alone.outcome, Outcome::NeedsApproval, "{alone:?}");
    assert_eq!(
        parts(alone.plan.as_ref().unwrap()),
        ["program"],
        "no selection plans the program alone"
    );
    assert!(
        world.ollama_requests().is_empty(),
        "planning asks the server nothing"
    );
}

#[test]
fn the_plan_digest_binds_every_selected_role_name_and_size() {
    let text = StoredModel::new(1);
    let vision = StoredModel::new(9);
    let mut world = World::local_ai(&text, &vision);
    let mut digest_of = |selection: &[(&str, &str, u64)]| {
        world.selection = selection
            .iter()
            .map(|(role, name, size)| ((*role).to_owned(), (*name).to_owned(), *size))
            .collect();
        let planned = world.plan(Some(vec![ItemId::LocalAi]));
        assert_eq!(planned.outcome, Outcome::NeedsApproval, "{planned:?}");
        planned.plan_digest().unwrap()
    };
    let selection = [
        ("text_extraction", TEXT, 5),
        ("vision_transcription", VISION, 7),
    ];
    let digest = digest_of(&selection);
    assert_eq!(
        digest_of(&[selection[1], selection[0]]),
        digest,
        "the order the desktop selects them in is not part of the plan"
    );
    for changed in [
        [("text_extraction", "synthetic-text:other", 5), selection[1]],
        [("text_extraction", TEXT, 6), selection[1]],
        [("column_role_mapping", TEXT, 5), selection[1]],
    ] {
        assert_ne!(digest_of(&changed), digest, "{changed:?}");
    }
    assert_ne!(digest_of(&selection[..1]), digest);
    let program_only = digest_of(&[]);
    assert_ne!(program_only, digest, "no selection plans the program alone");
}
