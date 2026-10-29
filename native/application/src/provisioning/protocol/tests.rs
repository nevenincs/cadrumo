//! The role's protocol driven end to end: each test starts this test binary as the
//! `components` role, with its real protocol over pipes, against real local servers.
//!
//! The child runs [`role_child`], which builds the engine from a configuration file the
//! test writes: the storage root, the pins and driver the test made, a network that
//! trusts the test's certificate and reaches its server, and the stand-in browser and
//! local AI server the tests already use. Everything after that is the production code
//! path: the command line, the engine and every line the role writes and reads.

use super::*;
use crate::provisioning::{
    browser::{
        self, DriverManifest,
        tests::{
            Archives, BROWSER_VERSION, HOST, driver_package, fake_environment, fake_leading,
            launchable_archives,
        },
    },
    engine::{EngineConfig, Outcome},
    items::Locations,
    local_ai::{
        fake_ollama::FakeOllama,
        hardware::Hardware,
        models::{LocalModels, ModelName, SelectedModel},
        program::{SERVER_RECORD, SERVER_RECORD_SCHEMA, ServerRecord},
    },
    pins::{ComponentPins, Platform},
    proxy::{PROXY_URL, ProxySettings},
    test_servers::{
        Released, Reply, Request, TestCertificate, TlsServer, network_nowhere, network_to, response,
    },
    transfer::RetryPolicy,
};
use rustls::{RootCertStore, pki_types::CertificateDer};
use serde::Serialize;
use std::{
    collections::{BTreeMap, VecDeque},
    fs,
    io::Cursor,
    net::SocketAddr,
    path::{Path, PathBuf},
    process::{Child, ChildStdin, Command as Process, Stdio},
    sync::atomic::{AtomicUsize, Ordering},
};

const CHILD: &str = "provisioning::protocol::tests::role_child";
const CHILD_CONFIG: &str = "CADRUMO_TEST_COMPONENTS_ROLE";
const GIB: u64 = 1024 * 1024 * 1024;
/// Obviously synthetic names: the engine knows no model, so its tests name none.
const TEXT: &str = "synthetic-text:test";
const VISION: &str = "synthetic-vision:test";
const PROGRAM_VERSION: &str = "9.9.9";
const PROGRAM_PATH: &str = "/ollama/ollama/releases/download/v9.9.9/ollama.zip";
const EXECUTABLE: &str = if cfg!(windows) {
    "ollama.exe"
} else {
    "bin/ollama"
};

/// What one role child is built from.
#[derive(Clone, Deserialize, Serialize)]
struct ChildConfig {
    root: PathBuf,
    pins: PathBuf,
    driver: Option<PathBuf>,
    certificate: Vec<u8>,
    /// The test's server every name resolves to; `None` resolves no name at all.
    address: Option<SocketAddr>,
    /// The fixed address of the local AI server, which the test answers for itself.
    local_ai_address: SocketAddr,
    free_bytes: Option<u64>,
    /// Measure this computer as the production role does, instead of a fixture.
    measure_hardware: bool,
    /// The fixture computer's memory, with no NVIDIA card.
    memory_bytes: u64,
    /// The local models the child's engine is admitted to provision, as role, name and
    /// size: `Some` plays the desktop's engine, `None` the role as it ships.
    admitted: Option<Vec<(String, String, u64)>>,
    arguments: Vec<String>,
}

fn child_engine(config: &ChildConfig) -> Result<Engine, Error> {
    let mut roots = RootCertStore::empty();
    roots
        .add(CertificateDer::from(config.certificate.clone()))
        .map_err(|_| Error::Invalid("test certificate".into()))?;
    let network = match config.address {
        Some(address) => network_to(roots, address, None),
        None => network_nowhere(roots),
    };
    let mut browser_environment = fake_environment(&format!("version={BROWSER_VERSION}"));
    browser_environment.remove(OsStr::new(CHILD_CONFIG));
    let free_bytes = config.free_bytes;
    let mut engine = Engine::new(EngineConfig {
        storage_root: config.root.clone(),
        locations: Locations::under(&config.root),
        pins: ComponentPins::load(&config.pins)?,
        driver: config
            .driver
            .as_deref()
            .map(DriverManifest::read)
            .transpose()?,
        platform: Platform::current(),
        network,
        ambient: Box::new(|name| std::env::var_os(name)),
        local_ai_address: config.local_ai_address,
        browser_environment,
        scratch: config.root.join("tmp"),
        free_space: Box::new(move |_| free_bytes),
        hardware: (!config.measure_hardware).then_some(Hardware {
            total_memory_bytes: Some(config.memory_bytes),
            nvidia_vram_bytes: None,
        }),
        policy: RetryPolicy::default(),
    })?;
    engine.browser_leading = fake_leading();
    if let Some(admitted) = &config.admitted {
        let models = admitted
            .iter()
            .map(|(role, name, size)| SelectedModel::new(role, name, Some(*size)))
            .collect::<Result<_, _>>()?;
        engine.admit_local_ai(LocalModels::new(models)?);
    }
    Ok(engine)
}

/// Plays the `components` role for a test in another process: serves the protocol on
/// this process's own standard input and output, then exits with the role's status. Does
/// nothing unless started as that role.
#[test]
fn role_child() {
    let Some(path) = std::env::var_os(CHILD_CONFIG) else {
        return;
    };
    let config: ChildConfig = serde_json::from_slice(&fs::read(path).unwrap()).unwrap();
    let arguments: Vec<OsString> = config.arguments.iter().map(OsString::from).collect();
    let code = serve(&arguments, std::io::stdin(), std::io::stdout(), || {
        child_engine(&config)
    });
    std::process::exit(code);
}

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

/// Everything one test's roles share: the folders, the pins, the publisher's server.
struct World {
    directory: tempfile::TempDir,
    certificate: TestCertificate,
    gates: Arc<Mutex<VecDeque<Arc<Released>>>>,
    server: TlsServer,
    ollama: Option<FakeOllama>,
    driver: bool,
    /// The local models the desktop admits its engine to provision; `None` runs the role
    /// as it ships, read-only for the local AI.
    admitted: Option<Vec<(String, String, u64)>>,
    spawned: AtomicUsize,
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

impl World {
    /// A world whose build carries the browser driver and its pinned archives.
    fn browser() -> Self {
        let directory = tempfile::tempdir().unwrap();
        driver_package(&directory.path().join("driver"));
        let Archives { table, served } = launchable_archives("role");
        fs::create_dir_all(directory.path().join("pins")).unwrap();
        fs::write(directory.path().join("pins/browser_archives.toml"), table).unwrap();
        Self::serving(directory, served, true, None)
    }

