use super::framing::{base64_decode, document, is_uuid, text};
use super::refusal::Refusal;
#[cfg(windows)]
use cadrumo_platform::runtime_pipe;
use serde_json::Value;
use std::io;
use std::path::Path;
use std::time::Instant;
use zeroize::Zeroizing;

pub(super) const RECEIPT_RECORD_MAX_BYTES: u64 = 8 * 1024;

pub(super) const RECEIPT_FILENAME: &str = "session.v2.json";

pub(super) const KEYSTORE_DIRECTORY: &str = "keystore";

pub(super) const RECEIPT_KEYCHAIN_SERVICE: &str = "cadrumo:profile-session:v2";

pub(super) const RECEIPT_KEY_BYTES: usize = 32;

/// Presentations of one resume; each after the first needs a proof that
/// changed since the last refusal.
pub(super) const RECEIPT_PROOF_ATTEMPTS: usize = 3;

/// The persisted-session refusal reasons a runtime may name for a presented receipt.
pub(super) const RECEIPT_REFUSAL_REASONS: [&str; 9] = [
    "absent",
    "malformed",
    "schema_version_mismatch",
    "expired_idle",
    "expired_absolute",
    "keychain_entry_missing",
    "keyring_unavailable",
    "custody_changed",
    "tampered",
];

/// Reads the stored sign-in's proof and has `present` offer it to the runtime.
///
/// A sign-in that completes between reading the proof and the runtime's check
/// replaces the receipt, so the proof read before it no longer unwraps the one
/// the runtime reads. Such a refusal is retried with a fresh read, a bounded
/// number of times and only while the proof differs from the one refused.
pub(super) fn present_stored_proof<T>(
    storage_root: &Path,
    profile_id: &str,
    deadline: Instant,
    closed: impl Fn() -> bool,
    present: impl Fn(&[u8]) -> Result<T, Refusal>,
) -> Result<T, ResumeRefusal> {
    let mut presented: Option<Zeroizing<Vec<u8>>> = None;
    for attempt in 1..=RECEIPT_PROOF_ATTEMPTS {
        let proof = stored_sign_in_proof(storage_root, profile_id)
            .map_err(|refusal| ResumeRefusal::Receipt(refusal.code().to_owned()))?;
        if presented
            .as_ref()
            .is_some_and(|refused| **refused == *proof)
        {
            // No sign-in replaced the receipt: the proof was refused for itself.
            return Err(ResumeRefusal::Receipt("tampered".to_owned()));
        }
        let refusal = match present(&proof) {
            Ok(admitted) => return Ok(admitted),
            Err(refusal) => refusal,
        };
        let Some(reason) = receipt_refusal(&refusal) else {
            return Err(ResumeRefusal::Runtime(refusal));
        };
        if reason != "tampered"
            || attempt == RECEIPT_PROOF_ATTEMPTS
            || Instant::now() >= deadline
            || closed()
        {
            return Err(ResumeRefusal::Receipt(reason.to_owned()));
        }
        presented = Some(proof);
    }
    Err(ResumeRefusal::Receipt("tampered".to_owned()))
}

/// Why a stored sign-in was not resumed.
#[derive(Debug)]
pub enum ResumeRefusal {
    /// The receipt does not sign this login in, by its persisted-session
    /// refusal reason: none is stored, it could not be read, or the runtime
    /// refused it.
    Receipt(String),
    /// The runtime could not be asked, or refused for another reason.
    Runtime(Refusal),
}

impl ResumeRefusal {
    pub fn code(&self) -> &str {
        match self {
            Self::Receipt(reason) => reason,
            Self::Runtime(refusal) => refusal.code(),
        }
    }
}

impl std::fmt::Display for ResumeRefusal {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Receipt(reason) => write!(formatter, "receipt_refused: {reason}"),
            Self::Runtime(refusal) => refusal.fmt(formatter),
        }
    }
}

impl std::error::Error for ResumeRefusal {}

/// The receipt refusal a runtime denial of a presented receipt stands for,
/// if it is one: the sign-in reason it names, or the denial's own meaning.
pub(super) fn receipt_refusal(refusal: &Refusal) -> Option<&str> {
    if let Some(reason) = refusal
        .sign_in_reason()
        .filter(|reason| RECEIPT_REFUSAL_REASONS.contains(reason))
    {
        return Some(reason);
    }
    match refusal {
        Refusal::Denied { code, .. } => match code.as_str() {
            // The runtime deleted a receipt that no longer signs this login in.
            "authentication_required" => Some("absent"),
            // The denial does not distinguish idle from absolute expiry.
            "session_expired" => Some("expired_idle"),
            "custody_changed" => Some("custody_changed"),
            "credential_rejected" => Some("tampered"),
            _ => None,
        },
        _ => None,
    }
}

/// Why no proof of a stored sign-in could be read. The names are the
/// runtime's own refusal reasons for the same states.
#[derive(Debug, PartialEq, Eq)]
pub enum ProofRefusal {
    /// The profile holds no stored sign-in.
    Absent,
    /// The receipt names a credential-store entry that is not there.
    KeychainEntryMissing,
    /// The credential store could not be read.
    KeyringUnavailable,
    /// The receipt or its entry is not what a runtime writes.
    Malformed,
    /// The receipt names another profile.
    Tampered,
}

impl ProofRefusal {
    pub fn code(&self) -> &'static str {
        match self {
            Self::Absent => "absent",
            Self::KeychainEntryMissing => "keychain_entry_missing",
            Self::KeyringUnavailable => "keyring_unavailable",
            Self::Malformed => "malformed",
            Self::Tampered => "tampered",
        }
    }
}

