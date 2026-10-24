use super::*;
use std::io::Cursor;
use zip::write::SimpleFileOptions;

enum Member<'a> {
    Folder(&'a str),
    File(&'a str, &'a [u8]),
    Link(&'a str, &'a str),
}
use Member::{File as F, Folder as D, Link as L};

fn zip_of(members: &[Member<'_>]) -> Vec<u8> {
    let mut zip = zip::ZipWriter::new(Cursor::new(Vec::new()));
    let options = SimpleFileOptions::default;
    for member in members {
        match member {
            D(name) => zip.add_directory(*name, options()).unwrap(),
            F(name, data) => {
                zip.start_file(*name, options().unix_permissions(0o644))
                    .unwrap();
                zip.write_all(data).unwrap();
            }
            L(name, target) => zip.add_symlink(*name, *target, options()).unwrap(),
        }
    }
    zip.finish().unwrap().into_inner()
}

const LIMITS: Limits = Limits {
    entries: 64,
    unpacked_bytes: 1_000_000,
};

/// Extracts `bytes` into a fresh folder two levels below a file named `outside`.
fn extract_zip(
    bytes: &[u8],
    rule: LinkRule,
) -> (
    tempfile::TempDir,
    std::path::PathBuf,
    Result<Extracted, Error>,
) {
    let directory = tempfile::tempdir().unwrap();
    fs::write(directory.path().join("outside"), b"outside").unwrap();
    let archive = directory.path().join("archive.zip");
    fs::write(&archive, bytes).unwrap();
    let destination = directory.path().join("build/inner");
    fs::create_dir_all(&destination).unwrap();
    let result = extract(
        &archive,
        ArchiveFormat::Zip,
        &destination,
        LIMITS,
        rule,
        &Cancellation::default(),
    );
    (directory, destination, result)
}

const LIBRARY: &[u8] = b"framework library bytes";

const FRAMEWORK: &str = "chrome-mac/App.app/Contents/Frameworks/F.framework";

/// The pinned macOS Chromium archive's links in miniature, in its own order: links
/// through `Versions/Current` come before that folder link, and one of them names a file.
fn framework() -> Vec<u8> {
    let at = |path: &str| format!("{FRAMEWORK}/{path}");
    let names = [
        at(""),
        at("Resources"),
        at("Versions/"),
        at("Versions/Current"),
        at("Versions/1.0/"),
        at("Versions/1.0/Resources/"),
        at("Versions/1.0/Resources/en.pak"),
        at("Versions/1.0/F"),
        at("F"),
        "chrome-mac/App.app/Contents/MacOS/App".to_owned(),
    ];
    zip_of(&[
        D(&names[0]),
        L(&names[1], "Versions/Current/Resources"),
        D(&names[2]),
        L(&names[3], "1.0"),
        D(&names[4]),
        D(&names[5]),
        F(&names[6], b"pak"),
        F(&names[7], LIBRARY),
        L(&names[8], "Versions/Current/F"),
        F(&names[9], b"app"),
    ])
}

fn no_link_left(destination: &Path, case: &str) {
    let mut pending = vec![destination.to_path_buf()];
    while let Some(folder) = pending.pop() {
        for entry in fs::read_dir(folder).unwrap() {
            let entry = entry.unwrap();
            let kind = entry.file_type().unwrap();
            assert!(!kind.is_symlink(), "{case}: a link was left");
            if kind.is_dir() {
                pending.push(entry.path());
            }
        }
    }
}

#[cfg(unix)]
#[test]
fn links_inside_the_folder_are_created_after_the_files_as_the_links_they_are() {
    let (_directory, destination, result) = extract_zip(&framework(), LinkRule::Symbolic);
    let extracted = result.unwrap();
    assert_eq!(
        extracted
            .links
            .keys()
            .map(RelativePath::as_str)
            .collect::<Vec<_>>(),
        [
            format!("{FRAMEWORK}/F"),
            format!("{FRAMEWORK}/Resources"),
            format!("{FRAMEWORK}/Versions/Current"),
        ]
    );
    for (link, target) in &extracted.links {
        let path = link.under(&destination);
        assert!(
            fs::symlink_metadata(&path).unwrap().is_symlink(),
            "{link:?}"
        );
        assert_eq!(fs::read_link(&path).unwrap(), Path::new(target));
        assert!(
            !extracted.files.contains_key(link),
            "a link is not recorded as a file"
        );
    }
    let framework = destination.join(FRAMEWORK);
    assert_eq!(fs::read(framework.join("F")).unwrap(), LIBRARY);
    assert_eq!(
        fs::read(framework.join("Resources/en.pak")).unwrap(),
        b"pak"
    );
    assert!(framework.join("Versions/Current").is_dir());
    assert_eq!(extracted.entries, 10);
    assert_eq!(extracted.files.len(), 3);
}

#[test]
fn without_symbolic_links_a_file_link_is_a_hard_link_and_a_folder_link_is_refused() {
    let file_links = zip_of(&[
        F("lib/libggml.so.0.27.0", LIBRARY),
        L("lib/libggml.so", "libggml.so.0"),
        L("lib/libggml.so.0", "./libggml.so.0.27.0"),
        L("lib/cuda/libggml.so", "../libggml.so.0.27.0"),
    ]);
    let mut rules = vec![LinkRule::FilesAsHardLinks];
    if !cfg!(unix) {
        rules.push(LinkRule::Symbolic);
    }
    for rule in rules {
        let (_directory, destination, result) = extract_zip(&file_links, rule);
        let extracted = result.unwrap();
        assert!(extracted.links.is_empty(), "{rule:?}");
        for name in ["lib/libggml.so", "lib/libggml.so.0", "lib/cuda/libggml.so"] {
            let path = destination.join(name);
            filesystem::refuse_links(&path).unwrap();
            assert_eq!(fs::read(&path).unwrap(), LIBRARY, "{rule:?} {name}");
            assert_eq!(
                extracted.files[&RelativePath::new(name).unwrap()],
                Sha256Digest::of(LIBRARY)
            );
        }
        no_link_left(&destination, "file links");
        let (_directory, destination, result) = extract_zip(&framework(), rule);
        assert!(
            matches!(result, Err(Error::Invalid(_))),
            "{rule:?}: {result:?}"
        );
        no_link_left(&destination, "a folder link");
    }
}

#[test]
fn links_that_escape_are_absolute_name_nothing_or_loop_are_refused() {
    let cases: Vec<(&str, Vec<Member<'static>>)> = vec![
        ("escape", vec![L("a/escape", "../../outside")]),
        (
            "escape from a folder",
            vec![D("a/b/"), L("a/b/up", "../../../outside")],
        ),
        ("absolute", vec![L("a/absolute", "/etc/passwd")]),
        ("backslash", vec![F("a/f", b"x"), L("a/back", "..\\a\\f")]),
        ("dangling", vec![L("a/nothing", "missing")]),
        ("dangling folder", vec![D("a/"), L("a/nothing", "missing/")]),
        ("through a file", vec![F("a/f", b"x"), L("a/inner", "f/x")]),
        (
            "file as folder",
            vec![F("a/f", b"x"), L("a/back", "f/../f")],
        ),
        ("cycle", vec![L("a/x", "y"), L("a/y", "x")]),
        ("self", vec![L("a/self", "self")]),
        ("root", vec![F("a/f", b"x"), L("a/root", "..")]),
        ("ancestor", vec![D("a/b/"), L("a/b/up", "..")]),
        ("own folder", vec![D("a/"), L("a/here", ".")]),
        (
            "folders that hold each other",
            vec![D("a/"), D("b/"), L("a/to-b", "../b"), L("b/to-a", "../a")],
        ),
        (
            "member inside a link",
            vec![D("a/real/"), L("a/link", "real"), F("a/link/f", b"x")],
        ),
        ("empty", vec![F("a/f", b"x"), L("a/empty", "")]),
    ];
    for rule in [LinkRule::Symbolic, LinkRule::FilesAsHardLinks] {
        for (case, members) in &cases {
            let (directory, destination, result) = extract_zip(&zip_of(members), rule);
            assert!(
                matches!(result, Err(Error::Invalid(_))),
                "{rule:?} {case}: {result:?}"
            );
            assert_eq!(
                fs::read(directory.path().join("outside")).unwrap(),
                b"outside"
            );
            no_link_left(&destination, case);
        }
    }
}

fn tar_gz_of(members: &[(&str, tar::EntryType, &str, &[u8])]) -> Vec<u8> {
    let mut builder = tar::Builder::new(Vec::new());
    for (name, kind, link, data) in members {
        let mut header = tar::Header::new_gnu();
        let old = header.as_old_mut();
        old.name[..name.len()].copy_from_slice(name.as_bytes());
        old.linkname[..link.len()].copy_from_slice(link.as_bytes());
        header.set_entry_type(*kind);
        header.set_size(data.len() as u64);
        header.set_mode(0o644);
        header.set_cksum();
        builder.append(&header, *data).unwrap();
    }
    let mut encoder = flate2::write::GzEncoder::new(Vec::new(), flate2::Compression::fast());
    encoder.write_all(&builder.into_inner().unwrap()).unwrap();
    encoder.finish().unwrap()
}

#[test]
fn a_tar_hard_link_is_always_a_hard_link_and_a_tar_folder_link_follows_the_rule() {
    use tar::EntryType::{Directory, Link, Regular, Symlink};
    let bytes = tar_gz_of(&[
        ("lib/real/", Directory, "", b""),
        ("lib/real/libx.so.1", Regular, "", LIBRARY),
        ("lib/copy.so", Link, "lib/real/libx.so.1", b""),
        ("lib/current", Symlink, "real", b""),
    ]);
    let directory = tempfile::tempdir().unwrap();
    let archive = directory.path().join("archive.tar.gz");
    fs::write(&archive, &bytes).unwrap();
    for rule in [LinkRule::Symbolic, LinkRule::FilesAsHardLinks] {
        let destination = directory.path().join(format!("{rule:?}"));
        fs::create_dir(&destination).unwrap();
        let result = extract(
            &archive,
            ArchiveFormat::TarGz,
            &destination,
            LIMITS,
            rule,
            &Cancellation::default(),
        );
        if cfg!(unix) && rule == LinkRule::Symbolic {
            let extracted = result.unwrap();
            assert_eq!(
                extracted
                    .links
                    .keys()
                    .map(RelativePath::as_str)
                    .collect::<Vec<_>>(),
                ["lib/current"]
            );
            assert_eq!(
                fs::read(destination.join("lib/current/libx.so.1")).unwrap(),
                LIBRARY
            );
            let copy = destination.join("lib/copy.so");
            assert!(!fs::symlink_metadata(&copy).unwrap().is_symlink());
            assert_eq!(fs::read(&copy).unwrap(), LIBRARY);
        } else {
            assert!(matches!(result, Err(Error::Invalid(_))), "{rule:?}");
            no_link_left(&destination, "a refused tar folder link");
        }
    }
}

#[test]
fn link_placements_count_against_the_member_and_byte_bounds() {
    let bytes = zip_of(&[
        F("lib/real.so", LIBRARY),
        L("lib/a.so", "real.so"),
        L("lib/b.so", "real.so"),
    ]);
    let directory = tempfile::tempdir().unwrap();
    let archive = directory.path().join("archive.zip");
    fs::write(&archive, &bytes).unwrap();
    let run = |entries: usize, unpacked_bytes: u64, name: &str| {
        let destination = directory.path().join(name);
        fs::create_dir(&destination).unwrap();
        extract(
            &archive,
            ArchiveFormat::Zip,
            &destination,
            Limits {
                entries,
                unpacked_bytes,
            },
            LinkRule::FilesAsHardLinks,
            &Cancellation::default(),
        )
    };
    let placed = 3 * LIBRARY.len() as u64;
    assert!(matches!(
        run(2, placed, "entries"),
        Err(Error::LimitExceeded)
    ));
    assert!(matches!(
        run(3, placed - 1, "bytes"),
        Err(Error::LimitExceeded)
    ));
    run(3, placed, "fits").unwrap();
}

#[cfg(unix)]
#[test]
fn the_check_after_creation_refuses_a_link_it_did_not_create_or_that_leaves() {
    use std::os::unix::fs::symlink;
    let directory = tempfile::tempdir().unwrap();
    let destination = directory.path().join("build");
    fs::create_dir_all(destination.join("lib")).unwrap();
    fs::write(destination.join("lib/real"), b"x").unwrap();
    fs::write(directory.path().join("outside"), b"o").unwrap();
    symlink("real", destination.join("lib/ours")).unwrap();
    let ours: BTreeMap<RelativePath, String> =
        [(RelativePath::new("lib/ours").unwrap(), "real".to_owned())].into();
    verify_links(&destination, &ours).unwrap();
    assert!(
        matches!(
            verify_links(&destination, &BTreeMap::new()),
            Err(Error::Integrity(_))
        ),
        "a link this extraction did not create"
    );
    symlink("../..", destination.join("lib/planted")).unwrap();
    assert!(matches!(
        verify_links(&destination, &ours),
        Err(Error::Integrity(_))
    ));
    fs::remove_file(destination.join("lib/planted")).unwrap();
    fs::remove_file(destination.join("lib/ours")).unwrap();
    symlink("../../outside", destination.join("lib/ours")).unwrap();
    let leaving: BTreeMap<RelativePath, String> = [(
        RelativePath::new("lib/ours").unwrap(),
        "../../outside".to_owned(),
    )]
    .into();
    assert!(
        matches!(
            verify_links(&destination, &leaving),
            Err(Error::Integrity(_))
        ),
        "a link that resolves outside"
    );
}