    /// A world whose build carries only the local AI, its server played by the test.
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
        world.admitted = Some(
            [
                ("vision_transcription", VISION, vision.size()),
                ("text_extraction", TEXT, text.size()),
                ("column_role_mapping", TEXT, text.size()),
                ("supply_nature_proposal", TEXT, text.size()),
            ]
            .into_iter()
            .map(|(role, name, size)| (role.to_owned(), name.to_owned(), size))
            .collect(),
        );
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
            admitted: None,
            spawned: AtomicUsize::new(0),
        }
    }

    fn root(&self) -> PathBuf {
        self.directory.path().join("storage")
    }

    fn config(&self, arguments: &[&str]) -> ChildConfig {
        let arguments = arguments.iter().map(|word| (*word).to_owned()).collect();
        ChildConfig {
            root: self.root(),
            pins: self.directory.path().join("pins"),
            driver: self.driver.then(|| self.directory.path().join("driver")),
            certificate: self.certificate.der.clone(),
            address: Some(self.server.address()),
            local_ai_address: self
                .ollama
                .as_ref()
                .map_or_else(|| "127.0.0.1:23743".parse().unwrap(), FakeOllama::address),
            free_bytes: Some(1024 * GIB),
            measure_hardware: false,
            memory_bytes: 64 * GIB,
            admitted: self.admitted.clone(),
            arguments,
        }
    }

    /// Holds the next unranged archive answer halfway until the gate is dropped.
    fn gate(&self) -> Gate {
        let gate = Arc::new(Released::default());
        self.gates.lock().unwrap().push_back(gate.clone());
        Gate(gate)
    }

    fn programs(&self) -> PathBuf {
        self.root().join("components/ollama")
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
            models: self.root().join("models/ollama"),
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

    fn archive_requests(&self) -> usize {
        self.server
            .targets()
            .iter()
            .filter(|target| target.as_str() != "/")
            .count()
    }

    fn start(&self, arguments: &[&str]) -> Role {
        self.start_with(&self.config(arguments))
    }

    fn start_with(&self, config: &ChildConfig) -> Role {
        let number = self.spawned.fetch_add(1, Ordering::Relaxed);
        let path = self.directory.path().join(format!("role-{number}.json"));
        fs::write(&path, serde_json::to_vec(config).unwrap()).unwrap();
        Role::start(&path)
    }

    /// Runs one command to its result, keeping its input open until then.
    fn run(&self, arguments: &[&str]) -> Finished {
        self.start(arguments).finish()
    }
}

/// One running role child, its lines arriving in order.
struct Role {
    child: Child,
    input: Option<ChildStdin>,
    lines: mpsc::Receiver<Value>,
}

/// A role child's lines after `started`, its result, and its exit status.
struct Finished {
    events: Vec<Value>,
    result: Value,
    code: i32,
}

impl Role {
    fn start(config: &Path) -> Self {
        let mut process = Process::new(std::env::current_exe().unwrap());
        process
            .args(["--exact", CHILD, "--nocapture", "--test-threads=1", "-q"])
            .env(CHILD_CONFIG, config)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            process.creation_flags(CREATE_NO_WINDOW);
        }
        let mut child = process.spawn().unwrap();
        let output = child.stdout.take().unwrap();
        let (sender, lines) = mpsc::channel();
        std::thread::spawn(move || {
            let mut started = false;
            for line in BufReader::new(output).lines() {
                let Ok(line) = line else { break };
                match serde_json::from_str::<Value>(&line) {
                    Ok(value) if started || value["type"] == "started" => {
                        started = true;
                        if sender.send(value).is_err() {
                            break;
                        }
                    }
                    // The test harness's own lines before the role starts.
                    _ if !started => {}
                    _ => {
                        let _ = sender.send(Value::String(line));
                    }
                }
            }
        });
        let role = Self {
            input: child.stdin.take(),
            child,
            lines,
        };
        let started = role.next();
        assert_eq!(started["type"], "started", "{started}");
        assert_eq!(started["protocol"], PROTOCOL_VERSION);
        role
    }

    fn next(&self) -> Value {
        self.lines
            .recv()
            .expect("the role ended before its result line")
    }

    /// Reads lines until one of `kind`, returning those before it and it.
    fn until(&self, kind: &str) -> (Vec<Value>, Value) {
        let mut seen = Vec::new();
        loop {
            let line = self.next();
            assert_locale_neutral(&line);
            if line["type"] == kind {
                return (seen, line);
            }
            assert_ne!(line["type"], "result", "{line} before a {kind}");
            seen.push(line);
        }
    }

    fn send(&mut self, line: Value) {
        let input = self.input.as_mut().unwrap();
        writeln!(input, "{line}").unwrap();
        input.flush().unwrap();
    }

    fn finish(mut self) -> Finished {
        let (events, result) = self.until("result");
        drop(self.input.take());
        let code = self.child.wait().unwrap().code().unwrap();
        assert!(
            self.lines.recv().is_err(),
            "nothing follows the result line"
        );
        Finished {
            events,
            result,
            code,
        }
    }

    fn kill(mut self) {
        self.child.kill().unwrap();
        self.child.wait().unwrap();
    }
}

/// No line carries words: every string is a code, an id, a version, a host, a path or
/// a digest, none of which holds a space.
fn assert_locale_neutral(value: &Value) {
    match value {
        Value::String(text) => assert!(!text.contains(char::is_whitespace), "{text:?}"),
        Value::Array(values) => values.iter().for_each(assert_locale_neutral),
        Value::Object(map) => map.values().for_each(assert_locale_neutral),
        _ => {}
    }
}

fn row<'a>(result: &'a Value, item: &str) -> &'a Value {
    result["rows"]
        .as_array()
        .unwrap()
        .iter()
        .find(|row| row["item_id"] == item)
        .unwrap()
}

fn phases(events: &[Value], item: &str) -> Vec<String> {
    events
        .iter()
        .filter(|event| event["type"] == "phase" && event["item_id"] == item)
        .map(|event| event["step"].as_str().unwrap().to_owned())
        .collect()
}

