use super::*;

const PROFILE_ID: &str = "11111111-1111-4111-8111-111111111111";

fn definition(id: &str) -> Definition {
    admitted(id).unwrap()
}
fn object(value: Value) -> Map<String, Value> {
    value.as_object().unwrap().clone()
}
fn hex(digit: char) -> String {
    digit.to_string().repeat(64)
}

#[test]
fn the_window_names_no_profile_and_no_edit_amounts_in_a_plain_payload() {
    for (id, payload) in [
        ("modelo.work.list", json!({"profile_id":"another"})),
        ("modelo.quickfile", json!({"bucket_id":"another"})),
        ("modelo.edit.preflight", json!({"work_unit_id":hex('a')})),
        ("modelo.edit.apply", json!({})),
    ] {
        assert_eq!(
            admit_fields(definition(id), &object(payload.clone()))
                .unwrap_err()
                .code,
            "invalid",
            "{id} {payload}"
        );
    }
    assert!(admit_fields(definition("modelo.work.list"), &object(json!({}))).is_ok());
}

#[test]
fn the_subject_is_the_one_the_contract_declares() {
    let unit = hex('a');
    let cases = [
        (
            "modelo.work.list",
            json!({}),
            None,
            Ok(format!("profile:{PROFILE_ID}")),
        ),
        (
            "modelo.work.form",
            json!({"work_unit_id":unit}),
            None,
            Ok(unit.clone()),
        ),
        (
            "modelo.work.discard",
            json!({"baseline":{"work_unit_id":unit}}),
            None,
            Ok(unit.clone()),
        ),
        (
            "modelo.work.m303_attestation",
            json!({"work_unit_id":null}),
            None,
            Ok(format!("profile:{PROFILE_ID}")),
        ),
        (
            "modelo.work.m303_attestation",
            json!({"work_unit_id":unit}),
            None,
            Ok(unit.clone()),
        ),
        (
            "modelo.export",
            json!({"calculation_revision_id":"r"}),
            Some(unit.as_str()),
            Ok(unit.clone()),
        ),
        // A stored record's work unit comes from the window, and only there.
        ("modelo.export", json!({}), None, Err("invalid")),
        (
            "modelo.export",
            json!({}),
            Some("not-a-unit"),
            Err("invalid"),
        ),
        (
            "modelo.work.list",
            json!({}),
            Some(unit.as_str()),
            Err("invalid"),
        ),
        ("modelo.work.form", json!({}), None, Err("invalid")),
        (
            "modelo.work.form",
            json!({"work_unit_id":" "}),
            None,
            Err("invalid"),
        ),
        (
            "modelo.work.discard",
            json!({"baseline":7}),
            None,
            Err("invalid"),
        ),
    ];
    for (id, payload, work_unit, expected) in cases {
        let found = subject(
            definition(id),
            PROFILE_ID,
            &object(payload.clone()),
            work_unit,
        )
        .map_err(|failure| failure.code);
        assert_eq!(found, expected, "{id} {payload}");
    }
}

#[test]
fn the_profile_is_filled_only_where_the_request_names_it() {
    let unit = hex('b');
    let (request, subject) = plain_submission(
        definition("modelo.work.calculate"),
        PROFILE_ID,
        Wiped(json!({"work_unit_id":unit, "actor":"desktop"})),
        None,
    )
    .unwrap();
    assert_eq!(subject, unit);
    assert!(request.0["payload"].get("profile_id").is_none());
    assert_eq!(request.0["action"], "operation_submit");
    assert_eq!(request.0["subject_ref"], unit);
    let (request, _) = plain_submission(
        definition("modelo.work.list"),
        PROFILE_ID,
        Wiped(json!({})),
        None,
    )
    .unwrap();
    assert_eq!(request.0["payload"]["profile_id"], PROFILE_ID);
    let refused = plain_submission(
        definition("modelo.work.rename"),
        PROFILE_ID,
        Wiped(json!({"work_unit_id":unit, "label":"a".repeat(PAYLOAD_LIMIT)})),
        None,
    )
    .unwrap_err();
    assert_eq!(refused.code, "too_large");
}

