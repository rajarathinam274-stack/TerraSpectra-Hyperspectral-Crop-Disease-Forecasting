"""Inventory the public Dataverse dataset and download selected metadata CSVs."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "dataset.yaml"
TIMEOUT = 60


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def main() -> None:
    config = load_config()["dataset"]
    api = config["dataverse_api"].rstrip("/")
    pid = config["persistent_id"]
    metadata_dir = ROOT / config["metadata_dir"]
    metadata_dir.mkdir(parents=True, exist_ok=True)

    response = requests.get(
        f"{api}/datasets/:persistentId/",
        params={"persistentId": pid},
        headers={"Accept": "application/json"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
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
            "filesize": data_file.get("filesize"),
            "content_type": data_file.get("contentType"),
        })

    (metadata_dir / "file_inventory.json").write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Saved inventory with {len(inventory)} files.")

    selected = set(config.get("selected_metadata_files", []))
    found = set()
    for item in inventory:
        filename, file_id = item.get("filename"), item.get("id")
        if filename not in selected or not file_id:
            continue
        file_response = requests.get(
            f"{api}/access/datafile/{quote(str(file_id))}", timeout=TIMEOUT
        )
        file_response.raise_for_status()
        destination = metadata_dir / Path(filename).name
        destination.write_bytes(file_response.content)
        found.add(filename)
        print(f"Downloaded {filename}: {len(file_response.content)} bytes")

    missing = sorted(selected - found)
    if missing:
        print("Configured files not found in this dataset version:", ", ".join(missing))
    print("Metadata inventory/download step completed.")


if __name__ == "__main__":
    main()