fn last_progress(events: &[Value]) -> (u64, u64) {
    let progress: Vec<(u64, u64)> = events
        .iter()
        .filter(|event| event["type"] == "progress")
        .map(|event| {
            (
                event["completed"].as_u64().unwrap(),
                event["total"].as_u64().unwrap(),
            )
        })
        .collect();
    assert!(
        progress.windows(2).all(|pair| pair[0].0 <= pair[1].0),
        "{progress:?}"
    );
    *progress.last().expect("progress was reported")
}

#[test]
fn a_setup_runs_only_under_the_plan_digest_the_person_approved() {
    let world = World::browser();
    let status = world.run(&["status"]);
    assert_eq!(status.code, 0);
    assert_eq!(status.result["outcome"], "ok");
    assert_eq!(status.result["setup_complete"], false);
    let browser = row(&status.result, "browser");
    assert_eq!(browser["state"], "absent");
    assert_eq!(browser["recovery"], "set_up");
    assert_eq!(browser["recovery_action_id"], "operator.provision.browser");
    let local_ai = row(&status.result, "local_ai");
    assert_eq!(local_ai["state"], "blocked");
    assert_eq!(local_ai["blocked_reason"], "not_in_this_build");

    let plan = world.run(&["plan"]);
    let digest = plan.result["plan_digest"].as_str().unwrap().to_owned();
    let entries = plan.result["plan"]["entries"].as_array().unwrap();
    assert_eq!(
        entries.len(),
        1,
        "a build without the local AI plans the browser alone"
    );
    assert_eq!(entries[0]["item_id"], "browser");
    assert_eq!(
        Some(entries[0]["download_bytes"].as_u64().unwrap()),
        browser["size_estimate_bytes"].as_u64()
    );
    assert_eq!(plan.result["plan"]["space"]["sufficient"], true);

    let other = Sha256Digest::of(b"another plan").to_string();
    let changed = world.run(&["setup", "--approve", &other]);
    assert_eq!(changed.code, 1);
    assert_eq!(changed.result["outcome"], "plan_changed");
    assert_eq!(changed.result["plan_digest"], digest.as_str());
    assert!(changed.events.iter().all(|event| event["type"] != "review"));

    let mut asked = world.start(&["setup"]);
    let (_, review) = asked.until("review");
    assert_eq!(review["plan_digest"], digest.as_str());
    asked.send(json!({"type": "approve", "plan_digest": other}));
    assert_eq!(asked.finish().result["outcome"], "plan_changed");

    let mut declined = world.start(&["setup"]);
    declined.until("review");
    declined.send(json!({"type": "decline"}));
    let declined = declined.finish();
    assert_eq!(declined.result["outcome"], "needs_approval");
    assert_eq!(declined.code, 1);
    assert_eq!(
        world.archive_requests(),
        0,
        "nothing downloads without approval"
    );

    let mut approved = world.start(&["setup"]);
    let (reviewed, _) = approved.until("review");
    approved.send(json!({"type": "approve", "plan_digest": digest}));
    let mut approved = approved.finish();
    approved.events = [reviewed, approved.events].concat();
    assert_eq!(
        approved.result["outcome"], "completed",
        "{}",
        approved.result
    );
    assert_eq!(approved.code, 0);
    assert_eq!(
        phases(&approved.events, "browser"),
        ["plan", "preflight", "download", "install"]
            .into_iter()
            .chain(std::iter::repeat_n(["download", "install"], builds() - 1).flatten())
            .chain(["verify", "cleanup"])
            .collect::<Vec<_>>()
    );
    let phase = approved
        .events
        .iter()
        .find(|event| event["type"] == "phase")
        .unwrap();
    assert_eq!(phase["phase_code"], "dependencies.setup.browser.plan");
    let (completed, total) = last_progress(&approved.events);
    assert_eq!(completed, total);
    assert_eq!(Some(total), entries[0]["download_bytes"].as_u64());
    assert_eq!(row(&approved.result, "browser")["state"], "ready");

    let requests = world.server.targets().len();
    let quick = world.run(&["status"]);
    assert_eq!(
        world.server.targets().len(),
        requests,
        "a quick check reads no network"
    );
    assert_eq!(row(&quick.result, "browser")["state"], "ready");
    assert_eq!(row(&quick.result, "browser")["mode"], "quick");

    let again = world.run(&["setup"]);
    assert_eq!(again.result["outcome"], "nothing_to_do");
    assert_eq!(again.code, 0);
    assert!(again.events.is_empty(), "{:?}", again.events);

    let verified = world.run(&["verify", "--item", "browser"]);
    assert_eq!(verified.result["outcome"], "ok");
    assert_eq!(verified.result["mode"], "full");
    let browser = row(&verified.result, "browser");
    assert_eq!(
        (&browser["state"], &browser["mode"]),
        (&json!("ready"), &json!("full"))
    );
    assert_eq!(browser["version"], BROWSER_VERSION);

    let removed = world.run(&["remove", "--item", "browser"]);
    assert_eq!(removed.result["outcome"], "removed");
    assert_eq!(removed.result["items"], json!(["browser"]));
    assert_eq!(row(&removed.result, "browser")["state"], "absent");
    assert!(
        fs::read_dir(world.root().join("components/playwright"))
            .unwrap()
            .next()
            .is_none(),
        "every build is gone"
    );
    assert!(
        !world
            .root()
            .join("components/receipts/browser.json")
            .exists()
    );
}