#[test]
fn every_request_field_that_names_a_file_takes_a_token() {
    let contracts = admitted::tests::contracts();
    for (id, facts) in contracts["operations"].as_object().unwrap() {
        let shipped: Vec<(&str, &str)> = facts["file_fields"]
            .as_object()
            .unwrap()
            .iter()
            .map(|(field, shape)| (field.as_str(), shape.as_str().unwrap()))
            .collect();
        let mut host: Vec<(&str, &str)> = PATH_FIELDS
            .iter()
            .filter(|field| field.definition == id)
            .map(|field| {
                let shape = match field.shape {
                    Shape::One => "one",
                    Shape::Optional => "optional",
                };
                (field.field, shape)
            })
            .collect();
        host.sort_unstable();
        assert_eq!(host, shipped, "{id}");
    }
    for field in PATH_FIELDS {
        assert!(admitted(field.definition).is_some(), "{}", field.definition);
        let writes = matches!(field.file, FileUse::Write(formats) if !formats.is_empty());
        assert!(
            writes || matches!(field.file, FileUse::Read(_)) || field.definition == EXPORT,
            "{} {} names how it is written",
            field.definition,
            field.field
        );
    }
}

/// A scratch folder with one file of each kind the purposes read.
fn scratch(name: &str) -> std::path::PathBuf {
    let root = std::env::temp_dir().join(format!(
        "cadrumo-modelo-tokens-{name}-{}",
        std::process::id()
    ));
    let _ = std::fs::remove_dir_all(&root);
    std::fs::create_dir_all(&root).unwrap();
    for file in ["justificante.pdf", "review.zip", "review.sig"] {
        std::fs::write(root.join(file), b"x").unwrap();
    }
    root
}
fn token(files: &Files, identity: &Value, purpose: Purpose, path: std::path::PathBuf) -> Value {
    let picks =
        serde_json::to_value(files.issue_all(identity, purpose, vec![path]).unwrap()).unwrap();
    picks["files"][0]["token"].clone()
}
fn saved(files: &Files, identity: &Value, format: Format, path: std::path::PathBuf) -> Value {
    let picks = serde_json::to_value(files.issue_save(identity, format, path).unwrap()).unwrap();
    picks["files"][0]["token"].clone()
}

