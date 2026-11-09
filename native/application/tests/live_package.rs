//! Explicit acceptance against a selected staged or independently relocated package.
#![cfg(feature = "live-package-tests")]
use cadrumo_application::{
    child::ChildConfiguration,
    component::Cancellation,
    package::Readiness,
    provisioning::{
        browser::{BrowserLayout, DRIVER_PACKAGE, DriverManifest},
        connection::Network,
        items::{FULL_CHECK_BUDGET, Locations},
        local_ai::{
            Placement,
            hardware::Hardware,
            huggingface::{HuggingFaceFile, HuggingFaceModel},
            llama_server::{self, LlamaServer, Presentation},
            loopback::Loopback,
            models::{LocalModels, ModelArtefact, Models, SelectedModel},
            program::{self, Uncontained},
            supervision::Supervised,
        },
        pins::{ComponentPins, Platform},
        receipts::ReceiptReading,
        state::Observation,
        transfer::{RetryPolicy, SystemPacing, Transfer, TransferEvent},
    },
    python::{self, PythonExpectation},
    value::RelativePath,
};
use serde_json::{Value, json};
use std::{
    net::{SocketAddr, TcpListener},
    num::NonZeroU32,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    time::{Duration, Instant},
};

#[tokio::test]
async fn manifest_cohort_matches_selected_packaged_interpreter() {
    let root = PathBuf::from(
        std::env::var_os("CADRUMO_TEST_PACKAGE_ROOT")
            .expect("CADRUMO_TEST_PACKAGE_ROOT is required"),
    );
    let manifest_path = RelativePath::new(
        std::env::var("CADRUMO_TEST_PACKAGE_MANIFEST")
            .expect("CADRUMO_TEST_PACKAGE_MANIFEST is required from the selected layout"),
    )
    .unwrap();
    let manifest_bytes = std::fs::read(manifest_path.under(&root)).unwrap();
    let layout: serde_json::Value = serde_json::from_slice(&manifest_bytes).unwrap();
    let executable = RelativePath::new(
        layout["layout"]["paths"]["executable"]
            .as_str()
            .expect("projected executable path"),
    )
    .unwrap();
    let platform = std::env::var("CADRUMO_TEST_PACKAGE_PLATFORM")
        .expect("CADRUMO_TEST_PACKAGE_PLATFORM is required from the selected layout");
    let abi = std::env::var("CADRUMO_TEST_PACKAGE_ABI")
        .expect("CADRUMO_TEST_PACKAGE_ABI is required from the selected layout")
        .parse()
        .expect("package ABI must be an integer");
    #[cfg(feature = "live-release-tests")]
    let inspection = {
        use cadrumo_application::package::release::{ReleaseExpectation, inspect_release};
        let expectations = std::env::var_os("CADRUMO_TEST_RELEASE_EXPECTATION").expect(
            "CADRUMO_TEST_RELEASE_EXPECTATION must name verifier-supplied release expectations",
        );
        let expected: ReleaseExpectation =
            serde_json::from_slice(&std::fs::read(expectations).unwrap()).unwrap();
        assert_eq!(expected.platform, platform);
        assert_eq!(expected.abi, abi);
        inspect_release(&root, &manifest_path, &expected).unwrap()
    };
    #[cfg(not(feature = "live-release-tests"))]
    let inspection = cadrumo_application::package::PackageManifest::read(&root, &manifest_path)
        .unwrap()
        .inspect(&root, &manifest_path, &platform, abi)
        .unwrap();
    assert_eq!(inspection.readiness, Readiness::Ready);
    let expected = PythonExpectation::from_manifest(&inspection.manifest, &executable).unwrap();
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let configuration = ChildConfiguration::from_platform(
        executable.under(&root),
        directory.path().to_owned(),
        directory.path(),
        std::env::vars_os(),
    )
    .unwrap();
    let report = python::probe(
        &configuration,
        &expected,
        Duration::from_secs(60),
        &Cancellation::default(),
    )
    .await
    .unwrap();
    let package_path = |key: &str| {
        RelativePath::new(
            layout["layout"]["paths"][key]
                .as_str()
                .expect("projected package path"),
        )
        .unwrap()
        .under(&root)
    };
    let driver = DriverManifest::read(&package_path("packages").join(DRIVER_PACKAGE)).unwrap();
    let pins = ComponentPins::load(&package_path("component_pins")).unwrap();
    let browser_root = directory.path().join("empty-browser-cache");
    let browser = BrowserLayout::new(
        browser_root.clone(),
        &driver,
        pins.browser.as_ref(),
        Platform::current().expect("supported package host"),
    )
    .unwrap();
    assert!(
        browser.pinned(),
        "package browser pins must cover its driver"
    );
    assert_eq!(
        browser.quick_check(&ReceiptReading::Absent).observation,
        Observation::Absent
    );
    assert!(!browser_root.exists(), "browser inspection created data");
    assert_eq!(
        std::fs::read(manifest_path.under(&root)).unwrap(),
        manifest_bytes,
        "probe changed manifest"
    );
    let after = inspection
        .manifest
        .inspect(&root, &manifest_path, &platform, abi)
        .unwrap();
    assert_eq!(
        after.readiness,
        Readiness::Ready,
        "probe changed package inventory"
    );
    println!(
        "Packaged CPython {}: {} exact distribution versions; browser absent",
        report.version,
        report.distributions.len()
    );
}

