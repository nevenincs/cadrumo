use super::super::framing::{
    DOCUMENT_FRAME, MAXIMUM_FRAME_BYTES, base64_decode, frame, frame_header, is_uuid, request_id,
};

#[test]
fn frames_carry_a_kind_a_big_endian_length_and_bounded_payloads() {
    let framed = frame(DOCUMENT_FRAME, b"{}").unwrap();
    assert_eq!(framed, [b'J', 0, 0, 0, 2, b'{', b'}']);
    assert!(frame(DOCUMENT_FRAME, b"").is_err());
    assert!(frame(DOCUMENT_FRAME, &vec![b'x'; MAXIMUM_FRAME_BYTES]).is_ok());
    assert!(frame(DOCUMENT_FRAME, &vec![b'x'; MAXIMUM_FRAME_BYTES + 1]).is_err());
    assert_eq!(frame_header(&[b'E', 0, 0, 1, 0]).unwrap(), (b'E', 256));
    for header in [
        [b'S', 0, 0, 0, 1],
        [b'J', 0, 0, 0, 0],
        [b'J', 0, 1, 0, 1],
        [b'X', 0, 0, 0, 1],
    ] {
        assert!(frame_header(&header).is_err(), "{header:?}");
    }
}

#[test]
fn base64_accepts_only_the_canonical_spelling() {
    assert_eq!(base64_decode("aGk=").unwrap(), b"hi");
    assert_eq!(base64_decode("aGV5").unwrap(), b"hey");
    assert_eq!(base64_decode("aA==").unwrap(), b"h");
    assert_eq!(
        base64_decode("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
            .unwrap()
            .len(),
        32
    );
    for rejected in ["", "aGk", "aGk=x", "a===", "aGl=", "aB==", "a Gk=", "YQ=="] {
        if rejected == "YQ==" {
            assert_eq!(base64_decode(rejected).unwrap(), b"a");
            continue;
        }
        assert!(base64_decode(rejected).is_none(), "{rejected}");
    }
}

#[test]
fn request_ids_are_distinct_version_four_uuids() {
    let first = request_id();
    let second = request_id();
    assert!(is_uuid(&first), "{first}");
    assert_ne!(first, second);
    assert_eq!(&first[14..15], "4");
    assert!(matches!(&first[19..20], "8" | "9" | "a" | "b"));
    assert!(!is_uuid("0A1B2C3D-4E5F-4A6B-9C7D-8E9F0A1B2C3D"));
}
