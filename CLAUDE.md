# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

OrgaCal (境算师) is a Gradio web workbench for organoid orbital-shaker culture: pre-culture parameter calculation (shear, feasible rpm interval, rpm conversion) and post-culture image morphology/batch consistency. UI text and docs are in Chinese. Flat Python layout, no package structure, no GPU or API keys needed.

## Commands

Windows, Python 3.12+ (tested on 3.13). Use the project venv (`.venv` is local and git-ignored).

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py                      # serves http://127.0.0.1:7860 (or double-click 启动OrgaCal.bat)
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m unittest tests.test_physics -v   # one test module
.venv\Scripts\python.exe -m unittest tests.test_physics.<Class>.<test_name>   # single test
```

- No linter or formatter is configured.
- `requirements-dev.txt` adds openpyxl, only needed for `scripts/validate_paper_mad.py --source-dir <dir>`.
- `scripts/validate_slimia.py <OperaPhenix.zip> --output-dir <dir>` runs the external segmentation validation. `build_reference_index.py` and `cache_literature.py` regenerate data under `data/`.
- Docker: `Dockerfile` (python:3.13-slim) runs `python app.py` on port 7860 using `GRADIO_SERVER_NAME`/`GRADIO_SERVER_PORT` env vars. `app.py` exposes a global `demo` object for ModelScope Gradio mode.
- Dependencies are pinned to exact versions in `requirements.txt`; keep it that way.

## Architecture

Layered, with pure computation modules separated from Gradio glue:

- **Also computation:** `reliability.py` (ICC), `screening.py` (constraint grid scan + `scan_for_ui`), `literature_inputs.py` (DOI/PDF), `presentation.py` (overview/validation HTML), `run_metadata.py` (`timed_state` decorator adds `runtime_ms` to the state dict).
- **Computation (no Gradio):** `physics.py` (liquid-depth-scale shear estimate, geometry/vessel support via `SUPPORTED_GEOMETRY`), `constraints.py` (shear upper bound ∩ suspension/oxygen lower bounds → conditional rpm interval, `convert_rpm` for equal-shear / equal-linear-speed / equal-acceleration criteria, Δρ×Q sensitivity), `morphology.py` (traditional-CV candidate segmentation + rendering), `calibration.py` (scale bar → um/px), `batch.py` (multi-image analysis with metadata CSV, manual exclusion, reference records), `consistency.py` (stratified relative MAD, PCA), `literature.py` (Europe PMC search, full-text evidence extraction, 21 local cached records), `reports.py` (CSV/JSON/Markdown/PDF/ZIP bundle).
- **UI glue:** `ui_logic.py` holds the `*_for_ui` callbacks that wrap the computation modules and shape results for Gradio; `single_ui.py` builds the single-image tab (`build_single`) with its own calibration/exclusion state; `visual_design.py` provides theme, CSS, header and heading helpers (styles also in `assets/workbench.css`; design tokens in `design-system/MASTER.md`).
- **Entry:** `app.py` assembles the left-nav layout and pages (剪切预算, 转速换算, 形态量化, 文献条件, 条件筛选, plus a separate 综合报告 page) and wires callbacks.
- **Data:** `data/reference/` holds validation outputs (`mad_validation.json`, `segmentation_validation.json`) and paper-derived parameters; `examples/` holds demo images, `batch_metadata.csv` template and `source_manifest.json`.

Report export aggregates the outputs of whichever modules were run; unrun modules must be labelled as such, and downloads are snapshots.

## Conventions that matter

- **Evidence boundary is a product requirement.** Physics is an uncalibrated scenario model; feasible intervals are never "experimentally safe". Do not add UI copy or defaults implying calibration, safety guarantees, or that paper EV1 parameters were reproduced from images. Demo data and the author's original data must stay explicitly labelled.
- Results appear only after the user runs a calculation; missing inputs/no-intersection cases are reported explicitly rather than filled with defaults. Temperature is a record unless it actually enters the calculation, and the UI must not claim otherwise.
- MAD is `median(abs(x−median(x)))/abs(median(x))` with no 1.4826 factor; the UI shows it as a percentage (×100). Keep Circularity and Solidity as distinct, unitless metrics.
- Scale resolution order: per-image um/px, then a user-confirmed shared scale, else keep px. Stratify statistics by unit, day and imaging batch; reject duplicate filenames in one batch.
- Not implemented (do not claim): rotating chamber, mechanical-disturbance sub-terms, target-morphology surrogate model, OCR for scanned PDFs, ICC confidence intervals or reliability grading.
- Implemented with limits: sample CV = 100·SD(ddof=1)/|mean| shown beside relative MAD; ICC(2,1) is a point estimate for complete balanced repeated measurements only (independent photos cannot yield ICC); DOI lookup accepts only a DOI or doi.org URL; PDF import extracts text locally with `pypdf` and all fields stay "待人工核对"; `screening.py` is a physical-constraint grid scan with 0 paired condition–morphology samples, so it must never claim to predict or rank morphology.
- Model assumptions, metric definitions and validation records live in `docs/` (e.g. `模型假设.md`, `指标定义与验收清单.md`, `整体验证记录.md`); update them when changing a model or metric.
- Several files (docs, `design-system/MASTER.md`) are UTF-8 Chinese; read and write them as UTF-8 (the launcher uses `python -X utf8`). PowerShell's default output may show them garbled.
- Reports, zips, `outputs/`, `.env`, and auth files are git-ignored and must not be committed. Third-party data licensing is in `THIRD_PARTY_NOTICES.md`.