/// The smallest public GGUF model the local engine tests need, pinned as the catalogue
/// pins a model: llama.cpp's own test model, one 1.2 MB file at a fixed commit.
const TINY_REPOSITORY: &str = "ggml-org/test-model-stories260K";
const TINY_REVISION: &str = "479896ec924af6d40fd419ab8f4d1eb2101de00d";
const TINY_FILE: &str = "stories260K-f32.gguf";
const TINY_SHA256: &str = "270cba1bd5109f42d03350f60406024560464db173c0e387d91f0426d3bd256d";
const TINY_BYTES: u64 = 1_185_376;
/// The llama.cpp context the tiny model is stated with, which its pull records and the
/// router's preset loads it with.
const TINY_CONTEXT: NonZeroU32 = NonZeroU32::new(8192).unwrap();
/// The most a real program may take to answer after it starts.
const PROGRAM_WAIT: Duration = Duration::from_secs(120);

/// The package's `llama_server` folder, from the selected layout.
fn packaged_llama_folder() -> PathBuf {
    let root = PathBuf::from(
        std::env::var_os("CADRUMO_TEST_PACKAGE_ROOT")
            .expect("CADRUMO_TEST_PACKAGE_ROOT is required"),
    );
    let manifest_path = RelativePath::new(
        std::env::var("CADRUMO_TEST_PACKAGE_MANIFEST")
            .expect("CADRUMO_TEST_PACKAGE_MANIFEST is required from the selected layout"),
    )
    .unwrap();
    let layout: Value =
        serde_json::from_slice(&std::fs::read(manifest_path.under(&root)).unwrap()).unwrap();
    RelativePath::new(
        layout["layout"]["paths"]["llama_server"]
            .as_str()
            .expect("projected package path"),
    )
    .unwrap()
    .under(&root)
}

fn free_address() -> SocketAddr {
    TcpListener::bind("127.0.0.1:0")
        .unwrap()
        .local_addr()
        .unwrap()
}

/// Fetches the tiny model into the models folder `root` with the engine's own fetcher,
/// from Hugging Face itself, stating its llama.cpp context, and returns it with the
/// folder's `Models`.
fn fetch_tiny_model(root: &Path) -> (SelectedModel, Models) {
    let file = HuggingFaceFile::new(TINY_FILE, TINY_SHA256, TINY_BYTES).unwrap();
    let declared = HuggingFaceModel::new(TINY_REPOSITORY, TINY_REVISION, file, None).unwrap();
    let model = SelectedModel::of_artefact(
        "text_extraction",
        ModelArtefact::HuggingFace(declared),
        None,
        Some(TINY_CONTEXT),
    )
    .unwrap();
    let models = Models::new(
        LocalModels::new(vec![model.clone()]).unwrap(),
        root.to_owned(),
    );
    // The hosts a plan would name for the model: nothing else may be reached.
    let hosts = model.artefact.source_hosts();
    let network = Network::new(None);
    let mut pacing = SystemPacing::default();
    let cancellation = Cancellation::default();
    let mut events = |_: TransferEvent| {};
    let pulled = models
        .pull(
            &model,
            &mut Transfer {
                network: &network,
                hosts: &hosts,
                policy: RetryPolicy::default(),
                pacing: &mut pacing,
                events: &mut events,
                cancellation: &cancellation,
            },
        )
        .expect("the tiny model is fetched from Hugging Face at its pinned digest");
    assert_eq!(pulled.observation, Observation::Present);
    assert_eq!(pulled.bytes, TINY_BYTES);
    (model, models)
}

