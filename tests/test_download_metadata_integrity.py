import hashlib

import pytest

from scripts.download_metadata import checksum_matches, verify_download_integrity


def test_pinned_md5_verifies_content_when_api_checksum_is_absent():
    content = b"publisher metadata bytes"
    expected = hashlib.md5(content, usedforsecurity=False).hexdigest()
    result = verify_download_integrity(
        "sample.csv", content, len(content), None, expected
    )
    assert result["checksum_verified"] is True
    assert result["pinned_md5_verified"] is True
    assert result["verification_methods"] == ["publisher-pinned MD5"]


def test_both_api_and_pinned_checksums_must_match_when_available():
    content = b"metadata"
    expected = hashlib.md5(content, usedforsecurity=False).hexdigest()
    result = verify_download_integrity(
        "sample.csv", content, len(content),
        {"type": "MD5", "value": expected}, expected
    )
    assert result["dataverse_checksum_verified"] is True
    assert result["pinned_md5_verified"] is True
    assert len(result["verification_methods"]) == 2


def test_rejects_publisher_pinned_checksum_mismatch_even_if_api_checksum_matches():
    content = b"metadata"
    api_expected = hashlib.md5(content, usedforsecurity=False).hexdigest()
    with pytest.raises(IOError, match="Publisher-pinned MD5 mismatch"):
        verify_download_integrity(
            "sample.csv", content, len(content),
            {"type": "MD5", "value": api_expected}, "0" * 32
        )


def test_rejects_size_mismatch_before_checksum():
    content = b"metadata"
    expected = hashlib.md5(content, usedforsecurity=False).hexdigest()
    with pytest.raises(IOError, match="Size mismatch"):
        verify_download_integrity("sample.csv", content, len(content) + 1, None, expected)


def test_rejects_unverifiable_download():
    with pytest.raises(IOError, match="No supported checksum available"):
        verify_download_integrity("sample.csv", b"metadata", None, None, None)


def test_checksum_helper_returns_none_for_unsupported_algorithm():
    assert checksum_matches(b"metadata", {"type": "unknown", "value": "x"}) is None
