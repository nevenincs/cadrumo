//! Native publication ACL and namespace admission, before any state is created.
#![allow(unsafe_code)]
use crate::admission::Refusal;
use cadrumo_application::installation::maintenance::NativeContext;
use std::{
    ffi::c_void,
    fs::{self, File},
    os::windows::{
        fs::{MetadataExt, OpenOptionsExt},
        io::AsRawHandle,
    },
    path::{Component, Path, Prefix},
    ptr,
};
use windows_sys::Win32::{
    Foundation::*,
    Security::{Authorization::*, *},
    Storage::FileSystem::*,
};

const SYSTEM: &str = "S-1-5-18";
const ADMINISTRATORS: &str = "S-1-5-32-544";
const OWNER_RIGHTS: &str = "S-1-3-4";
const MAXIMUM_ENTRIES: usize = 100_000;
const ACCESS_ALLOWED_ACE_TYPE: u8 = 0;
const ACCESS_DENIED_ACE_TYPE: u8 = 1;
const NAMESPACE_MUTATION: u32 = DELETE
    | WRITE_DAC
    | WRITE_OWNER
    | FILE_DELETE_CHILD
    | GENERIC_ALL
    | GENERIC_WRITE
    | FILE_WRITE_DATA
    | FILE_WRITE_EA
    | FILE_WRITE_ATTRIBUTES;
const CONTENT_MUTATION: u32 = NAMESPACE_MUTATION
    | GENERIC_WRITE
    | FILE_WRITE_DATA
    | FILE_APPEND_DATA
    | FILE_WRITE_EA
    | FILE_WRITE_ATTRIBUTES;

struct Local(*mut c_void);
impl Drop for Local {
    fn drop(&mut self) {
        // SAFETY: memory comes from LocalAlloc-backed security APIs.
        unsafe {
            LocalFree(self.0);
        }
    }
}

fn wide(value: &str) -> Result<Vec<u16>, Refusal> {
    if value.contains('\0') {
        return Err(Refusal::InvalidRequest);
    }
    Ok(value.encode_utf16().chain([0]).collect())
}

fn sid_text(sid: PSID) -> Result<String, Refusal> {
    // SAFETY: caller supplies a SID in a validated native security descriptor.
    if unsafe { IsValidSid(sid) } == 0 {
        return Err(Refusal::NativeFailure);
    }
    let mut text = ptr::null_mut();
    // SAFETY: valid SID and writable allocation output.
    if unsafe { ConvertSidToStringSidW(sid, &mut text) } == 0 {
        return Err(Refusal::NativeFailure);
    }
    let _allocation = Local(text.cast());
    let mut length = 0;
    // SAFETY: conversion returned a terminated SID string with bounded length.
    while length < 184 && unsafe { *text.add(length) } != 0 {
        length += 1;
    }
    if length == 184 {
        return Err(Refusal::NativeFailure);
    }
    // SAFETY: the preceding scan established the readable extent.
    String::from_utf16(unsafe { std::slice::from_raw_parts(text, length) })
        .map_err(|_| Refusal::NativeFailure)
}

fn trusted_installer() -> Result<String, Refusal> {
    let account = wide(r"NT SERVICE\TrustedInstaller")?;
    let mut storage = [0_usize; 16];
    let mut size = size_of_val(&storage) as u32;
    let mut domain = [0; 256];
    let mut domain_size = domain.len() as u32;
    let mut usage = 0;
    // SAFETY: exact local service account, bounded aligned SID/domain outputs.
    if unsafe {
        LookupAccountNameW(
            ptr::null(),
            account.as_ptr(),
            storage.as_mut_ptr().cast(),
            &mut size,
            domain.as_mut_ptr(),
            &mut domain_size,
            &mut usage,
        )
    } == 0
    {
        return Err(Refusal::NativeFailure);
    }
    sid_text(storage.as_mut_ptr().cast())
}

