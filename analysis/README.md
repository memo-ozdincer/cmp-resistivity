# Recooldown analysis

Source: `/Users/memoozdincer/Downloads/recooldown.zip`. Original extracted files are preserved in `data/recooldown/raw/`; main analysis uses numbered runs 2–6. Run 1 supplies calibration marker context only.

User confirmed **channel 1 = base plate; channel 2 = sample** on 2026-11-27. This overrides the historical CLI sample label for channel 1. Original CSV columns and bytes are preserved; the merged CSV adds explicitly named sensor columns.

From the repository root, using uv without changing acquisition dependencies:

```sh
uv run --no-project --with pandas==3.0.1 --with numpy==2.4.2 --with matplotlib==3.10.8 python analysis/analyze_recooldown.py
```

Outputs go to `results/recooldown/`: HTML report, seven PNG and SVG figures, merged data, run summary, audit JSON with input hashes, and a ZIP of all results. Results and raw inputs are saved in the repository.

Figures 1–5 retain raw voltage axes. At the user’s request, figures 6–7 use a provisional linear base plate calibration: 433.188154 mV at 23.5 °C and highest recorded voltage 981.166 mV assigned nominal 77 K. The original marked cold interval drifts and is not used. This assumes LN2 equilibrium and does not independently establish it. Channel 2 (sample) remains uncalibrated. Coefficients, selected source row, and limitations are saved in base_plate_calibration.json. Current is not logged. The fifth plot explicitly assumes constant 79.8 mA from an earlier bench observation; it is not a verified resistance measurement. No transition temperature is extracted. Failed electrical rows are retained in the merged data but excluded from electrical figures. Gaps are not filled.

Verified: original archive member hashes match extracted inputs, all report links resolve, ZIP passes integrity checks, main row totals and sensor mapping agree with the audit. Figures were visually inspected.
