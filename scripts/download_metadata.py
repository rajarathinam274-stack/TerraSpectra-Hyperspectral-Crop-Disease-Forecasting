"""Inventory Dataverse and download selected annotation CSVs only."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "dataset.yaml"
TIMEOUT = (15, 120)


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def request_json(url: str, **kwargs) -> dict:
    response = requests.get(url, timeout=TIMEOUT, **kwargs)
    response.raise_for_status()
    return response.json()


def checksum_matches(content: bytes, checksum: dict) -> bool | None:
    """Return True/False for supported advertised checksums, otherwise None."""
    algorithm = str(checksum.get("type", "")).lower().replace("-", "")
    expected = str(checksum.get("value", "")).lower()
    if not algorithm or not expected:
        return None
    try:
        digest = hashlib.new(algorithm, content).hexdigest().lower()
    except (ValueError, TypeError):
        return None
    return digest == expected


def verify_download_integrity(
    filename: str,
    content: bytes,
    expected_size: int | None,
    api_checksum: dict | None,
    pinned_md5: str | None,
) -> dict:
    """Fail closed unless size and at least one supported checksum are verified.

    If both a Dataverse checksum and a pinned publisher checksum are available,
    both must match. The pinned MD5 is a dataset-version integrity guard, not a
    cryptographic security mechanism.
    """
    if expected_size is not None and len(content) != int(expected_size):
        raise IOError(
            f"Size mismatch for {filename}: expected {expected_size}, got {len(content)}"
        )

    api_checksum = api_checksum or {}
    api_result = checksum_matches(content, api_checksum)
    if api_result is False:
        raise IOError(f"Dataverse checksum mismatch for {filename}")

    methods = []
    if api_result is True:
        methods.append(f"Dataverse {api_checksum.get('type')} checksum")

    pinned_result = None
    if pinned_md5:
        try:
            actual_md5 = hashlib.md5(content, usedforsecurity=False).hexdigest().lower()
        except TypeError:  # compatibility fallback for Python implementations
            actual_md5 = hashlib.md5(content).hexdigest().lower()
        pinned_result = actual_md5 == str(pinned_md5).lower()
        if not pinned_result:
            raise IOError(
                f"Publisher-pinned MD5 mismatch for {filename}: "
                f"expected {pinned_md5}, got {actual_md5}"
            )
        methods.append("publisher-pinned MD5")

    if not methods:
        raise IOError(
            f"No supported checksum available for {filename}; "
            "download cannot be declared verified."
        )

    return {
        "checksum_verified": True,
        "verification_methods": methods,
        "dataverse_checksum_verified": api_result,
        "pinned_md5_verified": pinned_result,
    }


def main() -> None:
    dataset = load_config()["dataset"]
    api = dataset["dataverse_api"].rstrip("/")
    persistent_id = dataset["persistent_id"]
    metadata_dir = ROOT / dataset["metadata_dir"]
    metadata_dir.mkdir(parents=True, exist_ok=True)

    payload = request_json(
        f"{api}/datasets/:persistentId/",
        params={"persistentId": persistent_id},
        headers={"Accept": "application/json"},
    )
    (metadata_dir / "dataset_metadata.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    files = payload.get("data", {}).get("latestVersion", {}).get("files", [])
    inventory = []
    for item in files:
        data_file = item.get("dataFile", {})
        inventory.append({
            "id": data_file.get("id"),
            "filename": data_file.get("filename"),
            "directory_label": item.get("directoryLabel", ""),
            "filesize": data_file.get("filesize"),
            "content_type": data_file.get("contentType"),
            "checksum": data_file.get("checksum", {}),
        })

    (metadata_dir / "file_inventory.json").write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Dataset inventory saved: {len(inventory)} file records.")

    selected = set(dataset.get("selected_metadata_files", []))
    pinned_checksums = dataset.get("pinned_md5_checksums", {})
    available = {
        item["filename"]: item
        for item in inventory
        if item.get("filename") in selected and item.get("id") is not None
    }
    missing = sorted(selected - set(available))
    if missing:
        raise RuntimeError(
            "Required annotation files not found in the current dataset version: "
            + ", ".join(missing)
        )

    downloaded = []
    for filename in sorted(selected):
        item = available[filename]
        url = f"{api}/access/datafile/{quote(str(item['id']), safe='')}"
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        content = response.content

        integrity = verify_download_integrity(
            filename=filename,
            content=content,
            expected_size=item.get("filesize"),
            api_checksum=item.get("checksum"),
            pinned_md5=pinned_checksums.get(filename),
        )

        destination = metadata_dir / Path(filename).name
        destination.write_bytes(content)
        downloaded.append({
            "filename": filename,
            "file_id": item["id"],
            "directory_label": item.get("directory_label", ""),
            "bytes": len(content),
            "dataverse_checksum": item.get("checksum", {}),
            **integrity,
            "sha256": hashlib.sha256(content).hexdigest(),
            "local_path": str(destination.relative_to(ROOT)),
        })
        print(
            f"Downloaded and checksum-verified {filename} "
            f"({len(content):,} bytes; {', '.join(integrity['verification_methods'])})."
        )

    manifest = {
        "persistent_id": persistent_id,
        "dataset_title": dataset.get("name"),
        "dataset_version": payload.get("data", {}).get("latestVersion", {}).get("versionNumber"),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "downloaded_files": downloaded,
        "note": "Metadata CSVs only; raw hyperspectral archives were not downloaded.",
    }
    (metadata_dir / "download_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Metadata step complete: {len(downloaded)} annotation CSVs saved.")
    print(f"Manifest: {metadata_dir / 'download_manifest.json'}")


if __name__ == "__main__":
    main()
