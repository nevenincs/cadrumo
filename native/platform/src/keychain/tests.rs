use super::*;
use std::{
    process::Command,
    time::{Duration, Instant},
};

/// A service name no product entry uses, unique to this run.
fn service(purpose: &str) -> String {
    format!("cadrumo-platform-test:{purpose}:{}", std::process::id())
}

/// Stores an item as this program, through the same frameworks the read uses.
fn store_here(service: &str, account: &str, secret: &[u8]) {
    let frameworks = Frameworks::open().unwrap();
    // SAFETY: exact CoreFoundation and Security ABIs; the frameworks stay loaded.
    let (create_data, add) = unsafe {
        (
            std::mem::transmute::<
                *mut c_void,
                unsafe extern "C" fn(CfType, *const u8, isize) -> CfType,
            >(frameworks.foundation.symbol(c"CFDataCreate").unwrap()),
            std::mem::transmute::<*mut c_void, unsafe extern "C" fn(CfType, *mut CfType) -> i32>(
                frameworks.security.symbol(c"SecItemAdd").unwrap(),
            ),
        )
    };
    let service = frameworks.string(service).unwrap();
    let account = frameworks.string(account).unwrap();
    // SAFETY: the secret is valid for its stated length and copied.
    let data = frameworks
        .owned(unsafe { create_data(ptr::null(), secret.as_ptr(), secret.len() as isize) });
    let mut entries = frameworks.item(&service, &account).unwrap();
    entries.push((
        frameworks.security.constant(c"kSecValueData").unwrap(),
        data.value,
    ));
    let query = frameworks.dictionary(&entries).unwrap();
    // SAFETY: a live attribute dictionary; no result is requested.
    assert_eq!(unsafe { add(query.value, ptr::null_mut()) }, 0);
}

/// Stores an item as the system `security` tool, another program. `trust_any` gives it an
/// access list every program may use.
fn store_elsewhere(service: &str, account: &str, secret: &str, trust_any: bool) {
    let mut command = Command::new("/usr/bin/security");
    command.args([
        "add-generic-password",
        "-U",
        "-s",
        service,
        "-a",
        account,
        "-w",
        secret,
    ]);
    if trust_any {
        command.arg("-A");
    }
    assert!(command.status().unwrap().success());
}

fn remove(service: &str, account: &str) {
    let _ = Command::new("/usr/bin/security")
        .args(["delete-generic-password", "-s", service, "-a", account])
        .output();
}

#[test]
fn an_absent_item_is_absent() {
    assert_eq!(
        read_generic_password(&service("absent"), "nobody").unwrap(),
        None
    );
}

#[test]
#[ignore = "writes to this account's login keychain: run with --ignored on an unlocked desktop session"]
fn an_item_this_program_stored_is_read_back_exactly() {
    let service = service("own");
    store_here(&service, "profile:session", b"c2VjcmV0LWtleQ==");
    let read = read_generic_password(&service, "profile:session");
    let other = read_generic_password(&service, "other-account");
    remove(&service, "profile:session");
    assert_eq!(read.unwrap().as_deref(), Some(&b"c2VjcmV0LWtleQ=="[..]));
    assert_eq!(other.unwrap(), None);
}

#[test]
#[ignore = "writes to this account's login keychain: run with --ignored on an unlocked desktop session"]
fn an_item_another_program_stored_is_refused_without_a_prompt() {
    for trust_any in [false, true] {
        let service = service(if trust_any { "any" } else { "guarded" });
        store_elsewhere(&service, "profile:session", "c2VjcmV0LWtleQ==", trust_any);
        let started = Instant::now();
        let read = read_generic_password(&service, "profile:session");
        let elapsed = started.elapsed();
        remove(&service, "profile:session");
        assert!(read.is_err(), "{read:?}");
        // A prompt would hold the read until a person answered it.
        assert!(elapsed < Duration::from_secs(2), "{elapsed:?}");
    }
}
