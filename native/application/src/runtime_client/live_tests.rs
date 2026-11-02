use super::connection::{Connection, SessionExchange};
use super::endpoint::Endpoint;
use super::events::{Event, Pushed};
use super::framing::text;
use super::handshake::Cohort;
use super::refusal::Refusal;
use super::session::Frontend;
use super::stored_proof::{ProofRefusal, stored_sign_in_proof};
use serde_json::{Map, Value, json};
use std::sync::{Mutex, mpsc};
use std::time::{Duration, Instant};
use zeroize::Zeroizing;

struct Live {
    root: std::path::PathBuf,
    cohort: Cohort,
    profile_id: String,
    password: Zeroizing<Vec<u8>>,
    /// A Modelo 303 work unit the profile holds.
    work_unit: String,
}

fn live() -> Option<Live> {
    let root = std::env::var_os("CADRUMO_RUNTIME_LIVE_ROOT")?;
    let password_file = std::env::var_os("CADRUMO_RUNTIME_LIVE_PASSWORD_FILE")?;
    Some(Live {
        root: root.into(),
        cohort: Cohort {
            product_version: std::env::var("CADRUMO_RUNTIME_LIVE_VERSION").ok()?,
            authority_generation: None,
        },
        profile_id: std::env::var("CADRUMO_RUNTIME_LIVE_PROFILE_ID").ok()?,
        password: Zeroizing::new(std::fs::read(password_file).ok()?),
        work_unit: std::env::var("CADRUMO_RUNTIME_LIVE_WORK_UNIT").ok()?,
    })
}

fn soon() -> Instant {
    Instant::now() + Duration::from_secs(30)
}

/// The real connection, noting each definition whose streamed upload the
/// runtime took and answered with an admitted operation.
struct Streams<'a> {
    connection: &'a Connection,
    streamed: Mutex<Vec<String>>,
}

impl SessionExchange for Streams<'_> {
    fn exchange(&self, request: &Value, deadline: Instant) -> Result<Map<String, Value>, Refusal> {
        self.connection.exchange(request, deadline)
    }

    fn exchange_streamed(
        &self,
        request: &Value,
        payload: &[u8],
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        let answered = self
            .connection
            .exchange_streamed(request, payload, deadline)?;
        if text(&answered, "kind") == Some("operation_submitted") {
            let definition = text(request.as_object().unwrap(), "definition_id");
            self.streamed
                .lock()
                .unwrap()
                .push(definition.unwrap_or_default().to_owned());
        }
        Ok(answered)
    }

    fn exchange_with_secret(
        &self,
        request: &Value,
        secret: &[u8],
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        self.connection
            .exchange_with_secret(request, secret, deadline)
    }

    fn subscribe_scoped(&self) -> mpsc::Receiver<Pushed> {
        self.connection.subscribe_scoped()
    }

    fn close(&self) {
        self.connection.close();
    }
}