struct Policy<'a> {
    context: &'a NativeContext,
    installer: String,
}
impl Policy<'_> {
    fn trusted(&self, sid: &str) -> bool {
        matches!(sid, SYSTEM | ADMINISTRATORS)
            || sid == self.installer
            || matches!(self.context, NativeContext::User { sid: owner } if owner == sid)
    }

    fn admit(&self, file: &File, content: bool) -> Result<(), Refusal> {
        let mut owner = ptr::null_mut();
        let mut dacl = ptr::null_mut();
        let mut descriptor = ptr::null_mut();
        // SAFETY: live handle with READ_CONTROL; all security outputs are writable.
        let status = unsafe {
            GetSecurityInfo(
                file.as_raw_handle(),
                SE_FILE_OBJECT,
                OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION,
                &mut owner,
                ptr::null_mut(),
                &mut dacl,
                ptr::null_mut(),
                &mut descriptor,
            )
        };
        if status != ERROR_SUCCESS {
            return Err(Refusal::IncompleteInventory);
        }
        let _descriptor = Local(descriptor);
        if owner.is_null() || dacl.is_null() {
            return Err(Refusal::InvalidRequest);
        }
        let owner = sid_text(owner)?;
        let mutation = if content {
            CONTENT_MUTATION
        } else {
            NAMESPACE_MUTATION
        };
        let mut owner_restricted = false;
        let required_read = FILE_GENERIC_READ
            | if file
                .metadata()
                .map_err(|_| Refusal::IncompleteInventory)?
                .is_dir()
            {
                FILE_TRAVERSE
            } else {
                0
            };
        let mut readable = false;
        // SAFETY: GetSecurityInfo supplied a valid ACL in the retained descriptor.
        let count = unsafe { (*dacl).AceCount };
        if count > 1024 {
            return Err(Refusal::IncompleteInventory);
        }
        for index in 0..u32::from(count) {
            let mut address = ptr::null_mut();
            // SAFETY: bounded ACE index in a valid live ACL, writable pointer output.
            if unsafe { GetAce(dacl, index, &mut address) } == 0 {
                return Err(Refusal::NativeFailure);
            }
            // SAFETY: native ACL validates the returned ACE header and extent.
            let header = unsafe { &*address.cast::<ACE_HEADER>() };
            if u32::from(header.AceFlags) & INHERIT_ONLY_ACE != 0 {
                continue;
            }
            if !matches!(
                header.AceType,
                ACCESS_ALLOWED_ACE_TYPE | ACCESS_DENIED_ACE_TYPE
            ) || usize::from(header.AceSize) < size_of::<ACCESS_ALLOWED_ACE>()
            {
                return Err(Refusal::InvalidRequest);
            }
            // SAFETY: these two ACE variants share Mask and SidStart layout.
            let ace = unsafe { &*address.cast::<ACCESS_ALLOWED_ACE>() };
            let sid = sid_text(ptr::from_ref(&ace.SidStart).cast_mut().cast())?;
            let mut effective = ace.Mask;
            if effective & GENERIC_ALL != 0 {
                effective = u32::MAX;
            }
            if effective & GENERIC_READ != 0 {
                effective |= FILE_GENERIC_READ;
            }
            if effective & GENERIC_EXECUTE != 0 {
                effective |= FILE_GENERIC_EXECUTE;
            }
            if header.AceType == ACCESS_DENIED_ACE_TYPE && effective & required_read != 0 {
                return Err(Refusal::InvalidRequest);
            }
            let reader = matches!(sid.as_str(), "S-1-5-11" | "S-1-1-0" | "S-1-5-32-545")
                || matches!(self.context, NativeContext::User { sid: user } if user == &sid);
            if header.AceType == ACCESS_ALLOWED_ACE_TYPE
                && reader
                && effective & required_read == required_read
            {
                readable = true;
            }
            if sid == OWNER_RIGHTS {
                owner_restricted = true;
            }
            if header.AceType == ACCESS_ALLOWED_ACE_TYPE
                && !self.trusted(&sid)
                && ace.Mask & mutation != 0
            {
                return Err(Refusal::InvalidRequest);
            }
        }
        // An untrusted owner has implicit WRITE_DAC unless OWNER_RIGHTS appears
        // as an effective ACE. File creation by an elevated user must not grant
        // the user's limited token authority to rewrite machine publication ACLs.
        if (!self.trusted(&owner) && !owner_restricted) || !readable {
            return Err(Refusal::InvalidRequest);
        }
        Ok(())
    }
}

fn open(path: &Path, directory: bool) -> Result<File, Refusal> {
    let file = File::options()
        .access_mode(READ_CONTROL)
        .share_mode(3)
        .custom_flags(
            FILE_FLAG_OPEN_REPARSE_POINT
                | if directory {
                    FILE_FLAG_BACKUP_SEMANTICS
                } else {
                    0
                },
        )
        .open(path)
        .map_err(|_| Refusal::IncompleteInventory)?;
    let metadata = file.metadata().map_err(|_| Refusal::IncompleteInventory)?;
    if metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0
        || metadata.is_dir() != directory
        || (!directory && !metadata.is_file())
    {
        return Err(Refusal::InvalidRequest);
    }
    Ok(file)
}