/// The entries of the router's model list: each model's id, aliases and status.
fn listed(router: Loopback) -> Vec<Value> {
    let (status, body) = router.get("/models").unwrap();
    assert_eq!(status, 200);
    let list: Value = serde_json::from_slice(&body).unwrap();
    list["data"].as_array().expect("a list of models").clone()
}

/// The packaged llama-server, started as the manager starts it, answers as the pinned
/// build while it holds no model, presents the model the Rust fetcher stored, and
/// generates a counted token with it.
#[test]
fn the_packaged_llama_server_answers_as_the_pinned_build_and_generates_from_a_fetched_model() {
    let storage = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let locations = Locations::under(storage.path());
    let (model, models) = fetch_tiny_model(&locations.models);
    let build = cadrumo_platform::LLAMA_SERVER_BUILD;
    let mut llama =
        LlamaServer::packaged(&packaged_llama_folder(), build, &locations, Placement::Auto)
            .expect("the selected package carries the llama-server");
    llama
        .serve(
            free_address(),
            &Uncontained,
            &|name| std::env::var_os(name),
            None,
        )
        .expect("the router starts, answers ready and reports the pinned build");
    let folder = llama.folder().to_owned();
    // The preset loads the model with the context its pull recorded.
    let preset = std::fs::read_to_string(folder.join(llama_server::PRESET)).unwrap();
    assert!(
        preset.contains(&format!("ctx-size = {TINY_CONTEXT}\n")),
        "{preset}"
    );
    let router = llama.server().expect("the router runs").loopback();
    let name = model.name().to_string();

    // The router answers its build while no model is loaded.
    let (status, body) = router.get(llama_server::PROPERTIES).unwrap();
    assert_eq!(status, 200);
    let properties: Value = serde_json::from_slice(&body).unwrap();
    let reported = properties["build_info"].as_str().expect("a build_info");
    assert!(
        reported == build || reported.starts_with(&format!("{build}-")),
        "{reported}"
    );
    assert_eq!(properties["role"], "router");
    let entries = listed(router);
    assert!(
        entries
            .iter()
            .all(|entry| entry["status"]["value"] == "unloaded"),
        "{entries:?}"
    );
    // It lists the model under the id the preset names and answers to its name as an alias.
    let entry = entries
        .iter()
        .find(|entry| entry["id"] == llama_server::router_id(&name))
        .unwrap_or_else(|| panic!("the router lists no model under its id: {entries:?}"));
    assert!(entry["aliases"].as_array().unwrap().contains(&json!(name)));
    assert_eq!(
        llama_server::presentation(&folder, model.name()),
        Presentation::Presented
    );

    // A load by the model's name, then a completion that reports the tokens it made.
    llama_server::load(&folder, model.name()).expect("the router takes the load by its name");
    // The router answers a load before the model has loaded: its entry reads loaded later.
    let loading = Instant::now();
    while !listed(router).iter().any(|entry| {
        entry["id"] == llama_server::router_id(&name) && entry["status"]["value"] == "loaded"
    }) {
        assert!(
            loading.elapsed() < FULL_CHECK_BUDGET,
            "the model never read loaded: {:?}",
            listed(router)
        );
        std::thread::sleep(Duration::from_millis(100));
    }
    let request = json!({
        "model": name,
        "prompt": "Reply with one word.",
        "max_tokens": 1,
        "stream": false,
    });
    let (status, body) = router
        .with_io_timeout(FULL_CHECK_BUDGET)
        .post("/v1/completions", request.to_string().as_bytes())
        .unwrap();
    assert_eq!(status, 200, "{}", String::from_utf8_lossy(&body));
    let completion: Value = serde_json::from_slice(&body).unwrap();
    assert!(
        completion["usage"]["completion_tokens"]
            .as_u64()
            .is_some_and(|tokens| tokens >= 1),
        "{completion}"
    );
    let unload = json!({ "model": name });
    let (status, _) = router
        .post("/models/unload", unload.to_string().as_bytes())
        .unwrap();
    assert_eq!(status, 200);
    // The router answers an unload before the model has gone: the full check below starts
    // from a model the router no longer holds, as a check of a stored model does.
    let unloading = Instant::now();
    while !listed(router).iter().any(|entry| {
        entry["id"] == llama_server::router_id(&name) && entry["status"]["value"] == "unloaded"
    }) {
        assert!(
            unloading.elapsed() < FULL_CHECK_BUDGET,
            "the model never read unloaded: {:?}",
            listed(router)
        );
        std::thread::sleep(Duration::from_millis(100));
    }

    // The engine's own full check, from the store to the unload.
    assert_eq!(
        models
            .check_full_on_router(&folder, &model, &Hardware::default())
            .expect("the full check reaches an answer"),
        Observation::Present
    );
    assert!(
        listed(router)
            .iter()
            .all(|entry| entry["status"]["value"] == "unloaded"),
        "the check unloads what it loaded"
    );
    llama.halt();
}

