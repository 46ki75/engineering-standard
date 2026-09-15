# Recorded evaluation reports

Git contains the written reports, readable computed analyses, compact summaries, and adjudication records. Raw run artifacts remain local and are ignored: manifests, prompts, model responses, per-attempt logs, audit traces, and runtime locks. The full-suite `analysis.json` files also remain local because they embed individual judgments; their readable `analysis.md` counterparts are committed.

Two recorded documents are committed as fixed omission-control fixtures: the Mica and Quarry B outputs under `calibration-2026-09-15-v2/writers/`. They allow the control tests to run from a fresh checkout without the remaining raw artifacts.

Start with the [final report](full-openai55-v1/report.md). The [evaluation guide](../README.md), [full-suite protocol](../FULL-EVALUATION.md), and [recovery record](../RECOVERY.md) describe the experiment and its execution.

Reports also refer to local artifacts such as `manifest.json`, `audit.json`, and individual writer or judge files. Those references require the original run directory; they are not available from a Git checkout alone. Recomputing a recorded analysis or auditing its sessions requires those local artifacts and, for session exports, the corresponding OpenCode session store. The committed runner, prompts, and fixtures support new evaluation runs, whose model outputs can differ.