#[test]
fn file_tokens_become_paths_only_where_the_definition_reads_or_writes_a_file() {
    let root = scratch("substitute");
    let files = Files::default();
    let session = json!({"session_id":"one"});
    let text = |path: std::path::PathBuf| json!(path.to_str().unwrap());
    let justificante = token(
        &files,
        &session,
        Purpose::Evidence,
        root.join("justificante.pdf"),
    );
    let package = token(&files, &session, Purpose::Package, root.join("review.zip"));
    let signature = token(
        &files,
        &session,
        Purpose::Signature,
        root.join("review.sig"),
    );
    let out_sig = saved(&files, &session, Format::Sig, root.join("counter.sig"));
    let fichero = saved(&files, &session, Format::Boe, root.join("modelo-303.boe"));
    let dictionary = saved(&files, &session, Format::Xml, root.join("modelo-200.xml"));
    let text_file = saved(&files, &session, Format::Csv, root.join("modelo-303.csv"));
    let report = saved(&files, &session, Format::Pdf, root.join("report.pdf"));

    let mut import = object(json!({"work_unit_id":hex('a'), "source_path":justificante}));
    substitute(
        &files,
        &session,
        definition("modelo.filing_record.import"),
        &mut import,
    )
    .unwrap();
    assert_eq!(import["source_path"], text(root.join("justificante.pdf")));
    let mut unattached = object(json!({"source_path":null}));
    substitute(
        &files,
        &session,
        definition("modelo.filing_record.import"),
        &mut unattached,
    )
    .unwrap();
    assert_eq!(unattached["source_path"], Value::Null);

    let mut sign = object(json!({"package":package, "signature":signature, "output":out_sig}));
    substitute(
        &files,
        &session,
        definition("modelo.review_package.counter_sign"),
        &mut sign,
    )
    .unwrap();
    assert_eq!(sign["package"], text(root.join("review.zip")));
    assert_eq!(sign["signature"], text(root.join("review.sig")));
    assert_eq!(sign["output"], text(root.join("counter.sig")));

    let mut export = object(json!({"calculation_revision_id":"r", "output_path":fichero}));
    substitute(&files, &session, definition("modelo.export"), &mut export).unwrap();
    assert_eq!(export["output_path"], text(root.join("modelo-303.boe")));
    let mut xml = object(json!({"output_path":dictionary, "artefact":"fichero_boe"}));
    substitute(&files, &session, definition("modelo.export"), &mut xml).unwrap();
    assert_eq!(xml["output_path"], text(root.join("modelo-200.xml")));
    let mut quickfile = object(json!({"output_path":fichero.clone()}));
    substitute(
        &files,
        &session,
        definition("modelo.quickfile"),
        &mut quickfile,
    )
    .unwrap();
    assert_eq!(quickfile["output_path"], text(root.join("modelo-303.boe")));
    let mut pdf = object(json!({"output_path":report, "artefact":"calculation_report_pdf"}));
    substitute(&files, &session, definition("modelo.export"), &mut pdf).unwrap();
    assert_eq!(pdf["output_path"], text(root.join("report.pdf")));

    for (id, payload) in [
        // A path, not a token.
        (
            "modelo.reconcile.import",
            json!({"source_path":root.join("justificante.pdf").to_str().unwrap()}),
        ),
        // A token picked for another purpose.
        (
            "modelo.review_package.sign",
            json!({"package":signature.clone(), "output":out_sig.clone()}),
        ),
        // A file to read where one is written, and the other way round.
        (
            "modelo.review_package.sign",
            json!({"package":package.clone(), "output":package.clone()}),
        ),
        (
            "modelo.reconcile.import",
            json!({"source_path":fichero.clone()}),
        ),
        // Saved as a format the field does not take.
        (
            "modelo.spreadsheet.export",
            json!({"output_path":fichero.clone()}),
        ),
        (
            "modelo.export",
            json!({"output_path":fichero.clone(), "artefact":"calculation_review_xlsx"}),
        ),
        (
            "modelo.export",
            json!({"output_path":fichero.clone(), "artefact":"unknown"}),
        ),
        // A filing file is the layout's own: never another kind of file.
        ("modelo.export", json!({"output_path":text_file.clone()})),
        ("modelo.quickfile", json!({"output_path":text_file.clone()})),
        // Not a file at all.
        ("modelo.work.report_verify", json!({"source_path":7})),
    ] {
        let mut payload = object(payload);
        assert_eq!(
            substitute(&files, &session, definition(id), &mut payload)
                .unwrap_err()
                .code,
            "invalid",
            "{id} {payload:?}"
        );
    }
    std::fs::remove_dir_all(root).unwrap();
}

fn edit_input(bucket: &str, work_unit: &str) -> String {
    json!({"input_version":2, "submission":{"edit_contract_version":1,
        "baseline":{"bucket_id":bucket, "work_unit_id":work_unit, "baseline_id":hex('e')},
        "mutation_family":"scalar", "scalar_intents":[{"value":"1234.56"}]}})
    .to_string()
}