#[test]
fn builds_already_in_place_are_adopted_by_an_approved_setup_that_downloads_nothing() {
    let world = World::browser();
    let digest = world.run(&["plan"]).result["plan_digest"]
        .as_str()
        .unwrap()
        .to_owned();
    let installed = world.run(&["setup", "--approve", &digest]);
    assert_eq!(installed.result["outcome"], "completed");
    // The builds stay and only their record is gone, as an earlier installer leaves them.
    let record = world.root().join("components/receipts/browser.json");
    fs::remove_file(&record).unwrap();

    let status = world.run(&["status"]);
    let browser = row(&status.result, "browser");
    assert_eq!(
        browser["state"], "unknown",
        "builds no record describes are not believed"
    );
    assert_eq!(browser["recovery"], "check_again");
    assert!(
        browser.get("size_estimate_bytes").is_none(),
        "a check states no download: {browser}"
    );
    let plan = world.run(&["plan"]);
    assert_eq!(plan.result["plan"]["entries"][0]["download_bytes"], 0);
    let digest = plan.result["plan_digest"].as_str().unwrap().to_owned();

    let requests = world.server.targets().len();
    let adopted = world.run(&["setup", "--approve", &digest]);
    assert_eq!(adopted.result["outcome"], "completed", "{}", adopted.result);
    assert_eq!(
        world.server.targets().len(),
        requests,
        "adoption neither preflights nor downloads"
    );
    assert_eq!(
        phases(&adopted.events, "browser"),
        ["plan", "verify", "cleanup"]
    );
    assert!(
        adopted
            .events
            .iter()
            .all(|event| event["type"] != "progress")
    );
    assert!(record.is_file(), "the passing check recorded the builds");
    assert_eq!(row(&adopted.result, "browser")["state"], "ready");
    assert_eq!(
        row(&world.run(&["status"]).result, "browser")["state"],
        "ready"
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
    let plan = world.run(&["plan"]);
    assert!(plan.result["plan"]["entries"][0]["download_bytes"].as_u64() > Some(0));
    let digest = plan.result["plan_digest"].as_str().unwrap().to_owned();
    let archives = world.archive_requests();
    let repaired = world.run(&["setup", "--approve", &digest]);
    assert_eq!(
        repaired.result["outcome"], "completed",
        "{}",
        repaired.result
    );
    assert_eq!(world.archive_requests(), archives + 1);
    assert_eq!(row(&repaired.result, "browser")["state"], "ready");
}

#[test]
fn a_full_check_records_builds_an_earlier_installer_recorded_without_their_location() {
    let world = World::browser();
    let digest = world.run(&["plan"]).result["plan_digest"]
        .as_str()
        .unwrap()
        .to_owned();
    let installed = world.run(&["setup", "--approve", &digest]);
    assert_eq!(installed.result["outcome"], "completed");
    // The earlier installer's record: the same files, its fractional time, no location.
    let record = world.root().join("components/receipts/browser.json");
    let mut earlier: Value = serde_json::from_slice(&fs::read(&record).unwrap()).unwrap();
    earlier.as_object_mut().unwrap().remove("location");
    earlier["verified_at"] = json!("2026-10-22T07:34:53.797382Z");
    fs::write(&record, serde_json::to_vec(&earlier).unwrap()).unwrap();

    let status = world.run(&["status"]);
    let browser = row(&status.result, "browser");
    assert_eq!(
        (&browser["state"], &browser["recovery"]),
        (&json!("unknown"), &json!("check_again")),
        "a record that does not say where the builds are proves nothing: {browser}"
    );
    assert!(browser.get("size_estimate_bytes").is_none(), "{browser}");

    let archives = world.archive_requests();
    let verified = world.run(&["verify", "--item", "browser"]);
    assert_eq!(verified.result["outcome"], "ok", "{}", verified.result);
    assert_eq!(row(&verified.result, "browser")["state"], "ready");
    assert_eq!(world.archive_requests(), archives, "nothing is downloaded");
    let current: Value = serde_json::from_slice(&fs::read(&record).unwrap()).unwrap();
    assert_eq!(
        current["location"]["root"].as_str().map(PathBuf::from),
        Some(world.root().join("components").join("playwright")),
        "the passing launch recorded where the builds are"
    );
    assert_eq!(
        row(&world.run(&["status"]).result, "browser")["state"],
        "ready",
        "the quick check reads the current receipt"
    );
}

/// How many builds the browser's plan installs, one archive each: the test pins' families.
fn builds() -> usize {
    if Platform::current() == Some(Platform::WinX64) {
        4
    } else {
        3
    }
}

#[test]
fn an_interrupted_setup_resumes_without_a_second_review_while_its_plan_is_unchanged() {
    let world = World::browser();
    let digest = world.run(&["plan"]).result["plan_digest"]
        .as_str()
        .unwrap()
        .to_owned();
    let gate = world.gate();
    let interrupted = world.start(&["setup", "--approve", &digest]);
    interrupted.until("progress");
    interrupted.kill();
    gate.open();

    let status = world.run(&["status"]);
    let browser = row(&status.result, "browser");
    assert_eq!(browser["state"], "failed");
    assert_eq!(browser["failure_category"], "interrupted");
    assert_eq!(browser["recovery"], "resume");
    assert_eq!(
        world.run(&["plan"]).result["plan_digest"],
        digest.as_str(),
        "the partial download changes nothing the person approved"
    );

    let resumed = world.run(&["setup", "--approve", &digest]);
    assert_eq!(resumed.result["outcome"], "completed", "{}", resumed.result);
    assert!(resumed.events.iter().all(|event| event["type"] != "review"));
    assert!(
        world
            .server
            .requests
            .lock()
            .unwrap()
            .iter()
            .any(|request| request.header("range").is_some()),
        "the resumed download asked only for the bytes it lacked"
    );
    assert_eq!(row(&resumed.result, "browser")["state"], "ready");
}

#[test]
fn a_cancel_stops_a_setup_at_its_next_chunk_from_its_client_or_another_process() {
    let world = World::browser();
    let digest = world.run(&["plan"]).result["plan_digest"]
        .as_str()
        .unwrap()
        .to_owned();

    let gate = world.gate();
    let mut setup = world.start(&["setup", "--approve", &digest]);
    setup.until("progress");
    setup.send(json!({"type": "cancel"}));
    let (_, notice) = setup.until("notice");
    assert_eq!(notice["notice_code"], "cancel_requested");
    gate.open();
    let cancelled = setup.finish();
    assert_eq!(cancelled.result["outcome"], "cancelled");
    assert_eq!(cancelled.result["item_id"], "browser");
    assert_eq!(cancelled.result["failure_category"], "cancelled");
    assert_eq!(cancelled.code, 1);
    let browser = row(&cancelled.result, "browser");
    assert_eq!(
        (
            &browser["state"],
            &browser["failure_category"],
            &browser["recovery"]
        ),
        (&json!("failed"), &json!("cancelled"), &json!("try_again"))
    );

    let nothing = world.run(&["cancel"]);
    assert_eq!(nothing.result["outcome"], "nothing_running");
    assert_eq!(nothing.result["items"], json!([]));

    // Without the partial download the next setup asks for the first archive from its
    // start again, so the gate holds it there while another process asks it to stop.
    fs::remove_dir_all(world.root().join("components/playwright/.cadrumo-staging")).unwrap();
    let gate = world.gate();
    let setup = world.start(&["setup", "--approve", &digest]);
    setup.until("progress");
    let asked = world.run(&["cancel"]);
    assert_eq!(asked.result["outcome"], "cancel_requested");
    assert_eq!(asked.result["items"], json!(["browser"]));
    assert_eq!(row(&asked.result, "browser")["state"], "provisioning");
    gate.open();
    let cancelled = setup.finish();
    assert_eq!(cancelled.result["outcome"], "cancelled");

    let resumed = world.run(&["setup", "--approve", &digest]);
    assert_eq!(
        resumed.result["outcome"], "completed",
        "a cancel request is withdrawn once its setup ends: {}",
        resumed.result
    );
}

/// A role that finds its item being set up by another role follows that setup: it waits
/// for the follow notice and the first byte figure it relays.
fn following(world: &World, arguments: &[&str], digest: &str) -> (Role, Vec<Value>) {
    let follower = world.start(arguments);
    let (before, notice) = follower.until("notice");
    assert_eq!(notice["notice_code"], "following", "{notice}");
    assert_eq!(notice["subject_code"], "browser");
    assert_eq!(notice["plan_digest"], digest);
    assert!(before.is_empty(), "a follower plans nothing: {before:?}");
    let (relayed, progress) = follower.until("progress");
    assert_eq!(progress["subject_code"], "browser");
    (follower, [vec![notice], relayed, vec![progress]].concat())
}

#[test]
fn a_second_setup_follows_the_running_one_to_its_result_with_no_review_or_download() {
    let world = World::browser();
    let plan = world.run(&["plan"]).result;
    let digest = plan["plan_digest"].as_str().unwrap().to_owned();
    let gate = world.gate();
    let owner = world.start(&["setup", "--approve", &digest]);
    owner.until("progress");

    // A follower that stops following ends busy and leaves the setup running.
    let (mut leaving, _) = following(&world, &["setup", "--item", "browser"], &digest);
    leaving.send(json!({"type": "cancel"}));
    let left = leaving.finish();
    assert_eq!(left.result["outcome"], "busy", "{}", left.result);
    assert_eq!(left.result["item_id"], "browser");
    assert_eq!(left.code, 1);
    assert_eq!(row(&left.result, "browser")["state"], "provisioning");

    // Without --approve it would ask for a review; following asks for none.
    let (follower, seen) = following(&world, &["setup"], &digest);
    gate.open();
    let owned = owner.finish();
    let followed = follower.finish();
    assert_eq!(owned.result["outcome"], "completed", "{}", owned.result);
    assert_eq!(
        followed.result["outcome"], "completed",
        "{}",
        followed.result
    );
    assert_eq!(followed.code, 0);
    let events = [seen, followed.events].concat();
    assert!(events.iter().all(|event| event["type"] != "review"));
    assert_eq!(
        phases(&events, "browser"),
        ["download", "install"]
            .into_iter()
            .chain(std::iter::repeat_n(["download", "install"], builds() - 1).flatten())
            .chain(["verify", "cleanup"])
            .collect::<Vec<_>>(),
        "every step the owner reached, in order"
    );
    let (completed, total) = last_progress(&events);
    assert_eq!(completed, total);
    assert_eq!(
        Some(total),
        plan["plan"]["entries"][0]["download_bytes"].as_u64()
    );
    assert_eq!(row(&followed.result, "browser")["state"], "ready");
    assert_eq!(
        world.archive_requests(),
        builds(),
        "each archive was fetched once, by the owner"
    );
    assert!(followed.result.get("plan").is_none());
}

#[test]
fn a_follower_reports_the_cancel_the_person_asked_for_and_a_setup_whose_process_died() {
    let world = World::browser();
    let digest = world.run(&["plan"]).result["plan_digest"]
        .as_str()
        .unwrap()
        .to_owned();
    let gate = world.gate();
    let owner = world.start(&["setup", "--approve", &digest]);
    owner.until("progress");
    let (follower, seen) = following(&world, &["setup", "--item", "browser"], &digest);
    let activity = world.root().join("components/activity");
    let observed = fs::read_to_string(activity.join("browser.activity.json"));
    let asked = world.run(&["cancel"]);
    assert_eq!(asked.result["outcome"], "cancel_requested");
    gate.open();
    let owned = owner.finish();
    assert_eq!(owned.result["outcome"], "cancelled");
    let followed = follower.finish();
    assert_eq!(
        (
            &followed.result["outcome"],
            &followed.result["item_id"],
            &followed.result["failure_category"]
        ),
        (&json!("cancelled"), &json!("browser"), &json!("cancelled")),
        "follower: {}; events before: {seen:?}; events after: {:?}; owner: {}; \
         initial activity: {observed:?}; final activity: {:?}; end: {:?}; failure: {:?}",
        followed.result,
        followed.events,
        owned.result,
        fs::read_to_string(activity.join("browser.activity.json")),
        fs::read_to_string(activity.join("browser.ended.json")),
        fs::read_to_string(activity.join("browser.failure.json")),
    );

    // The partial download would let the next setup resume past the gate.
    fs::remove_dir_all(world.root().join("components/playwright/.cadrumo-staging")).unwrap();
    let gate = world.gate();
    let owner = world.start(&["setup", "--approve", &digest]);
    owner.until("progress");
    let (follower, _) = following(&world, &["setup", "--item", "browser"], &digest);
    owner.kill();
    let followed = follower.finish();
    gate.open();
    assert_eq!(
        (
            &followed.result["outcome"],
            &followed.result["failure_category"]
        ),
        (&json!("failed"), &json!("interrupted")),
        "{}",
        followed.result
    );
    assert_eq!(row(&followed.result, "browser")["recovery"], "resume");
}

#[test]
fn a_server_started_under_another_proxy_setting_is_never_pulled_through() {
    let text = StoredModel::new(1);
    let vision = StoredModel::new(9);
    let world = World::local_ai(&text, &vision);

    let mut setup = world.start(&["setup", "--item", "local_ai"]);
    let (_reviewed, review) = setup.until("review");
    setup.send(json!({"type": "approve", "plan_digest": review["plan_digest"]}));
    setup.until("notice");
    // The supervisor's server is recorded as started under a setting that is not this
    // engine's. Its environment is its own and this engine cannot change it, so the
    // refusal names the restart that can instead of asking for one.
    world.serve_local_ai_under(Some(&Sha256Digest::of(b"another setting").to_string()));
    let done = setup.finish();

    assert_eq!(
        (&done.result["outcome"], &done.result["failure_category"]),
        (&json!("failed"), &json!("program_proxy_differs")),
        "{}",
        done.result
    );
    let requests = world
        .ollama
        .as_ref()
        .unwrap()
        .state
        .lock()
        .unwrap()
        .requests
        .clone();
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
        let ollama = world.ollama.as_ref().unwrap();
        let mut state = ollama.state.lock().unwrap();
        let models = world.root().join("models/ollama");
        state
            .installs
            .insert(VISION.into(), moved.files(&models, VISION));
        state.tags.insert(VISION.into());
    }

    let mut setup = world.start(&["setup", "--item", "local_ai"]);
    let (_reviewed, review) = setup.until("review");
    setup.send(json!({"type": "approve", "plan_digest": review["plan_digest"]}));
    setup.until("notice");
    world.serve_local_ai();
    let done = setup.finish();

    assert_eq!(done.result["outcome"], "completed", "{}", done.result);
    assert_eq!(row(&done.result, "local_ai")["state"], "ready");
    let requests = world
        .ollama
        .as_ref()
        .unwrap()
        .state
        .lock()
        .unwrap()
        .requests
        .clone();
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
fn an_offline_computer_and_a_full_disk_refuse_before_any_review_or_download() {
    let world = World::browser();
    let offline = world
        .start_with(&ChildConfig {
            address: None,
            ..world.config(&["setup"])
        })
        .finish();
    assert_eq!(offline.result["outcome"], "refused");
    assert_eq!(offline.result["item_id"], "browser");
    assert_eq!(offline.result["failure_category"], "offline");
    assert_eq!(phases(&offline.events, "browser"), ["plan", "preflight"]);

    let full = world
        .start_with(&ChildConfig {
            free_bytes: Some(1024),
            ..world.config(&["setup"])
        })
        .finish();
    assert_eq!(full.result["outcome"], "refused");
    assert_eq!(full.result["failure_category"], "disk_full");
    let space = &full.result["plan"]["space"];
    assert_eq!(space["free_bytes"], 1024);
    assert!(space["required_bytes"].as_u64().unwrap() > GIB);

    for result in [&offline, &full] {
        assert!(result.events.iter().all(|event| event["type"] != "review"));
        assert_eq!(row(&result.result, "browser")["state"], "absent");
    }
    assert_eq!(world.archive_requests(), 0);
}

#[test]
fn the_local_ai_installs_its_program_pulls_each_model_once_and_checks_every_role() {
    let text = StoredModel::new(1);
    let vision = StoredModel::new(9);
    let world = World::local_ai(&text, &vision);
    let status = world.run(&["status"]);
    let local_ai = row(&status.result, "local_ai");
    assert_eq!(local_ai["state"], "absent");
    assert_eq!(local_ai["version"], PROGRAM_VERSION);
    assert_eq!(
        row(&status.result, "browser")["blocked_reason"],
        "not_in_this_build"
    );

    let mut setup = world.start(&["setup", "--item", "local_ai"]);
    let (reviewed, review) = setup.until("review");
    let entry = &review["plan"]["entries"][0];
    assert_eq!(
        entry["parts"]
            .as_array()
            .unwrap()
            .iter()
            .map(|part| part["part_id"].as_str().unwrap())
            .collect::<Vec<_>>(),
        [
            "program",
            "column_role_mapping",
            "supply_nature_proposal",
            "text_extraction",
            "vision_transcription"
        ]
    );
    assert_eq!(review["plan"]["contract_version"], 3);
    let keys = |value: &Value| {
        let mut keys: Vec<String> = value.as_object().unwrap().keys().cloned().collect();
        keys.sort_unstable();
        keys
    };
    assert_eq!(
        keys(entry),
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
    let parts = entry["parts"].as_array().unwrap();
    for part in parts {
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
        parts[1..]
            .iter()
            .map(|part| part["target_version"].as_str().unwrap())
            .collect::<Vec<_>>(),
        [TEXT, TEXT, TEXT, VISION]
    );
    let total = entry["download_bytes"].as_u64().unwrap();
    assert_eq!(
        total,
        program_archive().len() as u64 + text.size() + vision.size(),
        "roles that share a model count its download once"
    );
    setup.send(json!({"type": "approve", "plan_digest": review["plan_digest"]}));
    // The program is in place and recorded; the manager starts the server only now.
    let (before, waiting) = setup.until("notice");
    assert_eq!(waiting["notice_code"], "waiting_for_server");
    assert_eq!(waiting["subject_code"], "local_ai");
    let receipt: Value = serde_json::from_slice(
        &fs::read(world.root().join("components/receipts/local_ai.json")).unwrap(),
    )
    .unwrap();
    assert_eq!(
        receipt["location"]["facts"]["address"],
        world.ollama.as_ref().unwrap().address().to_string()
    );
    world.serve_local_ai();
    let mut done = setup.finish();
    done.events = [reviewed, before, done.events].concat();
    assert_eq!(done.result["outcome"], "completed", "{}", done.result);
    assert_eq!(
        phases(&done.events, "local_ai"),
        [
            "plan",
            "preflight",
            "download",
            "install",
            "download",
            "verify",
            "cleanup"
        ]
    );
    assert_eq!(last_progress(&done.events), (total, total));
    assert_eq!(row(&done.result, "local_ai")["state"], "ready");
    let requests = world
        .ollama
        .as_ref()
        .unwrap()
        .state
        .lock()
        .unwrap()
        .requests
        .clone();
    let count = |prefix: &str| {
        requests
            .iter()
            .filter(|line| line.starts_with(prefix))
            .count()
    };
    assert_eq!(count("POST /api/pull"), 2, "{requests:?}");
    assert_eq!(count("POST /api/generate"), 4, "one token for each role");

    // The quick check as the production role runs it, measuring this computer itself.
    // How long that takes depends on the machine, so only what it does and does not do
    // is asserted: it answers from the receipts, and loads and asks for nothing.
    let quick = world
        .start_with(&ChildConfig {
            measure_hardware: true,
            ..world.config(&["status"])
        })
        .finish();
    assert_eq!(row(&quick.result, "local_ai")["state"], "ready");
    assert_eq!(
        world
            .ollama
            .as_ref()
            .unwrap()
            .state
            .lock()
            .unwrap()
            .requests
            .len(),
        requests.len(),
        "a quick check loads no model and asks the server nothing"
    );
    assert_eq!(world.archive_requests(), 1, "nor does it reach the network");

    let verified = world.run(&["verify", "--item", "local_ai"]);
    assert_eq!(row(&verified.result, "local_ai")["state"], "ready");
    world.stop_local_ai();
    let stopped = world.run(&["verify", "--item", "local_ai"]);
    let local_ai = row(&stopped.result, "local_ai");
    assert_eq!(
        (&local_ai["state"], &local_ai["failure_category"]),
        (&json!("failed"), &json!("program_not_running")),
        "without the manager's server the full check cannot pass"
    );

    let removed = world.run(&["remove", "--item", "local_ai"]);
    assert_eq!(removed.result["outcome"], "removed", "{}", removed.result);
    assert_eq!(row(&removed.result, "local_ai")["state"], "absent");
    assert!(
        !world
            .root()
            .join("components/receipts/local_ai.json")
            .exists()
    );
    let models = world.root().join("models/ollama");
    for (model, name) in [(&text, TEXT), (&vision, VISION)] {
        assert!(
            model
                .files(&models, name)
                .iter()
                .all(|(path, _)| !path.exists())
        );
    }
}

#[test]
fn the_hardware_floor_is_the_selected_models_size_and_no_selection_is_never_held_back() {
    let text = StoredModel::new(1);
    let vision = StoredModel::new(9);
    let mut world = World::local_ai(&text, &vision);
    let small = |world: &World, arguments: &[&str]| {
        world
            .start_with(&ChildConfig {
                memory_bytes: GIB,
                ..world.config(arguments)
            })
            .finish()
    };
    let fits = small(&world, &["status"]);
    assert_eq!(
        row(&fits.result, "local_ai")["state"],
        "absent",
        "models of a few hundred bytes fit in any memory"
    );

    world.admitted.as_mut().unwrap()[0].2 = GIB + 1;
    let held = small(&world, &["status"]);
    let local_ai = row(&held.result, "local_ai");
    assert_eq!(
        (&local_ai["state"], &local_ai["blocked_reason"]),
        (&json!("blocked"), &json!("hardware")),
        "{local_ai}"
    );
    let refused = small(&world, &["plan", "--item", "local_ai"]);
    assert_eq!(
        (
            &refused.result["outcome"],
            &refused.result["failure_category"]
        ),
        (&json!("refused"), &json!("not_enough_memory")),
        "{}",
        refused.result
    );
    let roomy = world.run(&["status"]);
    assert_eq!(row(&roomy.result, "local_ai")["state"], "absent");

    world.admitted = Some(Vec::new());
    let alone = small(&world, &["plan", "--item", "local_ai"]);
    assert_eq!(alone.result["outcome"], "ok", "{}", alone.result);
    let parts = alone.result["plan"]["entries"][0]["parts"]
        .as_array()
        .unwrap()
        .iter()
        .map(|part| part["part_id"].as_str().unwrap().to_owned())
        .collect::<Vec<_>>();
    assert_eq!(parts, ["program"], "no selection plans the program alone");
    assert_eq!(
        world
            .ollama
            .as_ref()
            .unwrap()
            .state
            .lock()
            .unwrap()
            .requests
            .len(),
        0,
        "planning asks the server nothing"
    );
}

#[test]
fn the_role_as_it_ships_reports_the_local_ai_but_never_provisions_it() {
    let text = StoredModel::new(1);
    let vision = StoredModel::new(9);
    let mut world = World::local_ai(&text, &vision);
    world.admitted = None;

    let status = world.run(&["status"]);
    let local_ai = row(&status.result, "local_ai");
    assert_eq!(local_ai["state"], "absent", "{local_ai}");
    assert_eq!(local_ai["recovery"], "set_up_in_desktop");
    assert_eq!(
        local_ai["recovery_action_id"],
        "operator.provision.local_ai"
    );

    for command in ["plan", "setup", "remove"] {
        let refused = world.run(&[command, "--item", "local_ai"]);
        assert_eq!(
            (refused.code, &refused.result["outcome"]),
            (1, &json!("refused")),
            "{command}: {}",
            refused.result
        );
        assert!(
            refused.events.iter().all(|event| event["type"] != "review"),
            "{command}"
        );
    }

    for command in ["plan", "setup"] {
        let every = world.run(&[command]);
        assert!(
            every.result["plan"]["entries"]
                .as_array()
                .into_iter()
                .flatten()
                .all(|entry| entry["item_id"] != "local_ai"),
            "a {command} of every item leaves the local AI out: {}",
            every.result
        );
        assert!(every.events.iter().all(|event| event["type"] != "review"));
    }

    assert_eq!(world.archive_requests(), 0, "nothing was downloaded");
    assert!(!world.programs().join(EXECUTABLE).exists());
    assert_eq!(
        world
            .ollama
            .as_ref()
            .unwrap()
            .state
            .lock()
            .unwrap()
            .requests
            .len(),
        0,
        "no model was pulled"
    );
}

#[test]
fn the_desktop_engine_removes_one_model_and_keeps_the_program_and_the_rest() {
    let text = StoredModel::new(1);
    let vision = StoredModel::new(9);
    let world = World::local_ai(&text, &vision);
    let models = world.root().join("models/ollama");
    let store = |stored: &StoredModel, name: &str| {
        for (path, bytes) in stored.files(&models, name) {
            fs::create_dir_all(path.parent().unwrap()).unwrap();
            fs::write(path, bytes).unwrap();
        }
    };
    let remaining = |stored: &StoredModel, name: &str| {
        stored
            .files(&models, name)
            .iter()
            .filter(|(path, _)| path.exists())
            .count()
    };
    store(&text, TEXT);
    store(&vision, VISION);
    let receipt = world.root().join("components/receipts/local_ai.json");
    fs::create_dir_all(receipt.parent().unwrap()).unwrap();
    fs::write(&receipt, b"{}").unwrap();
    let name = ModelName::parse(TEXT).unwrap();
    let engine = |admitted: Option<Vec<(String, String, u64)>>| {
        child_engine(&ChildConfig {
            admitted,
            ..world.config(&[])
        })
        .unwrap()
    };

    let refused = engine(None).remove_model(&name, &mut |_| {});
    assert_eq!(
        (refused.outcome, refused.item),
        (Outcome::Refused, Some(ItemId::LocalAi)),
        "an engine the desktop did not admit removes no model"
    );
    assert_eq!(remaining(&text, TEXT), 3);

    let mut phases = Vec::new();
    let removed = engine(world.admitted.clone()).remove_model(&name, &mut |event| {
        phases.extend(event_value(event));
    });
    assert_eq!(removed.outcome, Outcome::Removed, "{:?}", removed.failure);
    assert_eq!(removed.items, [ItemId::LocalAi]);
    assert_eq!(remaining(&text, TEXT), 0);
    assert_eq!(remaining(&vision, VISION), 3, "every other model stays");
    assert!(receipt.is_file(), "the local AI's receipt stays");
    assert!(
        phases.iter().any(|event| event["type"] == "phase"),
        "the removal runs under the local AI's writer: {phases:?}"
    );
}

/// A shared output buffer the role writes its lines to in this process.
#[derive(Clone, Default)]
struct Output(Arc<Mutex<Vec<u8>>>);

impl Write for Output {
    fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
        self.0.lock().unwrap().extend_from_slice(bytes);
        Ok(bytes.len())
    }

    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}

#[test]
fn a_command_line_the_protocol_does_not_have_is_refused_without_an_engine() {
    for arguments in [
        &[][..],
        &["install"],
        &["status", "--approve", "00"],
        &["status", "--full", "--full"],
        &["setup", "--item", "google"],
        &["setup", "--approve", "not-a-digest"],
        &["setup", "--item"],
        &["remove"],
        &["cancel", "--item", "browser"],
        &["verify", "--full"],
        &["plan", "--model", "text_extraction", TEXT, "5"],
        &[
            "setup",
            "--item",
            "local_ai",
            "--model",
            "text_extraction",
            TEXT,
            "5",
        ],
        &["cancel", "--model", "text_extraction", TEXT, "5"],
    ] {
        let arguments: Vec<OsString> = arguments.iter().map(OsString::from).collect();
        let output = Output::default();
        let code = serve(&arguments, Cursor::new(Vec::new()), output.clone(), || {
            panic!("no engine is made for {arguments:?}")
        });
        assert_eq!(code, INVALID_REQUEST, "{arguments:?}");
        let written = output.0.lock().unwrap().clone();
        let line: Value = serde_json::from_slice(&written).unwrap();
        assert_eq!(line["outcome"], "invalid_request");
        assert_eq!(written.iter().filter(|byte| **byte == b'\n').count(), 1);
    }
    let digest = Sha256Digest::of(b"plan");
    let command = |arguments: &[&str]| CommandLine::parse(arguments).map(|request| request.command);
    assert_eq!(
        command(&[
            "setup",
            "--item",
            "local_ai",
            "--approve",
            digest.as_str(),
            "--item",
            "browser",
            "--item",
            "local_ai"
        ]),
        Some(Command::Setup(SetupRequest {
            items: Some(vec![ItemId::Browser, ItemId::LocalAi]),
            approved: Some(digest),
        }))
    );
    assert_eq!(
        command(&["status", "--full"]),
        Some(Command::Status {
            mode: CheckMode::Full,
            items: ItemId::ALL.to_vec(),
        })
    );
    assert_eq!(
        command(&["remove", "--item", "browser"]),
        Some(Command::Remove {
            items: vec![ItemId::Browser]
        })
    );
}

/// The plan's digest for the admitted selection `models`.
fn plan_digest(world: &World, models: &[(&str, &str, u64)]) -> String {
    let config = ChildConfig {
        admitted: Some(
            models
                .iter()
                .map(|(role, name, size)| ((*role).to_owned(), (*name).to_owned(), *size))
                .collect(),
        ),
        ..world.config(&["plan", "--item", "local_ai"])
    };
    let planned = world.start_with(&config).finish();
    assert_eq!(planned.result["outcome"], "ok", "{}", planned.result);
    planned.result["plan_digest"].as_str().unwrap().to_owned()
}

#[test]
fn the_plan_digest_binds_every_selected_role_name_and_size() {
    let text = StoredModel::new(1);
    let vision = StoredModel::new(9);
    let world = World::local_ai(&text, &vision);
    let selection = [
        ("text_extraction", TEXT, 5),
        ("vision_transcription", VISION, 7),
    ];
    let digest = plan_digest(&world, &selection);
    assert_eq!(
        plan_digest(&world, &[selection[1], selection[0]]),
        digest,
        "the order the desktop admits them in is not part of the plan"
    );
    for changed in [
        [("text_extraction", "synthetic-text:other", 5), selection[1]],
        [("text_extraction", TEXT, 6), selection[1]],
        [("column_role_mapping", TEXT, 5), selection[1]],
    ] {
        assert_ne!(plan_digest(&world, &changed), digest, "{changed:?}");
    }
    assert_ne!(plan_digest(&world, &selection[..1]), digest);
    let program_only = plan_digest(&world, &[]);
    assert_ne!(program_only, digest, "no selection plans the program alone");
}

#[test]
fn a_setting_the_engine_cannot_use_is_answered_with_that_refusals_own_category() {
    // The role's clients word the category they are given, so a proxy setting the
    // engine refuses must not reach them as a protocol fault.
    for (settings, category) in [
        (Some("ftp://proxy.example:3128"), "blocked_by_network"),
        (Some("http://proxy.example:0"), "blocked_by_network"),
        (None, "unexpected"),
    ] {
        let output = Output::default();
        let code = serve(
            &[OsString::from("status")],
            Cursor::new(Vec::new()),
            output.clone(),
            || {
                let proxy = ProxySettings::from_settings(|name| {
                    settings.filter(|_| name == PROXY_URL).map(str::to_owned)
                })?;
                assert!(proxy.is_none(), "a refused setting never becomes a proxy");
                Err(Error::Invalid("no engine for this case".into()))
            },
        );

        assert_eq!(code, 1, "{settings:?}");
        let written = output.0.lock().unwrap().clone();
        let lines: Vec<Value> = written
            .split(|byte| *byte == b'\n')
            .filter(|line| !line.is_empty())
            .map(|line| serde_json::from_slice(line).unwrap())
            .collect();
        let result = lines.last().unwrap();
        assert_eq!(result["type"], "result", "{settings:?}");
        assert_eq!(result["command"], "status", "{settings:?}");
        assert_eq!(result["outcome"], "failed", "{settings:?}");
        assert_eq!(result["failure_category"], category, "{settings:?}");
        assert_eq!(result["rows"], Value::Null, "{settings:?}");
    }
}