fn create(path: &Path, context: &NativeContext) -> Result<(), Refusal> {
    let owner = match context {
        NativeContext::Machine => "BA",
        NativeContext::User { sid } => sid,
    };
    let user = match context {
        NativeContext::Machine => String::new(),
        NativeContext::User { sid } => format!("(A;OICI;FA;;;{sid})"),
    };
    let sddl = wide(&format!(
        "O:{owner}G:BAD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA){user}(A;OICI;0x1200a9;;;BU)(A;OICI;RC;;;OW)"
    ))?;
    let mut descriptor = ptr::null_mut();
    // SAFETY: context SID is native-derived and validated by NativeOwner admission.
    if unsafe {
        ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl.as_ptr(),
            1,
            &mut descriptor,
            ptr::null_mut(),
        )
    } == 0
    {
        return Err(Refusal::NativeFailure);
    }
    let _descriptor = Local(descriptor);
    let attributes = SECURITY_ATTRIBUTES {
        nLength: size_of::<SECURITY_ATTRIBUTES>() as u32,
        lpSecurityDescriptor: descriptor,
        bInheritHandle: 0,
    };
    let name = wide(path.to_str().ok_or(Refusal::InvalidRequest)?)?;
    // SAFETY: creates only the explicit directory with its ACL atomically attached.
    if unsafe { CreateDirectoryW(name.as_ptr(), &attributes) } == 0 {
        // SAFETY: inspect this creation result before any other native call.
        if unsafe { GetLastError() } != ERROR_ALREADY_EXISTS {
            return Err(Refusal::NativeFailure);
        }
    }
    Ok(())
}

#[must_use = "hold namespace custody throughout native maintenance"]
pub struct PublicationCustody {
    _directories: Vec<File>,
}

/// Refuses unsafe existing ACLs and reparse ancestry rather than repairing them.
/// Readers receive read/traverse rights, including existing kernel lease files.
pub fn prepare(
    prefix: &Path,
    publication: &Path,
    context: &NativeContext,
) -> Result<PublicationCustody, Refusal> {
    admit(prefix, publication, context, true)
}

/// Custom actions may inspect an owner's namespace but must never establish or
/// repair its authority. Missing paths are refused without filesystem mutation.
pub fn admit_existing(
    prefix: &Path,
    publication: &Path,
    context: &NativeContext,
) -> Result<PublicationCustody, Refusal> {
    admit(prefix, publication, context, false)
}