#[test]
#[ignore = "needs a running runtime: see dev/runtime_lifecycle/native_client_live.py"]
fn a_window_signs_in_reads_its_session_and_signs_out_natively() {
    let live = live().expect("CADRUMO_RUNTIME_LIVE_* must name a served root");
    let endpoint = Endpoint::of(&live.root).unwrap();
    let watcher = Connection::open(&endpoint, &live.cohort, soon()).unwrap();
    assert_eq!(watcher.hello().product_version, live.cohort.product_version);
    let cues = watcher.subscribe();
    let (named, label) = watcher
        .login_target(&live.profile_id, soon())
        .unwrap()
        .unwrap();
    assert_eq!(named, live.profile_id);
    assert!(!label.is_empty());
    assert!(
        watcher
            .login_target("no-such-profile-label", soon())
            .unwrap()
            .is_none()
    );
    let active = watcher.active_profile(true, soon()).unwrap();
    assert_eq!(
        active.selected_profile_id.as_deref(),
        Some(live.profile_id.as_str())
    );
    let before = watcher
        .sign_in_status(&live.profile_id, true, soon())
        .unwrap();
    assert_eq!(
        before.presence, "present",
        "the harness stored a CLI sign-in first"
    );

    // The stored sign-in is resumed with the proof its receipt names, as a
    // window resumes it when it finds the profile signed in; timed from connecting.
    // A keychain that guards the command line's item from other programs refuses
    // the window at once, without asking, and the window signs in with the password.
    let resumed = match stored_sign_in_proof(&live.root, &live.profile_id) {
        Ok(_) => {
            let started = Instant::now();
            let resumed = Connection::open(&endpoint, &live.cohort, soon()).unwrap();
            let session = resumed
                .resume_receipt(&live.root, &live.profile_id, Frontend::Cli, soon())
                .unwrap();
            let resumed_in = started.elapsed();
            assert_eq!(session.profile_id, live.profile_id);
            assert_eq!(
                resumed.connection_id().as_deref(),
                Some(session.connection_id.as_str())
            );
            let status = resumed.status(&session, soon()).unwrap();
            assert_eq!(status["session_id"], json!(session.session_id));
            resumed.note_activity(&session, soon()).unwrap();
            Some((resumed, session, resumed_in))
        }
        Err(ProofRefusal::KeyringUnavailable) if cfg!(target_os = "macos") => None,
        Err(refusal) => panic!("stored sign-in proof: {refusal:?}"),
    };

    // The window's own password sign-in, on a development root, timed from
    // connecting. Storing it for the other frontends is admitted only from
    // the installed desktop image, so this sign-in is not stored.
    let started = Instant::now();
    let window = Connection::open(&endpoint, &live.cohort, soon()).unwrap();
    let connected = started.elapsed();
    let retirements = resumed
        .as_ref()
        .map(|(connection, _, _)| connection.subscribe());
    let held = window
        .login_password(
            &live.profile_id,
            Frontend::Desktop,
            &live.password,
            false,
            soon(),
        )
        .unwrap();
    let signed_in = started.elapsed();
    println!(
        "native sign-in: connect {} ms, password sign-in {} ms; receipt resume {:?}",
        connected.as_millis(),
        signed_in.as_millis(),
        resumed.as_ref().map(|(_, _, resumed_in)| resumed_in)
    );
    assert_eq!(held.profile_id, live.profile_id);
    assert!(
        window.status(&held, soon()).unwrap()["credential_authenticated"]
            .as_bool()
            .unwrap()
    );
    // A registered operation runs through the window's session: the
    // profile's language, as the desktop reads it.
    let language =
        crate::person_operations::profile_language::read_profile_language(&window, &held, soon())
            .unwrap();
    assert!(
        language
            .language
            .as_deref()
            .is_none_or(|language| ["es", "en", "ca", "hu"].contains(&language)),
        "{:?}",
        language.language
    );

    // A real Modelo 303 edit's preflight and apply operands, its renewal
    // and a plain submission too large for one frame all reach the
    // runtime's staging streamed: the runtime reads each upload's header,
    // says it is ready for exactly that upload, takes its bytes, decodes
    // them and answers with the operation it admitted. The baseline is the
    // one the form read admitted in the desktop frontend's committed
    // `modelo-303-1T-en.json` envelope, extracted whole, here naming this
    // profile and the work unit the harness created for it.
    let mut baseline: Value = serde_json::from_str(include_str!(
        "../tests/data/modelo-303-admitted-baseline.json"
    ))
    .unwrap();
    baseline["bucket_id"] = json!(live.profile_id);
    baseline["work_unit_id"] = json!(live.work_unit);
    let unit = live.work_unit.clone();
    let operand = json!({"input_version": 2, "output_language": "en",
        "submission": {"edit_contract_version": 1, "baseline": baseline,
        "mutation_family": baseline["mutation_family"], "scalar_intents": []}});
    let statement = json!({"profile_id": live.profile_id,
        "csv_text": "fecha,concepto,importe\n".repeat(4 * 1024)});
    let recording = Streams {
        connection: &window,
        streamed: Mutex::new(Vec::new()),
    };
    let mut relay = crate::person_operations::relay::OperationRelay::new();
    let mut submit = |action: &str, definition: &str, subject: String, member: &str, body| {
        let mut request = Map::new();
        request.insert("definition_id".into(), json!(definition));
        request.insert("subject_ref".into(), json!(subject));
        request.insert(member.into(), body);
        relay.handle(&recording, &held, action, &request)
    };
    let renewal = json!({"profile_id": live.profile_id, "baseline": baseline,
        "output_language": "en"});
    for (action, definition, member, body) in [
        (
            "operation_financial_submit",
            "modelo.edit.preflight",
            "input",
            operand.clone(),
        ),
        (
            "operation_financial_submit",
            "modelo.edit.apply",
            "input",
            operand,
        ),
        ("operation_submit", "modelo.edit.renew", "payload", renewal),
    ] {
        let answered = submit(action, definition, unit.clone(), member, body);
        let Ok(reply) = answered else {
            panic!("{definition}: {answered:?}");
        };
        assert_eq!(reply["kind"], "operation_submitted", "{definition}");
    }
    let classified = submit(
        "operation_submit",
        "ledger.classify.bulk",
        format!("profile:{}", live.profile_id),
        "payload",
        statement,
    )
    .unwrap();
    assert_eq!(classified["kind"], "operation_submitted");
    assert_eq!(
        *recording.streamed.lock().unwrap(),
        [
            "modelo.edit.preflight",
            "modelo.edit.apply",
            "modelo.edit.renew",
            "ledger.classify.bulk"
        ],
        "both went through the runtime's streamed upload"
    );

    // Signing out ends every human session and revokes the stored sign-in.
    let out = window.sign_out(&held, soon()).unwrap();
    assert!(out.automation_enabled.is_some() || out.automation_access_remains.is_none());
    assert!(out.session_ids.contains(&held.session_id));
    assert!(out.receipt_removed);
    if let (Some((_, session, _)), Some(retirements)) = (&resumed, &retirements) {
        assert!(out.session_ids.contains(&session.session_id));
        let retired = retirements.recv_timeout(Duration::from_secs(10)).unwrap();
        assert!(
            matches!(retired, Event::SessionRetired { .. }),
            "{retired:?}"
        );
    }
    let cue = cues.recv_timeout(Duration::from_secs(10)).unwrap();
    assert_eq!(cue, Event::SignInChanged);
    let after = watcher
        .sign_in_status(&live.profile_id, false, soon())
        .unwrap();
    assert_eq!(after.presence, "absent");
    assert_eq!(
        stored_sign_in_proof(&live.root, &live.profile_id).unwrap_err(),
        ProofRefusal::Absent
    );
    if let Some((resumed, session, _)) = &resumed {
        let refused = resumed.status(session, soon()).unwrap_err();
        assert!(
            matches!(refused, Refusal::Denied { .. } | Refusal::ConnectionClosed),
            "{refused}"
        );
    }
    window.close();
    watcher.close();
}