/// The receipt locator: the profile and session that name its credential-store half.
#[derive(Debug, PartialEq, Eq)]
pub struct ReceiptLocator {
    pub profile_id: String,
    pub session_id: String,
}

/// Reads the schema-independent locator of the receipt bytes a runtime wrote.
pub fn receipt_locator(payload: &[u8], profile_id: &str) -> Result<ReceiptLocator, ProofRefusal> {
    let document = document(payload).map_err(|_| ProofRefusal::Malformed)?;
    if document
        .get("schema_version")
        .and_then(Value::as_u64)
        .is_none_or(|version| version == 0)
    {
        return Err(ProofRefusal::Malformed);
    }
    let named = text(&document, "profile_id")
        .filter(|id| is_uuid(id))
        .ok_or(ProofRefusal::Malformed)?;
    let session_id = text(&document, "session_id")
        .filter(|id| is_uuid(id))
        .ok_or(ProofRefusal::Malformed)?;
    if named != profile_id {
        return Err(ProofRefusal::Tampered);
    }
    Ok(ReceiptLocator {
        profile_id: named.to_owned(),
        session_id: session_id.to_owned(),
    })
}

/// The credential-store account a receipt's key is stored under.
pub fn receipt_account(locator: &ReceiptLocator) -> String {
    format!("{}:{}", locator.profile_id, locator.session_id)
}

/// Decodes a stored key as the runtime's keyring writes it: the base64 text
/// of 32 bytes, as UTF-16 or UTF-8.
pub(super) fn decode_stored_key(blob: &[u8]) -> Result<Zeroizing<Vec<u8>>, ProofRefusal> {
    let utf16 = blob.len().is_multiple_of(2).then(|| {
        let units: Vec<u16> = blob
            .as_chunks::<2>()
            .0
            .iter()
            .map(|pair| u16::from_le_bytes(*pair))
            .collect();
        Zeroizing::new(String::from_utf16(&units).unwrap_or_default())
    });
    let utf8 = Zeroizing::new(String::from_utf8(blob.to_vec()).unwrap_or_default());
    let key = utf16
        .as_deref()
        .and_then(|encoded| base64_decode(encoded))
        .or_else(|| base64_decode(&utf8))
        .map(Zeroizing::new)
        .ok_or(ProofRefusal::Malformed)?;
    if key.len() != RECEIPT_KEY_BYTES {
        return Err(ProofRefusal::Malformed);
    }
    Ok(key)
}

/// The proof of `profile_id`'s stored sign-in under `storage_root`: the key
/// its receipt names in this user's credential store. Nothing is decrypted,
/// unwrapped, evaluated or deleted; the runtime does all of that when the
/// proof is presented. The caller presents the key once and drops it.
pub fn stored_sign_in_proof(
    storage_root: &Path,
    profile_id: &str,
) -> Result<Zeroizing<Vec<u8>>, ProofRefusal> {
    if !is_uuid(profile_id) {
        return Err(ProofRefusal::Malformed);
    }
    let path = storage_root
        .join(KEYSTORE_DIRECTORY)
        .join(profile_id)
        .join(RECEIPT_FILENAME);
    let metadata = match std::fs::symlink_metadata(&path) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Err(ProofRefusal::Absent),
        Err(_) => return Err(ProofRefusal::Malformed),
    };
    if !metadata.is_file() || metadata.len() > RECEIPT_RECORD_MAX_BYTES {
        return Err(ProofRefusal::Malformed);
    }
    let payload = std::fs::read(&path).map_err(|error| {
        if error.kind() == io::ErrorKind::NotFound {
            ProofRefusal::Absent
        } else {
            ProofRefusal::Malformed
        }
    })?;
    let locator = receipt_locator(&payload, profile_id)?;
    let blob = stored_key(&receipt_account(&locator))?;
    decode_stored_key(&blob)
}

/// The stored key's bytes, as the keyring wrote them for `account`.
#[cfg(windows)]
pub(super) fn stored_key(account: &str) -> Result<Zeroizing<Vec<u8>>, ProofRefusal> {
    let read = |target: &str| {
        runtime_pipe::read_generic_credential(target).map_err(|_| ProofRefusal::KeyringUnavailable)
    };
    // The keyring stores one entry under the service name and the rest under
    // `account@service`; the service entry answers only for its own account.
    let stored = match read(RECEIPT_KEYCHAIN_SERVICE)? {
        Some(credential) if credential.user_name == account => Some(credential),
        _ => read(&format!("{account}@{RECEIPT_KEYCHAIN_SERVICE}"))?,
    };
    let credential = stored.ok_or(ProofRefusal::KeychainEntryMissing)?;
    Ok(Zeroizing::new(credential.blob))
}

/// The stored key's bytes, as the keyring wrote them for `account`. An item this
/// program may not read without asking is unavailable, never a prompt.
#[cfg(target_os = "macos")]
pub(super) fn stored_key(account: &str) -> Result<Zeroizing<Vec<u8>>, ProofRefusal> {
    cadrumo_platform::keychain::read_generic_password(RECEIPT_KEYCHAIN_SERVICE, account)
        .map_err(|_| ProofRefusal::KeyringUnavailable)?
        .map(Zeroizing::new)
        .ok_or(ProofRefusal::KeychainEntryMissing)
}

/// This platform's credential store is not read natively yet; a stored sign-in falls
/// back to the password.
#[cfg(all(unix, not(target_os = "macos")))]
pub(super) fn stored_key(_account: &str) -> Result<Zeroizing<Vec<u8>>, ProofRefusal> {
    Err(ProofRefusal::KeyringUnavailable)
}