fn admit(
    prefix: &Path,
    publication: &Path,
    context: &NativeContext,
    create_missing: bool,
) -> Result<PublicationCustody, Refusal> {
    cadrumo_application::installation::maintenance::NativeOwner::new(
        "00000000-0000-0000-0000-000000000001".into(),
        context.clone(),
        prefix.to_owned(),
    )
    .map_err(|_| Refusal::InvalidRequest)?;
    if !prefix.is_absolute()
        || prefix.parent().is_none()
        || prefix == publication
        || !publication.starts_with(prefix)
        || !matches!(prefix.components().next(), Some(Component::Prefix(value)) if matches!(value.kind(), Prefix::Disk(_) | Prefix::VerbatimDisk(_)))
        || publication
            .components()
            .any(|part| matches!(part, Component::ParentDir))
    {
        return Err(Refusal::InvalidRequest);
    }
    let policy = Policy {
        context,
        installer: trusted_installer()?,
    };
    let mut ancestry = publication.ancestors().collect::<Vec<_>>();
    ancestry.reverse();
    let volume = wide(ancestry[0].to_str().ok_or(Refusal::InvalidRequest)?)?;
    // SAFETY: terminated absolute volume root; network/removable publication is refused.
    if unsafe { GetDriveTypeW(volume.as_ptr()) } != 3 {
        return Err(Refusal::InvalidRequest);
    }
    let mut directories = Vec::new();
    for path in ancestry {
        let inside = path.starts_with(prefix);
        if !path
            .try_exists()
            .map_err(|_| Refusal::IncompleteInventory)?
        {
            if !inside || !create_missing {
                return Err(Refusal::InvalidRequest);
            }
            create(path, context)?;
        }
        let directory = open(path, true)?;
        policy.admit(&directory, inside)?;
        directories.push(directory);
    }
    // Existing files may retain noninherited write grants or implicit owner
    // rights, even beneath a safe parent. Check every existing native member.
    let mut remaining = vec![prefix.to_owned()];
    let mut observed = 0;
    while let Some(directory) = remaining.pop() {
        for entry in fs::read_dir(&directory).map_err(|_| Refusal::IncompleteInventory)? {
            observed += 1;
            if observed > MAXIMUM_ENTRIES {
                return Err(Refusal::IncompleteInventory);
            }
            let entry = entry.map_err(|_| Refusal::IncompleteInventory)?;
            let kind = entry
                .file_type()
                .map_err(|_| Refusal::IncompleteInventory)?;
            let file = open(&entry.path(), kind.is_dir())?;
            policy.admit(&file, true)?;
            if kind.is_dir() {
                remaining.push(entry.path());
            }
        }
    }
    Ok(PublicationCustody {
        _directories: directories,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn standard_machine_program_files_ancestry_is_admitted_without_modification() {
        if crate::windows::installation_context(crate::admission::Scope::Machine).is_err() {
            return;
        }
        let path = std::path::PathBuf::from(
            std::env::var_os("ProgramFiles").expect("Windows Program Files directory"),
        );
        let policy = Policy {
            context: &NativeContext::Machine,
            installer: trusted_installer().unwrap(),
        };
        for ancestor in path.ancestors() {
            policy.admit(&open(ancestor, true).unwrap(), false).unwrap();
        }
    }
    #[test]
    fn native_user_publication_is_readable_and_machine_reuse_refuses_user_namespace() {
        let context = crate::windows::installation_context(crate::admission::Scope::User).unwrap();
        // The shared OS temp directory may intentionally grant other sandbox
        // accounts Modify rights. That namespace is correctly inadmissible.
        let local = std::env::var_os("LOCALAPPDATA").expect("Windows user local data directory");
        let root = tempfile::tempdir_in(local).unwrap();
        let prefix = root.path().join("installed");
        let state = prefix.join("data/installation-state");
        assert!(admit_existing(&prefix, &state, &context).is_err());
        assert!(!prefix.exists());
        let custody = prepare(&prefix, &state, &context).unwrap();
        let observer = admit_existing(&prefix, &state, &context).unwrap();
        drop(observer);
        fs::write(state.join("transaction.lock"), b"").unwrap();
        let policy = Policy {
            context: &context,
            installer: trusted_installer().unwrap(),
        };
        policy
            .admit(&open(&state.join("transaction.lock"), false).unwrap(), true)
            .unwrap();
        let reader = File::options()
            .read(true)
            .open(state.join("transaction.lock"))
            .unwrap();
        reader.try_lock_shared().unwrap();
        reader.unlock().unwrap();
        drop(reader);
        assert!(fs::rename(&prefix, root.path().join("renamed")).is_err());
        drop(custody);
        assert!(prepare(&prefix, &state, &NativeContext::Machine).is_err());
        assert!(prepare(&prefix, &root.path().join("outside"), &context).is_err());
    }

    #[test]
    fn machine_acl_rejects_implicit_owner_and_accepts_owner_rights_restriction() {
        let NativeContext::User { sid } =
            crate::windows::installation_context(crate::admission::Scope::User).unwrap()
        else {
            unreachable!()
        };
        let root = tempfile::tempdir().unwrap();
        let policy = Policy {
            context: &NativeContext::Machine,
            installer: trusted_installer().unwrap(),
        };
        // Construct real filesystem descriptors with the current user as owner,
        // but grants only for administrators/system and read-only ordinary users.
        for (name, owner_rights, admitted) in [
            ("implicit", "", false),
            ("restricted", "(A;OICI;RC;;;OW)", true),
        ] {
            let sddl = wide(&format!(
                "O:{sid}D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;0x1200a9;;;BU){owner_rights}"
            ))
            .unwrap();
            let mut descriptor = ptr::null_mut();
            // SAFETY: fixed SDDL and native current SID; writable allocation output.
            assert_ne!(
                unsafe {
                    ConvertStringSecurityDescriptorToSecurityDescriptorW(
                        sddl.as_ptr(),
                        1,
                        &mut descriptor,
                        ptr::null_mut(),
                    )
                },
                0
            );
            let _descriptor = Local(descriptor);
            let attributes = SECURITY_ATTRIBUTES {
                nLength: size_of::<SECURITY_ATTRIBUTES>() as u32,
                lpSecurityDescriptor: descriptor,
                bInheritHandle: 0,
            };
            let path = root.path().join(name);
            let path_wide = wide(path.to_str().unwrap()).unwrap();
            // SAFETY: isolated test directory receives the exact descriptor at creation.
            assert_ne!(
                unsafe { CreateDirectoryW(path_wide.as_ptr(), &attributes) },
                0
            );
            assert_eq!(
                policy.admit(&open(&path, true).unwrap(), true).is_ok(),
                admitted
            );
        }
    }
}