/// An Ollama program that ends with the test, whatever happens in it.
struct Serving(Child);

impl Drop for Serving {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

/// A real Ollama program lists and generates from a model the Rust fetcher wrote, and
/// leaves the store whole under `OLLAMA_NOPRUNE`. The program is one installed outside
/// Cadrumo, found as the engine reports one; the package carries none.
#[test]
fn a_real_ollama_lists_and_generates_from_a_model_the_rust_fetcher_wrote() {
    let storage = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let locations = Locations::under(storage.path());
    let (model, models) = fetch_tiny_model(&locations.models);
    let candidates = program::system_locations(&|name| std::env::var_os(name));
    let executable = program::system_program(&candidates, &locations.programs)
        .expect("an Ollama program installed outside Cadrumo is required");
    let address = free_address();
    let mut command = Command::new(&executable);
    command
        .arg("serve")
        .env("OLLAMA_HOST", address.to_string())
        .env("OLLAMA_MODELS", &locations.models)
        .env("OLLAMA_NOPRUNE", "1")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    let _serving = Serving(command.spawn().expect("the Ollama program starts"));
    let server = Loopback::new(address).unwrap();
    let started = Instant::now();
    while !matches!(server.get("/api/version"), Ok((200, _))) {
        assert!(
            started.elapsed() < PROGRAM_WAIT,
            "the Ollama program never answered"
        );
        std::thread::sleep(Duration::from_millis(250));
    }

    let name = model.name().to_string();
    let (status, body) = server.get("/api/tags").unwrap();
    assert_eq!(status, 200);
    let tags: Value = serde_json::from_slice(&body).unwrap();
    assert!(
        tags["models"]
            .as_array()
            .expect("a list of models")
            .iter()
            .any(|listed| listed["name"] == name),
        "the program does not list the fetched model: {tags}"
    );
    let request = json!({
        "model": name,
        "prompt": "Reply with one word.",
        "stream": false,
        "keep_alive": 0,
        "options": { "num_predict": 1 },
    });
    let (status, body) = server
        .with_io_timeout(FULL_CHECK_BUDGET)
        .post("/api/generate", request.to_string().as_bytes())
        .unwrap();
    assert_eq!(status, 200, "{}", String::from_utf8_lossy(&body));
    let generated: Value = serde_json::from_slice(&body).unwrap();
    assert_eq!(generated["done"], true, "{generated}");
    assert_eq!(
        models.observe_quick(&model, &Hardware::default()),
        Observation::Present,
        "the program left the store whole"
    );
}