#[test]
fn an_edits_amounts_come_only_as_a_raw_input_for_this_profiles_baseline() {
    let unit = hex('a');
    let body = InvokeBody::Raw(edit_input(PROFILE_ID, &unit).into_bytes());
    let (input, work_unit) = financial_body(&body, PROFILE_ID).unwrap();
    assert_eq!(work_unit, unit);
    assert_eq!(
        input.0["submission"]["scalar_intents"][0]["value"],
        "1234.56"
    );
    assert_eq!(format!("{input:?}"), "Wiped(..)", "it never prints");
    let request = financial_submission("modelo.edit.preflight", &work_unit, input).unwrap();
    assert_eq!(
        request.0["action"], "operation_financial_submit",
        "the operand never travels as a plain payload"
    );
    assert_eq!(request.0["definition_id"], "modelo.edit.preflight");
    assert_eq!(request.0["subject_ref"], unit);
    assert!(request.0.get("payload").is_none());
    assert_eq!(
        request.0["input"]["submission"]["baseline"]["bucket_id"],
        PROFILE_ID
    );
    let mut with_profile: Value = serde_json::from_str(&edit_input(PROFILE_ID, &unit)).unwrap();
    with_profile["profile_id"] = json!(PROFILE_ID);
    let mut versionless: Value = serde_json::from_str(&edit_input(PROFILE_ID, &unit)).unwrap();
    versionless.as_object_mut().unwrap().remove("input_version");
    for refused in [
        InvokeBody::Json(serde_json::from_str(&edit_input(PROFILE_ID, &unit)).unwrap()),
        InvokeBody::Raw(edit_input("22222222-2222-4222-8222-222222222222", &unit).into_bytes()),
        InvokeBody::Raw(edit_input(PROFILE_ID, "short").into_bytes()),
        InvokeBody::Raw(with_profile.to_string().into_bytes()),
        InvokeBody::Raw(versionless.to_string().into_bytes()),
        InvokeBody::Raw(b"[]".to_vec()),
        InvokeBody::Raw(vec![b' '; person::REQUEST_LIMIT + 1]),
    ] {
        assert_eq!(
            financial_body(&refused, PROFILE_ID).unwrap_err().code,
            "invalid"
        );
    }
    let mut large: Value = serde_json::from_str(&edit_input(PROFILE_ID, &unit)).unwrap();
    large["submission"]["scalar_intents"][0]["value"] = json!("1".repeat(person::REQUEST_LIMIT));
    assert_eq!(
        financial_submission("modelo.edit.apply", &unit, Wiped(large))
            .unwrap_err()
            .code,
        "too_large"
    );
}

#[test]
fn a_named_read_is_passed_on_only_for_this_profile_declaration_and_language() {
    let unit = hex('a');
    let form = json!({"result_version":1, "profile_id":PROFILE_ID, "work_unit_id":unit,
        "form":{"form":{"sections":[]}}, "registry_revision_id":"303-2026"});
    assert_eq!(
        read_answer(form.clone(), PROFILE_ID, Some(&unit), None).unwrap(),
        form,
        "the read model reaches the window unchanged"
    );
    let list = json!({"result_version":1, "profile_id":PROFILE_ID, "output_language":"es",
        "rows":[]});
    assert!(read_answer(list.clone(), PROFILE_ID, None, Some("es")).is_ok());
    assert!(read_answer(list, PROFILE_ID, None, Some("ca")).is_err());
    assert!(read_answer(form.clone(), PROFILE_ID, Some(&hex('b')), None).is_err());
    assert!(
        read_answer(
            form.clone(),
            "22222222-2222-4222-8222-222222222222",
            Some(&unit),
            None
        )
        .is_err()
    );
    let mut future = form;
    future["result_version"] = json!(2);
    assert!(read_answer(future, PROFILE_ID, Some(&unit), None).is_err());
}

#[test]
fn dialog_words_and_read_references_are_bounded() {
    assert!(label_admitted("Fichero BOE"));
    assert!(!label_admitted(""));
    assert!(!label_admitted(&"a".repeat(LABEL_LIMIT + 1)));
    assert!(!label_admitted("a\nb"));
    assert!(file_name_admitted("modelo-303-2026-3T.txt"));
    for name in ["..\\x.txt", "a/b.txt", "C:x.txt", ".hidden"] {
        assert!(!file_name_admitted(name), "{name}");
    }
    assert!(reference_admitted("01"));
    assert!(!reference_admitted(" "));
    assert!(!reference_admitted(&"a".repeat(REFERENCE_LIMIT + 1)));
    assert!(work_unit_admitted(&hex('a')));
    assert!(!work_unit_admitted("a"));
}

#[cfg(windows)]
mod relayed {
    use super::super::scripted::{OPERATION, PROFILE, holder, observed, resulted, step};
    use super::*;

