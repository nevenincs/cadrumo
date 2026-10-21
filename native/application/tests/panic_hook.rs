//! Each scenario panics in a real child process; the parent reads the durable
//! log the child configured. A control child that keeps a silent hook proves
//! the assertions detect a missing record.
use cadrumo_application::{
    diagnostics::{DiagnosticSource, Diagnostics, panic},
    error::application::Operation,
};
use serde_json::Value;
use std::{env, fs, path::Path, process::Command, sync::Arc};

const SECRET: &str = "ES12345678Z-synthetic-private-payload";
const CHILD: &str = "--panic-child";

fn main() {
    let arguments: Vec<String> = env::args().skip(1).collect();
    if let [flag, scenario, hooked, directory] = arguments.as_slice()
        && flag == CHILD
    {
        child(scenario, hooked == "hooked", Path::new(directory));
    }
    let scenarios = [
        ("main", Ending::Unwound, "main"),
        ("thread", Ending::Exited, "panic-thread"),
        ("task", Ending::Exited, "main"),
        ("callback", Ending::Aborted, "main"),
    ];
    for (scenario, ending, thread) in scenarios {
        let run = run(scenario, true);
        run.assert_ending(ending);
        let panic = run.panic().unwrap_or_else(|| {
            panic!("{scenario}: no panic record in {:?}", run.log);
        });
        assert_eq!(panic["panic"]["file"], "panic_hook.rs", "{scenario}");
        assert_eq!(panic["panic"]["line"], site(scenario), "{scenario}");
        assert!(panic["panic"]["column"].as_u64().is_some_and(|c| c > 0));
        assert_eq!(panic["panic"]["thread"], thread, "{scenario}");
        assert_eq!(panic["panic"]["category"], "result_err", "{scenario}");
        assert_eq!(panic["source"], "desktop");
        assert!(panic["timestampMs"].as_u64().is_some_and(|t| t > 0));
        if matches!(ending, Ending::Exited) {
            assert!(
                run.records().iter().any(|r| r["kind"] == "failure"
                    && r["failure"]["code"] == "panic"
                    && r["failure"]["operation"] == "launch"),
                "{scenario}: the joined panic was not recorded"
            );
        }
        run.assert_private();
        println!("panic_hook {scenario}: ok");
    }

    // Without a configured file the record still leaves on standard error.
    let unconfigured = run("unconfigured", true);
    unconfigured.assert_ending(Ending::Unwound);
    let line = unconfigured
        .stderr
        .lines()
        .find(|line| line.contains("\"kind\":\"panic\""))
        .expect("an unconfigured panic reaches standard error");
    let record: Value = serde_json::from_str(line).unwrap();
    assert_eq!(record["panic"]["line"], site("unconfigured"));
    unconfigured.assert_private();
    println!("panic_hook unconfigured: ok");

    // The defect the hook prevents: a silent hook and an aborting boundary.
    let control = run("callback", false);
    control.assert_ending(Ending::Aborted);
    assert!(
        control.panic().is_none(),
        "the control child must leave no panic record"
    );
    println!("panic_hook control: ok");
}

/// The source line marked `site:<scenario>`, where that scenario panics.
fn site(scenario: &str) -> u32 {
    let marker = format!("// site:{scenario}");
    let index = include_str!("panic_hook.rs")
        .lines()
        .position(|line| line.trim_end().ends_with(&marker))
        .expect("every scenario marks its panic site");
    u32::try_from(index + 1).unwrap()
}

#[derive(Clone, Copy, Debug)]
enum Ending {
    /// The panic unwound out of `main`.
    Unwound,
    /// The child contained the panic and exited with `CONTAINED`.
    Exited,
    /// The panic could not unwind and the process aborted.
    Aborted,
}

const CONTAINED: i32 = 3;

struct Run {
    status: std::process::ExitStatus,
    log: String,
    stderr: String,
}

impl Run {
    fn records(&self) -> Vec<Value> {
        self.log
            .lines()
            .map(|line| serde_json::from_str(line).expect("every log line is one JSON record"))
            .collect()
    }
    fn panic(&self) -> Option<Value> {
        self.records().into_iter().find(|r| r["kind"] == "panic")
    }
    fn assert_ending(&self, ending: Ending) {
        match ending {
            Ending::Unwound => assert_eq!(self.status.code(), Some(101), "{ending:?}"),
            Ending::Exited => assert_eq!(self.status.code(), Some(CONTAINED), "{ending:?}"),
            Ending::Aborted => assert!(
                !self.status.success()
                    && ![Some(101), Some(CONTAINED)].contains(&self.status.code()),
                "{ending:?}: {:?}",
                self.status
            ),
        }
    }
    fn assert_private(&self) {
        assert!(!self.log.contains("ES12345678Z"), "payload in the log");
        assert!(!self.stderr.contains("ES12345678Z"), "payload on stderr");
    }
}

fn run(scenario: &str, hooked: bool) -> Run {
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let output = Command::new(env::current_exe().unwrap())
        .args([
            CHILD,
            scenario,
            if hooked { "hooked" } else { "silent" },
            directory.path().to_str().unwrap(),
        ])
        .output()
        .unwrap();
    let log = fs::read_to_string(directory.path().join("cadrumo-native.jsonl")).unwrap_or_default();
    Run {
        status: output.status,
        log,
        stderr: String::from_utf8_lossy(&output.stderr).into_owned(),
    }
}

fn failing() -> Result<(), String> {
    Err(SECRET.to_owned())
}

extern "C" fn callback() {
    // A panic cannot unwind out of an `extern "C"` function; the process aborts.
    failing().unwrap(); // site:callback
}

fn child(scenario: &str, hooked: bool, directory: &Path) -> ! {
    let diagnostics = Arc::new(Diagnostics::new(DiagnosticSource::Desktop));
    if hooked {
        panic::install(diagnostics.clone());
    } else {
        std::panic::set_hook(Box::new(|_| {}));
    }
    if scenario != "unconfigured" {
        diagnostics.configure(directory, 1 << 20, 1).unwrap();
    }
    match scenario {
        "main" => {
            failing().unwrap(); // site:main
            unreachable!()
        }
        "thread" => {
            let joined = std::thread::Builder::new()
                .name("panic-thread".into())
                .spawn(|| failing().unwrap()) // site:thread
                .unwrap()
                .join();
            assert!(joined.is_err());
            diagnostics.contained_panic(None, Operation::Launch);
            std::process::exit(CONTAINED)
        }
        "task" => {
            let runtime = tokio::runtime::Builder::new_current_thread()
                .build()
                .unwrap();
            let joined = runtime.block_on(async {
                tokio::spawn(async { failing().unwrap() }).await // site:task
            });
            assert!(joined.is_err_and(|error| error.is_panic()));
            diagnostics.contained_panic(None, Operation::Launch);
            std::process::exit(CONTAINED)
        }
        "callback" => {
            callback();
            unreachable!()
        }
        _ => {
            failing().unwrap(); // site:unconfigured
            unreachable!()
        }
    }
}
