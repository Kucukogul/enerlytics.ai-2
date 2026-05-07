# Data Directory Policy

This folder is intentionally ignored by Git and used for local datasets/artifacts.

## Structure

- `raw/`: immutable source datasets
- `processed/`: cleaned/feature-ready datasets

## Rules

- Do not commit real datasets, exports, or sensitive files.
- Keep only reproducible data generation logic in code (`scripts/`, `pipelines/`).
- If needed, keep a tiny anonymized sample in a separate tracked path (for example `analysis/samples/`).

## How to Recreate Data

Document your data acquisition and processing steps in project docs or scripts so another developer can rebuild this folder.
