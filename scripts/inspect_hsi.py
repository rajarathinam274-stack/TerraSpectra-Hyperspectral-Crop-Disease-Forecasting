"""Inspect a HySpex ENVI .hdr/.hyspex pair and write a JSON report."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
try:
    from .hsi_io import compare_sensor_profile, inspect_envi_header
except ImportError:
    from hsi_io import compare_sensor_profile, inspect_envi_header

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("header", type=Path)
    parser.add_argument("--image", type=Path, default=None)
    parser.add_argument("--modality", choices=["VNIR", "SWIR"], default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    report = inspect_envi_header(args.header, args.image)
    if args.modality:
        report["paper_sensor_profile_check"] = compare_sensor_profile(report, args.modality)
    output = json.dumps(report, indent=2, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output)

if __name__ == "__main__":
    main()
