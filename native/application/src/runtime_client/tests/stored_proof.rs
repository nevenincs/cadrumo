use super::super::refusal::Refusal;
use super::super::stored_proof::{
    KEYSTORE_DIRECTORY, ProofRefusal, RECEIPT_FILENAME, decode_stored_key, receipt_account,
    receipt_locator, receipt_refusal, stored_sign_in_proof,
};
use serde_json::json;

#[test]
fn a_refused_receipt_reads_as_its_receipt_reason_and_other_refusals_do_not() {
    let named = Refusal::Denied {
        code: "authentication_required".into(),
        sign_in: Some(json!({"reason": "expired_absolute"})),
        holder_operation_id: None,
        recovery_remaining_seconds: None,
    };
    assert_eq!(receipt_refusal(&named), Some("expired_absolute"));
    for (code, reason) in [
        ("authentication_required", "absent"),
        ("session_expired", "expired_idle"),
        ("custody_changed", "custody_changed"),
        ("credential_rejected", "tampered"),
    ] {
        assert_eq!(
            receipt_refusal(&Refusal::denied(code)),
            Some(reason),
            "{code}"
        );
    }
    let throttled = Refusal::Denied {
        code: "credential_rejected".into(),
        sign_in: Some(json!({"reason": "throttled", "remaining_seconds": 30})),
        holder_operation_id: None,
        recovery_remaining_seconds: None,
    };
    assert_eq!(receipt_refusal(&throttled), Some("tampered"));
    assert_eq!(receipt_refusal(&Refusal::denied("profile_locked")), None);
    assert_eq!(receipt_refusal(&Refusal::ConnectionClosed), None);
}

#[test]
fn a_receipt_locator_names_its_profile_and_session_or_is_refused() {
    let profile = "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d";
    let session = "1a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d";
    let payload = format!(
        r#"{{"profile_id":"{profile}","schema_version":3,"session_id":"{session}","wrapped":"x"}}"#
    );
    let locator = receipt_locator(payload.as_bytes(), profile).unwrap();
    assert_eq!(locator.session_id, session);
    assert_eq!(receipt_account(&locator), format!("{profile}:{session}"));
    assert_eq!(
        receipt_locator(payload.as_bytes(), "2a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d").unwrap_err(),
        ProofRefusal::Tampered
    );
    for malformed in [
        "",
        "[]",
        r#"{"profile_id":"x","session_id":"y","schema_version":1}"#,
    ] {
        assert_eq!(
            receipt_locator(malformed.as_bytes(), profile).unwrap_err(),
            ProofRefusal::Malformed
        );
    }
}

#[test]
fn a_stored_key_is_base64_text_in_utf16_or_utf8() {
    let encoded = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=";
    let utf16: Vec<u8> = encoded.encode_utf16().flat_map(u16::to_le_bytes).collect();
    assert_eq!(
        decode_stored_key(&utf16).unwrap().as_slice(),
        (0u8..32).collect::<Vec<_>>()
    );
    assert_eq!(decode_stored_key(encoded.as_bytes()).unwrap().len(), 32);
    assert_eq!(
        decode_stored_key(b"aGk=").unwrap_err(),
        ProofRefusal::Malformed
    );
    assert_eq!(
        decode_stored_key(&[0xff, 0xfe, 0xfd]).unwrap_err(),
        ProofRefusal::Malformed
    );
}

#[test]
fn a_profile_without_a_receipt_has_no_proof() {
    let root = std::env::temp_dir().join(format!("cadrumo-runtime-client-{}", std::process::id()));
    let profile = "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d";
    std::fs::create_dir_all(root.join(KEYSTORE_DIRECTORY).join(profile)).unwrap();
    assert_eq!(
        stored_sign_in_proof(&root, profile).unwrap_err(),
        ProofRefusal::Absent
    );
    assert_eq!(
        stored_sign_in_proof(&root, "not-a-profile").unwrap_err(),
        ProofRefusal::Malformed
    );
    let receipt = root
        .join(KEYSTORE_DIRECTORY)
        .join(profile)
        .join(RECEIPT_FILENAME);
    std::fs::write(&receipt, b"{}").unwrap();
    assert_eq!(
        stored_sign_in_proof(&root, profile).unwrap_err(),
        ProofRefusal::Malformed
    );
    std::fs::write(
        &receipt,
        format!(r#"{{"profile_id":"{profile}","schema_version":3,"session_id":"1a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d"}}"#),
    )
    .unwrap();
    // The locator is read; the entry it names was never stored.
    assert_eq!(
        stored_sign_in_proof(&root, profile).unwrap_err(),
        ProofRefusal::KeychainEntryMissing
    );
    let _ = std::fs::remove_dir_all(&root);
}
