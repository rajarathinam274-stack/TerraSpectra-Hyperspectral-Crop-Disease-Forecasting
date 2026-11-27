"""Streamlit wrapper for the guarded, date-specific TerraSpectra inference CLI."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from predict import PredictionValidationError, run_inference  # noqa: E402

st.set_page_config(page_title="TerraSpectra demo", page_icon="🌾", layout="wide")
st.title("TerraSpectra")
st.subheader("Hyperspectral inference demonstration")
st.warning(
    "Only load a trusted model bundle created by this project. Joblib files can execute "
    "code during deserialization. Do not upload untrusted model files."
)
st.info(
    "This demo performs date-specific classification using an existing fitted model. "
    "It is not a disease forecast, field diagnostic, or agronomic recommendation."
)

model_upload = st.file_uploader(
    "Trusted TerraSpectra model bundle (.joblib)", type=["joblib"], key="model_upload"
)
csv_upload = st.file_uploader(
    "Pot-level spectral CSV", type=["csv"], key="spectra_upload"
)
date_column = st.text_input(
    "Acquisition-date column",
    value="date_folder_yyyymmdd_candidate",
    help="Must contain the single date used by the uploaded model.",
)

if model_upload is None or csv_upload is None:
    st.caption("Upload both files to enable inference.")
elif st.button("Run guarded inference", type="primary"):
    try:
        with tempfile.TemporaryDirectory(prefix="terraspectra-demo-") as temp_dir:
            temp = Path(temp_dir)
            model_path = temp / "model.joblib"
            input_path = temp / "input.csv"
            output_path = temp / "predictions.csv"
            model_path.write_bytes(model_upload.getvalue())
            input_path.write_bytes(csv_upload.getvalue())
            summary = run_inference(
                input_path, model_path, output_path, date_column=date_column.strip()
            )
            predictions = pd.read_csv(output_path, encoding="utf-8-sig")
            st.session_state["terra_predictions"] = predictions
            st.session_state["terra_summary"] = summary
    except PredictionValidationError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"Inference could not be completed: {exc}")

if "terra_predictions" in st.session_state:
    summary = st.session_state["terra_summary"]
    st.success(
        f"Completed {summary['rows_predicted']} predictions for "
        f"{summary['selected_date']} ({summary['target_semantics']})."
    )
    st.caption(summary["interpretation"])
    st.dataframe(st.session_state["terra_predictions"], use_container_width=True)
    st.download_button(
        "Download predictions CSV",
        data=st.session_state["terra_predictions"].to_csv(index=False).encode("utf-8"),
        file_name="terraspectra_predictions.csv",
        mime="text/csv",
    )
    st.caption("Predictions are model outputs, not verified biological diagnoses.")