    #[tokio::test]
    async fn a_profile_less_request_is_submitted_on_its_work_unit_and_settles() {
        let unit = hex('a');
        let held = holder(|_| {
            vec![
                step(
                    "operation_submit",
                    json!([
                        ["definition_id", "modelo.work.calculate"],
                        ["subject_ref", unit.clone()],
                        ["payload.work_unit_id", unit.clone()],
                        ["payload.profile_id", ""]
                    ]),
                    json!({"kind":"operation_submitted","operation_id":OPERATION}),
                    false,
                ),
                step(
                    "operation_observe",
                    json!([["operation_id", OPERATION]]),
                    observed(
                        "modelo.work.calculate",
                        &unit,
                        "terminal",
                        json!({"terminal_condition":"succeeded","effect":"updated","revision":2}),
                    ),
                    false,
                ),
                step(
                    "operation_result",
                    json!([]),
                    resulted(
                        "modelo.work.calculate",
                        json!({"calculation_revision_id":"r-1"}),
                    ),
                    false,
                ),
            ]
        });
        let definition = definition("modelo.work.calculate");
        let (request, subject) = plain_submission(
            definition,
            PROFILE,
            Wiped(json!({"work_unit_id":unit, "actor":"desktop"})),
            None,
        )
        .unwrap();
        let operations = Operations::default();
        let mut events = held.events.subscribe();
        let outcome = submit_on(
            &operations,
            &held.person,
            held.identity.clone(),
            &mut events,
            definition,
            subject,
            request,
        )
        .await
        .unwrap();
        assert_eq!(
            outcome,
            Outcome::Settled {
                operation_id: OPERATION.into(),
                revision: 2,
                result: json!({"calculation_revision_id":"r-1"}),
            }
        );
        assert_eq!(operations.find(OPERATION).unwrap().subject, unit);
    }

    #[tokio::test]
    async fn an_edits_amounts_reach_the_relay_only_as_its_financial_operand() {
        let unit = hex('a');
        let held = holder(|_| {
            vec![
                step(
                    "operation_financial_submit",
                    json!([
                        ["definition_id", "modelo.edit.preflight"],
                        ["subject_ref", unit.clone()],
                        ["input.input_version", 2],
                        ["input.submission.baseline.bucket_id", PROFILE],
                        ["input.submission.scalar_intents.value", "1234.56"],
                        ["payload", ""]
                    ]),
                    json!({"kind":"operation_submitted","operation_id":OPERATION}),
                    false,
                ),
                step(
                    "operation_observe",
                    json!([]),
                    observed(
                        "modelo.edit.preflight",
                        &unit,
                        "terminal",
                        json!({"terminal_condition":"succeeded"}),
                    ),
                    false,
                ),
                step(
                    "operation_result",
                    json!([]),
                    resulted(
                        "modelo.edit.preflight",
                        json!({"result_version":1,"profile_id":PROFILE,"work_unit_id":unit,
                            "outcome":{"outcome":"evaluated"}}),
                    ),
                    false,
                ),
            ]
        });
        let body = InvokeBody::Raw(edit_input(PROFILE, &unit).into_bytes());
        let (input, work_unit) = financial_body(&body, PROFILE).unwrap();
        let definition = definition("modelo.edit.preflight");
        let request = financial_submission(definition.id, &work_unit, input).unwrap();
        let operations = Operations::default();
        let mut events = held.events.subscribe();
        let outcome = submit_on(
            &operations,
            &held.person,
            held.identity.clone(),
            &mut events,
            definition,
            work_unit,
            request,
        )
        .await
        .unwrap();
        let Outcome::Settled { result, .. } = outcome else {
            panic!("the preflight settled");
        };
        assert!(
            !result.to_string().contains("1234.56"),
            "the window's amounts are not echoed back here"
        );
    }

    #[tokio::test]
    async fn a_refused_submission_keeps_its_code_and_tracks_nothing() {
        let held = holder(|_| {
            vec![step(
                "operation_submit",
                json!([["subject_ref", hex('c')]]),
                json!({"kind":"operation_refused","code":"subject_busy","holder_operation_id":null}),
                false,
            )]
        });
        let definition = definition("modelo.export");
        let (request, subject) = plain_submission(
            definition,
            PROFILE,
            Wiped(json!({"calculation_revision_id":"r-1"})),
            Some(&hex('c')),
        )
        .unwrap();
        let operations = Operations::default();
        let mut events = held.events.subscribe();
        let refused = submit_on(
            &operations,
            &held.person,
            held.identity.clone(),
            &mut events,
            definition,
            subject,
            request,
        )
        .await
        .unwrap_err();
        assert_eq!(refused.code, "refused");
        assert_eq!(refused.reason.as_deref(), Some("subject_busy"));
        assert!(operations.find(OPERATION).is_err());
    }
}
