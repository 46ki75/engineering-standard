#!/usr/bin/env python3
"""Regenerate frozen full-suite analysis without inference (Python 3.9+).

Usage: python3 -B evals/documenting/full_analysis.py --output PATH
Only analysis.json and analysis.md are published; execution artifacts are read-only.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import importlib.util
import math
import os
from pathlib import Path
import random
import re
import sys
import tempfile


sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "_documenting_full_analysis_runner", HERE / "full.py"
)
if SPEC is None or SPEC.loader is None:
    raise ValueError("Cannot import full-suite runner")
full = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = full
SPEC.loader.exec_module(full)

# This is a versioned interpretation of the prose contract, not a new analysis
# plan. Unknown policy wording must fail explicitly instead of silently receiving
# the current implementation's semantics. Numeric settings come from the freeze.
POLICIES = {
    "primary_comparison": "C versus B on held-out cases; A versus B is secondary",
    "primary_score": "C win +1, B win -1, tie/uncertain 0; average valid primary repetitions within each document, then average documents equally",
    "secondary_measures": "Paired atomic requirement failure fraction, known-issue resolution (resolved=1, partial=0.5, unresolved/uncertain=0), organization, unnecessary change, critical regression flags, length and operational reliability",
    "adoption": "Adopt C only if the primary interval lower bound exceeds zero, its paired requirement-failure fraction does not increase, and no new critical regression is confirmed; otherwise retain B",
    "order_swaps": "Reliability diagnostic only; exclude swaps from primary effect and report incomplete pairs separately",
}
MEASURES = (
    "requirement_failure_fraction",
    "requirement_uncertainty_fraction",
    "known_issue_resolution",
    "organization",
    "unnecessary_change",
)
SEVERITIES = ("critical", "major", "minor")


def mean(values):
    values = list(values)
    return math.fsum(values) / len(values) if values else None


def fraction(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def settings_from_plan(plan, bootstrap_samples=None):
    for key, expected in POLICIES.items():
        if plan.get(key) != expected:
            raise ValueError("Unsupported frozen analysis policy: " + key)
    uncertainty = re.fullmatch(
        r"(\d+)% percentile bootstrap of documents within category, (\d+) resamples, "
        r"seed (\d+); repetitions and swapped judgments are not independent documents",
        plan.get("uncertainty", ""),
    )
    coverage = re.fullmatch(
        r"At least (\d+)% of planned primary BC judgments valid, with at least "
        r"(two|\d+) valid primary repetitions for every held-out document; "
        r"failures and uncertainty also reported explicitly",
        plan.get("coverage_gate", ""),
    )
    if not uncertainty or not coverage:
        raise ValueError("Unsupported frozen bootstrap or coverage policy")
    confidence, samples, seed = map(int, uncertainty.groups())
    percent, repetitions = coverage.groups()
    repetitions = 2 if repetitions == "two" else int(repetitions)
    if (
        not 0 < confidence < 100
        or samples < 1
        or not 0 < int(percent) <= 100
        or repetitions < 1
    ):
        raise ValueError("Invalid frozen analysis settings")
    if bootstrap_samples is not None and bootstrap_samples != samples:
        raise ValueError("--bootstrap-samples must match the frozen analysis_plan")
    return {
        "confidence": confidence / 100,
        "bootstrap_samples": samples,
        "bootstrap_seed": seed,
        "minimum_valid_fraction": int(percent) / 100,
        "minimum_valid_repetitions": repetitions,
    }


def load_manifest(output):
    frozen = full.read_json(output / "manifest.json")
    unsigned = {key: value for key, value in frozen.items() if key != "manifest_sha256"}
    if frozen.get("manifest_sha256") != full.json_hash(unsigned):
        raise ValueError("Manifest hash mismatch")
    if frozen.get("format_version") != 1 or frozen.get("stage") != "full-blind":
        raise ValueError("Unsupported manifest")
    # Deliberately do not call load_frozen/load_inputs: adoption can change live
    # prompts or fixtures without invalidating the recorded experiment.
    validate_schedule(frozen)
    return frozen


def validate_schedule(frozen):
    cases = {case["id"]: case for case in frozen["inputs"]["cases"]}
    metadata = frozen["inputs"]["case_metadata"]
    if len(cases) != len(frozen["inputs"]["cases"]) or set(cases) != set(metadata):
        raise ValueError("Duplicate cases or missing frozen case metadata")
    if frozen["max_attempts"] not in (1, 2):
        raise ValueError("Unsupported retry bound")
    for ident, case in cases.items():
        meta = metadata[ident]
        if meta["split"] not in full.SPLITS or meta["category"] not in full.CATEGORIES:
            raise ValueError("Invalid frozen case routing")
        if case["split"] != meta["split"]:
            raise ValueError("Frozen case split mismatch")
        if "embedded_sha256" in meta and meta["embedded_sha256"] != full.json_hash(
            case
        ):
            raise ValueError("Frozen embedded case hash mismatch")
        for field in ("requirements", "issues"):
            ids = [item["id"] for item in case[field]]
            if len(set(ids)) != len(ids) or (field == "requirements" and not ids):
                raise ValueError("Invalid frozen annotation IDs")
    jobs = frozen["jobs"]
    if set(jobs) != {"writers", "judges"}:
        raise ValueError("Unsupported job roles")
    lookups = {}
    for role in ("writers", "judges"):
        lookups[role] = {job["id"]: job for job in jobs[role]}
        if len(lookups[role]) != len(jobs[role]):
            raise ValueError("Duplicate job IDs")
        units = set()
        for job in jobs[role]:
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", job["id"]) is None:
                raise ValueError("Unsafe job ID")
            meta = metadata[job["case"]]
            if any(job[key] != meta[key] for key in ("split", "category")):
                raise ValueError("Job routing mismatch")
            if type(job["repetition"]) is not int or job["repetition"] < 1:
                raise ValueError("Invalid repetition")
            unit = (
                job["case"],
                job["repetition"],
                job.get("arm"),
                job.get("pair"),
                job.get("kind"),
            )
            if unit in units:
                raise ValueError("Duplicate scheduled measurement")
            units.add(unit)
    for job in jobs["writers"]:
        if job["arm"] not in full.ARMS:
            raise ValueError("Invalid writer arm")
    for job in jobs["judges"]:
        if job["pair"] not in ("AB", "BC") or job["kind"] not in ("primary", "swap"):
            raise ValueError("Unsupported comparison")
        if {job["left"], job["right"]} != set(job["pair"]):
            raise ValueError("Comparison arm mismatch")
        for side in ("left", "right"):
            writer = lookups["writers"][job[side + "_writer"]]
            if writer["arm"] != job[side] or any(
                writer[key] != job[key]
                for key in ("case", "repetition", "split", "category")
            ):
                raise ValueError("Writer dependency mismatch")
        primary = lookups["judges"][job["primary_id"]]
        if primary["kind"] != "primary" or any(
            primary[key] != job[key] for key in ("case", "repetition", "pair")
        ):
            raise ValueError("Primary comparison mismatch")
        if job["kind"] == "primary" and job["primary_id"] != job["id"]:
            raise ValueError("Primary ID mismatch")
        if job["kind"] == "swap" and (job["left"], job["right"]) != (
            primary["right"],
            primary["left"],
        ):
            raise ValueError("Swap is not the reversed primary")


def selected_artifact(output, role, job, entry, name):
    number = entry["selected_first_valid"]
    attempt = next(item for item in entry["attempts"] if item["attempt"] == number)
    # Construct the native path from the schedule, never a cache-supplied folder.
    path = output / role / job["id"] / ("attempt-" + str(number)) / name
    expected = attempt.get("artifact_sha256", {}).get(name)
    if not expected or full.file_hash(path) != expected:
        raise ValueError(
            "Selected artifact hash mismatch: " + role + "/" + job["id"] + "/" + name
        )
    return path


def selected_data(output, frozen, index):
    writers, judgments = {}, {}
    for role, records in (("writers", writers), ("judges", judgments)):
        for job in sorted(frozen["jobs"][role], key=lambda item: item["id"]):
            entry = index["jobs"][role][job["id"]]
            if entry["selected_first_valid"] is None:
                continue
            result = full.read_json(
                selected_artifact(output, role, job, entry, "result.json")
            )
            attempt = next(
                a
                for a in entry["attempts"]
                if a["attempt"] == entry["selected_first_valid"]
            )
            if (
                result.get("full_validation") != "valid"
                or full.metrics_only(result) != attempt["metrics"]
            ):
                raise ValueError("Selected native result/outcome mismatch")
            if role == "writers":
                path = selected_artifact(output, role, job, entry, "output.md")
                records[job["id"]] = path.read_bytes().decode("utf-8")
                continue
            mapping = full.read_json(
                selected_artifact(output, role, job, entry, "mapping.json")
            )
            for key in (
                "case",
                "repetition",
                "pair",
                "kind",
                "primary_id",
                "left",
                "right",
            ):
                if mapping[key] != job[key]:
                    raise ValueError("Selected judgment mapping mismatch")
            for side in ("left", "right"):
                writer_id = job[side + "_writer"]
                writer = index["jobs"]["writers"][writer_id]
                number = writer["selected_first_valid"]
                if number is None:
                    raise ValueError("Selected judgment has no selected writer")
                selected = next(a for a in writer["attempts"] if a["attempt"] == number)
                if mapping["writers"][side] != {
                    "job": writer_id,
                    "attempt": number,
                    "output_sha256": selected["artifact_sha256"]["output.md"],
                }:
                    raise ValueError("Selected judgment writer provenance mismatch")
            records[job["id"]] = full.read_json(
                selected_artifact(output, role, job, entry, "judgment.json")
            )
    return writers, judgments


def normalized_winner(job, judgment):
    winner = judgment["winner"]
    if winner not in ("left", "right", "tie", "uncertain"):
        raise ValueError("Unsupported selected winner")
    return job[winner] if winner in ("left", "right") else winner


def candidate_measures(candidate, case):
    counts = {}
    for field, statuses in (
        ("requirements", ("pass", "fail", "uncertain")),
        ("issues", ("resolved", "partial", "unresolved", "uncertain")),
    ):
        if set(candidate[field]) != {item["id"] for item in case[field]}:
            raise ValueError("Selected assessment annotation IDs mismatch")
        observed = Counter(item["status"] for item in candidate[field].values())
        if set(observed) - set(statuses):
            raise ValueError("Unsupported selected assessment status")
        counts[field] = {status: observed[status] for status in statuses}
        counts[field]["total"] = sum(observed.values())
    requirements, issues = counts["requirements"], counts["issues"]
    for field, lower, upper in (("organization", 1, 5), ("unnecessary_change", 0, 3)):
        if type(candidate[field]) is not int or not lower <= candidate[field] <= upper:
            raise ValueError("Unsupported selected ordinal score")
    return {
        "counts": counts,
        "requirement_failure_fraction": requirements["fail"] / requirements["total"],
        "requirement_uncertainty_fraction": requirements["uncertain"]
        / requirements["total"],
        "known_issue_resolution": (
            (issues["resolved"] + 0.5 * issues["partial"]) / issues["total"]
            if issues["total"]
            else None
        ),
        "organization": candidate["organization"],
        "unnecessary_change": candidate["unnecessary_change"],
    }


def percentile(sorted_values, probability):
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (
        position - lower
    )


def bootstrap(documents, settings):
    strata = defaultdict(list)
    for document in documents:
        strata[document["category"]]
        if document["score"] is not None:
            strata[document["category"]].append(document["score"])
    groups = [strata[key] for key in sorted(strata)]
    result = {
        "method": "category-stratified document percentile bootstrap; linear quantiles",
        "confidence": settings["confidence"],
        "samples": settings["bootstrap_samples"],
        "seed": settings["bootstrap_seed"],
        "documents_by_category": {key: len(strata[key]) for key in sorted(strata)},
        "interval": None,
    }
    if not groups or any(not group for group in groups):
        result["unavailable_reason"] = (
            "At least one planned category has no scored documents"
        )
        return result
    rng = random.Random(settings["bootstrap_seed"])
    size = sum(map(len, groups))
    samples = sorted(
        math.fsum(group[rng.randrange(len(group))] for group in groups for _ in group)
        / size
        for _ in range(settings["bootstrap_samples"])
    )
    alpha = (1 - settings["confidence"]) / 2
    result["interval"] = [percentile(samples, alpha), percentile(samples, 1 - alpha)]
    return result


def outcome_counts(rows, pair):
    winners = Counter(row["winner"] for row in rows if row["winner"] is not None)
    valid = sum(winners.values())
    return {
        "planned_jobs": len(rows),
        "valid_jobs": valid,
        "missing_jobs": len(rows) - valid,
        "positive_wins": winners[pair[1]],
        "negative_wins": winners[pair[0]],
        "ties": winners["tie"],
        "uncertain": winners["uncertain"],
        "job_score_sum": winners[pair[1]] - winners[pair[0]],
        "valid_fraction": fraction(valid, len(rows)),
    }


def paired_average(rows, pair, per_document=False):
    result = {}
    for measure in MEASURES:
        valid = [row for row in rows if row[measure][pair[0]] is not None]
        result[measure] = {
            arm: mean(row[measure][arm] for row in valid) for arm in pair
        }
        result[measure]["right_minus_left"] = mean(
            row[measure][pair[1]] - row[measure][pair[0]] for row in valid
        )
        result[measure][
            "contributing_cases" if per_document else "valid_repetitions"
        ] = len(valid)
        if per_document:
            result[measure]["contributing_jobs"] = sum(
                row[measure]["valid_repetitions"] for row in valid
            )
            result[measure]["document_value_sums"] = {
                arm: math.fsum(row[measure][arm] for row in valid) for arm in pair
            }
    return result


def comparison(frozen, index, judgments, split, pair, settings):
    documents, rows = [], []
    cases = sorted(
        (case for case in frozen["inputs"]["cases"] if case["split"] == split),
        key=lambda c: c["id"],
    )
    for case in cases:
        repetitions, paired = [], []
        jobs = sorted(
            (
                job
                for job in frozen["jobs"]["judges"]
                if job["case"] == case["id"]
                and job["pair"] == pair
                and job["kind"] == "primary"
            ),
            key=lambda j: j["repetition"],
        )
        for job in jobs:
            entry = index["jobs"]["judges"][job["id"]]
            judgment = judgments.get(job["id"])
            row = {
                "job": job["id"],
                "repetition": job["repetition"],
                "selected_attempt": entry["selected_first_valid"],
                "status": entry["status"],
                "winner": None,
                "score": None,
            }
            if judgment is not None:
                winner = normalized_winner(job, judgment)
                row.update(
                    winner=winner,
                    score=1 if winner == pair[1] else -1 if winner == pair[0] else 0,
                )
                assessments = {
                    job[side]: candidate_measures(judgment["candidates"][side], case)
                    for side in ("left", "right")
                }
                row["assessments"] = assessments
                paired.append(
                    {
                        measure: {arm: assessments[arm][measure] for arm in pair}
                        for measure in MEASURES
                    }
                )
            repetitions.append(row)
        counts = outcome_counts(repetitions, pair)
        documents.append(
            {
                "case": case["id"],
                "category": frozen["inputs"]["case_metadata"][case["id"]]["category"],
                **counts,
                "score": mean(
                    row["score"] for row in repetitions if row["score"] is not None
                ),
                "paired": paired_average(paired, pair),
                "repetitions": repetitions,
            }
        )
        rows.extend(repetitions)
    scored = [doc for doc in documents if doc["score"] is not None]
    return {
        "positive_arm": pair[1],
        "negative_arm": pair[0],
        "confidence_family": "confirmatory"
        if split == "holdout" and pair == "BC"
        else "secondary_descriptive",
        **outcome_counts(rows, pair),
        "case_coverage": fraction(len(scored), len(documents)),
        "document_score_sum": math.fsum(doc["score"] for doc in scored),
        "effect": mean(doc["score"] for doc in scored),
        "bootstrap": bootstrap(documents, settings),
        "paired": paired_average(
            [doc["paired"] for doc in documents], pair, per_document=True
        ),
        "documents": documents,
    }


def order_consistency(frozen, index, judgments):
    jobs = {job["id"]: job for job in frozen["jobs"]["judges"]}
    rows = []
    for swap in sorted(
        (job for job in jobs.values() if job["kind"] == "swap"), key=lambda j: j["id"]
    ):
        primary = jobs[swap["primary_id"]]
        winners = [
            normalized_winner(job, judgments[job["id"]])
            if job["id"] in judgments
            else None
            for job in (primary, swap)
        ]
        eligible = all(winner is not None for winner in winners)
        rows.append(
            {
                "primary": primary["id"],
                "swap": swap["id"],
                "split": swap["split"],
                "pair": swap["pair"],
                "primary_status": index["jobs"]["judges"][primary["id"]]["status"],
                "swap_status": index["jobs"]["judges"][swap["id"]]["status"],
                "primary_winner": winners[0],
                "swap_winner": winners[1],
                "eligible": eligible,
                "agreement": winners[0] == winners[1] if eligible else None,
                "decisive_reversal": (set(winners) == set(swap["pair"]))
                if eligible
                else None,
            }
        )

    def counts(group):
        eligible = sum(row["eligible"] for row in group)
        agreements = sum(row["agreement"] is True for row in group)
        return {
            "planned": len(group),
            "eligible": eligible,
            "incomplete": len(group) - eligible,
            "agreements": agreements,
            "disagreements": eligible - agreements,
            "decisive_reversals": sum(
                row["decisive_reversal"] is True for row in group
            ),
            "agreement_fraction": fraction(agreements, eligible),
        }

    return {
        **counts(rows),
        "by_split": {
            split: {
                pair: counts(
                    [
                        row
                        for row in rows
                        if row["split"] == split and row["pair"] == pair
                    ]
                )
                for pair in ("AB", "BC")
            }
            for split in full.SPLITS
        },
        "pairs": rows,
    }


def regression_flags(frozen, judgments):
    flags, assessed = [], []
    for job in sorted(frozen["jobs"]["judges"], key=lambda j: j["id"]):
        if job["id"] not in judgments:
            continue
        for side in ("left", "right"):
            context = {
                key: job[key]
                for key in ("id", "case", "split", "category", "pair", "kind")
            }
            context.update(arm=job[side], writer=job[side + "_writer"])
            assessed.append(context)
            for flag in judgments[job["id"]]["candidates"][side]["regressions"]:
                if flag["severity"] not in SEVERITIES:
                    raise ValueError("Unsupported regression severity")
                flags.append(
                    {**context, "finding": flag, "adjudication": "not_performed"}
                )

    def group(split, arm):
        eligible = [
            row
            for row in assessed
            if row["kind"] == "primary"
            and row["arm"] == arm
            and (split == "all" or row["split"] == split)
        ]
        records = [
            row
            for row in flags
            if row["kind"] == "primary"
            and row["arm"] == arm
            and (split == "all" or row["split"] == split)
        ]
        denominator = len({row["writer"] for row in eligible})
        result = {}
        for severity in SEVERITIES:
            matching = [
                row for row in records if row["finding"]["severity"] == severity
            ]
            writers = sorted({row["writer"] for row in matching})
            result[severity] = {
                "writer_ids": writers,
                "flag_occurrences": len(matching),
                "flagged_writer_fraction": fraction(len(writers), denominator),
            }
        return result

    return {
        "primary": {
            split: {arm: group(split, arm) for arm in full.ARMS}
            for split in (*full.SPLITS, "all")
        },
        "all_flags_for_review": flags,
        "note": "Counts deduplicate writer IDs within severity; raw flags, including swaps, are not adjudicated or merged.",
    }


def words_report(frozen, writers):
    cases = {case["id"]: case for case in frozen["inputs"]["cases"]}
    rows = []
    for job in sorted(frozen["jobs"]["writers"], key=lambda j: j["id"]):
        draft = cases[job["case"]]["draft"]
        text = writers.get(job["id"])
        source_words = len(draft.split())
        row = {
            **job,
            "source_words": source_words,
            "output_words": None,
            "word_ratio": None,
            "unchanged_literal": None,
            "unchanged_ignoring_one_final_lf": None,
            "final_lf_only_change": None,
        }
        if text is not None:
            exact = text == draft
            equivalent = text.removesuffix("\n") == draft.removesuffix("\n")
            row.update(
                output_words=len(text.split()),
                word_ratio=len(text.split()) / source_words if source_words else None,
                unchanged_literal=exact,
                unchanged_ignoring_one_final_lf=equivalent,
                final_lf_only_change=equivalent and not exact,
            )
        rows.append(row)

    def group(subset):
        selected = [row for row in subset if row["output_words"] is not None]
        documents = []
        for ident in sorted({row["case"] for row in subset}):
            revisions = [row for row in selected if row["case"] == ident]
            documents.append(
                {
                    "case": ident,
                    "valid_repetitions": len(revisions),
                    "output_words": mean(row["output_words"] for row in revisions),
                    "word_ratio": mean(
                        row["word_ratio"]
                        for row in revisions
                        if row["word_ratio"] is not None
                    ),
                }
            )
        return {
            "selected_jobs": fraction(len(selected), len(subset)),
            "case_coverage": fraction(
                sum(doc["valid_repetitions"] > 0 for doc in documents), len(documents)
            ),
            "equal_case_mean_words": mean(
                doc["output_words"]
                for doc in documents
                if doc["output_words"] is not None
            ),
            "equal_case_mean_word_ratio": mean(
                doc["word_ratio"] for doc in documents if doc["word_ratio"] is not None
            ),
            "selected_job_mean_words": mean(row["output_words"] for row in selected),
            **{
                field: fraction(sum(row[field] for row in selected), len(selected))
                for field in (
                    "unchanged_literal",
                    "unchanged_ignoring_one_final_lf",
                    "final_lf_only_change",
                )
            },
            "documents": documents,
        }

    return {
        "by_split": {
            split: {
                arm: {
                    "all_categories": group(
                        [
                            row
                            for row in rows
                            if row["split"] == split and row["arm"] == arm
                        ]
                    ),
                    "by_category": {
                        category: group(
                            [
                                row
                                for row in rows
                                if row["split"] == split
                                and row["arm"] == arm
                                and row["category"] == category
                            ]
                        )
                        for category in full.CATEGORIES
                    },
                }
                for arm in full.ARMS
            }
            for split in full.SPLITS
        },
        "writers": rows,
        "note": "Whitespace-delimited words; ratios are descriptive, not quality scores. Frozen draft comparison ignores at most one terminal LF only where labeled.",
    }


def failure_class(attempt):
    if attempt["status"] == "valid":
        return None
    kind = attempt.get("failure_kind")
    if kind in ("semantic", "semantic_failure", "quality", "preservation"):
        return None
    # Provider/transport errors can also report a missing StructuredOutput as a
    # downstream symptom. The recorded failure kind identifies the failed stage.
    if kind != "schema_or_evidence":
        return kind or "unknown"
    text = " ".join(attempt.get("failures", [])).lower()
    schema = any(word in text for word in ("schema", "json", "structuredoutput"))
    evidence = any(word in text for word in ("evidence", "quote"))
    if evidence and not schema:
        return "evidence"
    if schema and not evidence:
        return "schema"
    # full.py intentionally collapses schema and evidence validation errors.
    return "schema_or_evidence"


def operational_report(frozen, index):
    usage, reliability, failures, non_validator, jobs = {}, {}, [], [], []
    for split in (*full.SPLITS, "all"):
        usage[split], reliability[split] = {}, {}
        for role in ("writers", "judges"):
            entries = [
                entry
                for _, entry in sorted(index["jobs"][role].items())
                if split == "all" or entry["split"] == split
            ]
            first = [entry["attempts"][0] for entry in entries if entry["attempts"]]
            retries = [
                attempt for entry in entries for attempt in entry["attempts"][1:]
            ]
            selected = [
                attempt
                for entry in entries
                for attempt in entry["attempts"]
                if attempt["attempt"] == entry["selected_first_valid"]
            ]
            usage[split][role] = {
                key: full.usage(attempts)
                for key, attempts in (
                    ("first_attempt", first),
                    ("retained_retries", retries),
                    ("all_attempts", first + retries),
                    ("selected_first_valid", selected),
                )
            }
            first_valid = sum(attempt["status"] == "valid" for attempt in first)
            recovered = sum(
                (entry["selected_first_valid"] or 0) > 1 for entry in entries
            )
            reliability[split][role] = {
                "planned": len(entries),
                "attempted": len(first),
                "attempts": len(first) + len(retries),
                "statuses": dict(
                    sorted(Counter(entry["status"] for entry in entries).items())
                ),
                "valid_coverage": fraction(len(selected), len(entries)),
                "first_attempt_validity": fraction(first_valid, len(first)),
                "retry_recovery": fraction(recovered, len(first) - first_valid),
                "terminal": sum(entry["terminal"] for entry in entries),
            }
    for role in ("writers", "judges"):
        for job in sorted(frozen["jobs"][role], key=lambda j: j["id"]):
            entry = index["jobs"][role][job["id"]]
            jobs.append({"role": role, **job, **entry})
            for attempt in entry["attempts"]:
                if attempt["status"] == "valid":
                    continue
                record = {
                    "role": role,
                    "job": job["id"],
                    "split": job["split"],
                    "attempt": attempt["attempt"],
                    "status": attempt["status"],
                    "failure_kind": attempt.get("failure_kind"),
                    "failures": attempt.get("failures", []),
                    "classification": failure_class(attempt),
                }
                (failures if record["classification"] else non_validator).append(record)
    return {
        "usage": usage,
        "reliability": reliability,
        "jobs": jobs,
        "unselected_jobs": [
            {key: job[key] for key in ("role", "id", "split", "status", "terminal")}
            for job in jobs
            if job["selected_first_valid"] is None
        ],
        "validator_failures": failures,
        "validator_failure_counts": dict(
            sorted(Counter(row["classification"] for row in failures).items())
        ),
        "non_validator_failures": non_validator,
        "notes": [
            "All retained attempts contribute usage, including failed attempts. Five token buckets are kept separate.",
            "Missing usage is unknown; adapter zero placeholders without observed steps are not observed zero usage.",
            "Retry recovery denominator is attempted jobs without a valid first attempt, including unfinished jobs.",
            "Semantic requirement failures, regression flags, and uncertainty on valid judgments are outcomes, not validator failures.",
            "Recorded failure_kind takes precedence over error wording; only schema_or_evidence outcomes are refined into schema or evidence failures.",
            "Generic schema-or-evidence failures cannot be separated retrospectively from their metadata.",
            "Reported cost is not subscription billing; provider retries are unavailable. Summed adapter seconds are not batch wall time.",
        ],
    }


def adoption_decision(comparisons, flags, settings):
    primary = comparisons["holdout"]["BC"]
    interval = primary["bootstrap"]["interval"]
    fidelity = primary["paired"]["requirement_failure_fraction"]
    # Equal rational rates can round differently across repetitions/documents.
    # Apply an absolute-only guard at the decision boundary, not to statistics.
    fidelity_roundoff_tolerance = 1e-12
    minimum = settings["minimum_valid_repetitions"]
    insufficient = [
        {"case": doc["case"], "valid_repetitions": doc["valid_jobs"]}
        for doc in primary["documents"]
        if doc["valid_jobs"] < minimum
    ]
    ratio = primary["valid_fraction"]["rate"]
    coverage = (
        bool(primary["documents"])
        and ratio is not None
        and ratio >= settings["minimum_valid_fraction"]
        and not insufficient
    )
    critical = [
        row
        for row in flags["all_flags_for_review"]
        if row["finding"]["severity"] == "critical"
    ]
    c_critical = [row for row in critical if row["arm"] == "C"]
    gates = {
        "positive_primary_interval": {
            "passed": interval is not None and interval[0] > 0,
            "interval": interval,
        },
        "paired_requirement_nonincrease": {
            "passed": fidelity["B"] is not None
            and fidelity["C"] is not None
            and (
                fidelity["C"] <= fidelity["B"]
                or math.isclose(
                    fidelity["C"],
                    fidelity["B"],
                    rel_tol=0.0,
                    abs_tol=fidelity_roundoff_tolerance,
                )
            ),
            "B": fidelity["B"],
            "C": fidelity["C"],
            "C_minus_B": fidelity["right_minus_left"],
            "contributing_cases": fidelity["contributing_cases"],
            "absolute_roundoff_tolerance": fidelity_roundoff_tolerance,
            "relative_roundoff_tolerance": 0.0,
            "tolerance_note": "Numerical roundoff only; not a material noninferiority margin.",
        },
        "coverage": {
            "passed": coverage,
            "scope": "held-out primary BC judgments",
            "valid_jobs": primary["valid_fraction"],
            "minimum_valid_fraction": settings["minimum_valid_fraction"],
            "minimum_valid_repetitions_per_case": minimum,
            "insufficient_cases": insufficient,
            "cases_meeting_minimum": fraction(
                len(primary["documents"]) - len(insufficient), len(primary["documents"])
            ),
        },
        "critical_review": {
            "passed": None if c_critical else True,
            "status": "not_adjudicated",
            "all_critical_flag_occurrences": len(critical),
            "C_critical_flag_occurrences": len(c_critical),
            "C_flagged_writer_ids": sorted({row["writer"] for row in c_critical}),
            "confirmed_new_critical_regressions": None,
            "secondary_adjudication_required": bool(critical),
        },
    }
    eligible = all(
        gates[key]["passed"]
        for key in (
            "positive_primary_interval",
            "paired_requirement_nonincrease",
            "coverage",
        )
    )
    return {
        "recommendation": "eligible_pending_critical_review"
        if eligible
        else "retain_B",
        "automatic_adoption": False,
        "gates": gates,
        "note": "Eligibility is conditional evidence under the frozen plan, not proof. Critical flags and substantive disputes require source-grounded secondary adjudication; this program does not confirm or dismiss them.",
    }


def analyze(output, bootstrap_samples=None):
    output = Path(output)
    frozen = load_manifest(output)
    settings = settings_from_plan(frozen["analysis_plan"], bootstrap_samples)
    # jobindex.json is a replaceable, possibly stale execution cache. This helper
    # reconstructs its first-valid selection from finalized outcome metadata only.
    index = full.build_index(output, frozen, verify=False)
    writers, judgments = selected_data(output, frozen, index)
    comparisons = {
        split: {
            pair: comparison(frozen, index, judgments, split, pair, settings)
            for pair in ("AB", "BC")
        }
        for split in full.SPLITS
    }
    flags = regression_flags(frozen, judgments)
    operations = operational_report(frozen, index)
    return {
        "analysis_format_version": 1,
        "manifest_sha256": frozen["manifest_sha256"],
        "analysis_source_sha256": full.file_hash(Path(__file__)),
        "recorded_source_hashes": frozen["inputs"]["source_hashes"],
        "job_snapshot_sha256": full.json_hash(index["jobs"]),
        "all_jobs_terminal": all(job["terminal"] for job in operations["jobs"]),
        "all_jobs_valid": not operations["unselected_jobs"],
        "analysis_plan": frozen["analysis_plan"],
        "settings": settings,
        "comparisons": comparisons,
        "decision": adoption_decision(comparisons, flags, settings),
        "order_consistency": order_consistency(frozen, index, judgments),
        "regression_flags": flags,
        "word_counts": words_report(frozen, writers),
        "operations": operations,
        "raw_selected_findings": [
            {
                "job": job,
                "attempt": index["jobs"]["judges"][job["id"]]["selected_first_valid"],
                "judgment": judgments[job["id"]],
            }
            for job in sorted(frozen["jobs"]["judges"], key=lambda j: j["id"])
            if job["id"] in judgments
        ],
        "limitations": [
            "Held-out BC is the sole confirmatory confidence family. AB and development intervals are secondary/descriptive; no multiplicity-adjusted claims are made.",
            "Only valid primary repetitions are averaged within each document, followed by equal document weighting. Missing jobs are not uncertain outcomes or zero scores.",
            "Intervals condition on observed documents within planned categories; wholly missing categories give no interval. Coverage gates remain mandatory.",
            "Bootstrap units are documents within category, never repetitions or swaps. Scheduling/statistical seeds do not establish independence of model randomness.",
            "Requirement uncertainty is reported separately from failure. Clean documents with no known issues contribute null resolution, not zero.",
            "The manifest's own hash and selected native artifact hashes are checked; equality with live sources is intentionally not required.",
            "Analysis reads a metadata snapshot and does not lock ongoing execution. In-progress, blocked, failed, and pending jobs remain visible; regenerate after completion.",
            "Only the full judge contract's recognized fields are scored. Original selected findings are retained without programmatic adjudication.",
            frozen["analysis_plan"].get(
                "scope", "Synthetic frozen fixed-draft finalization only."
            ),
            frozen["analysis_plan"].get(
                "adjudication",
                "Label any secondary AI-assisted review and retain original assessments.",
            ),
        ],
    }


def markdown(report):
    def value(item):
        if item is None:
            return "—"
        return f"{item:.4f}" if isinstance(item, float) else str(item)

    lines = [
        "# Frozen full-suite analysis",
        "",
        "Recommendation: **" + report["decision"]["recommendation"] + "**",
        "",
        "Manifest: `" + report["manifest_sha256"] + "`",
        "",
        "## Primary judgments (swaps excluded)",
        "",
        "Positive scores favor B for AB and C for BC. Missing jobs are excluded from valid-repetition means and counted separately.",
        "",
        "| Split | Pair | Valid/planned jobs | Scored/planned cases | + wins | − wins | Ties | Uncertain | Missing | Equal-case effect | "
        + f"{report['settings']['confidence']:.0%} interval |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for split in full.SPLITS:
        for pair, item in report["comparisons"][split].items():
            cases = item["case_coverage"]
            interval = item["bootstrap"]["interval"]
            ci = (
                "—" if interval is None else "[" + ", ".join(map(value, interval)) + "]"
            )
            fields = [
                split,
                pair,
                f"{item['valid_jobs']}/{item['planned_jobs']}",
                f"{cases['numerator']}/{cases['denominator']}",
                item["positive_wins"],
                item["negative_wins"],
                item["ties"],
                item["uncertain"],
                item["missing_jobs"],
                value(item["effect"]),
                ci,
            ]
            lines.append("| " + " | ".join(map(str, fields)) + " |")
    lines += ["", "## Decision gates", ""]
    for name, gate in report["decision"]["gates"].items():
        lines.append(
            "- **"
            + name
            + "**: "
            + (
                "pending review"
                if gate["passed"] is None
                else "pass"
                if gate["passed"]
                else "fail"
            )
            + ". `"
            + full.json_text(gate).strip().replace("\n", " ")
            + "`"
        )
    lines += [
        "",
        report["decision"]["note"],
        "",
        "## Paired secondary measures",
        "",
        "Fractions are averaged within repetition/document, then equally across contributing documents. B is kept separate in AB and BC.",
        "",
        "| Split | Pair | Measure | Negative arm | Positive arm | Difference | Contributing cases | Contributing jobs |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for split in full.SPLITS:
        for pair, item in report["comparisons"][split].items():
            for measure, summary in item["paired"].items():
                lines.append(
                    "| "
                    + " | ".join(
                        map(
                            value,
                            (
                                split,
                                pair,
                                measure,
                                summary[pair[0]],
                                summary[pair[1]],
                                summary["right_minus_left"],
                                summary["contributing_cases"],
                                summary["contributing_jobs"],
                            ),
                        )
                    )
                    + " |"
                )
    order = report["order_consistency"]
    lines += [
        "",
        "## Order consistency",
        "",
        ", ".join(
            f"{key}: {order[key]}"
            for key in (
                "planned",
                "eligible",
                "incomplete",
                "agreements",
                "disagreements",
                "decisive_reversals",
            )
        )
        + ".",
        "Incomplete pairs have null agreement, not disagreement.",
        "",
        "## Regression flags",
        "",
        "Unique primary-assessed writer IDs per severity; repeated AB/BC assessments do not multiply writer counts.",
        "",
        "| Split | Arm | Severity | Flagged/assessed writers | Flag occurrences |",
        "| --- | --- | --- | --- | --- |",
    ]
    for split in full.SPLITS:
        for arm, severities in report["regression_flags"]["primary"][split].items():
            for severity, item in severities.items():
                count = item["flagged_writer_fraction"]
                lines.append(
                    f"| {split} | {arm} | {severity} | {count['numerator']}/{count['denominator']} | {item['flag_occurrences']} |"
                )
    lines += [
        "",
        "All original flags (including swaps), quotations, explanations, and selected judgments are preserved in `analysis.json` for secondary review.",
        "",
        "## Word counts and clean controls",
        "",
        "| Split | Arm | Group | Selected/planned writers | Equal-case words | Word ratio | Literal unchanged | Ignoring one final LF | LF-only change |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for split, arms in report["word_counts"]["by_split"].items():
        for arm, groups in arms.items():
            for name, item in (
                ("all", groups["all_categories"]),
                ("clean-controls", groups["by_category"]["clean-controls"]),
            ):
                count = item["selected_jobs"]
                unchanged = [
                    f"{item[key]['numerator']}/{item[key]['denominator']}"
                    for key in (
                        "unchanged_literal",
                        "unchanged_ignoring_one_final_lf",
                        "final_lf_only_change",
                    )
                ]
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            split,
                            arm,
                            name,
                            f"{count['numerator']}/{count['denominator']}",
                            value(item["equal_case_mean_words"]),
                            value(item["equal_case_mean_word_ratio"]),
                            *unchanged,
                        ]
                    )
                    + " |"
                )
    lines += [
        "",
        report["word_counts"]["note"],
        "",
        "## Operational reliability and all-attempt usage",
        "",
    ]
    for split in full.SPLITS:
        for role, reliability in report["operations"]["reliability"][split].items():
            lines += [
                f"### {split} / {role}",
                "",
                "```json",
                full.json_text(reliability).strip(),
                "```",
                "",
                "| Token bucket | Sum | Known attempts | Unknown attempts |",
                "| --- | --- | --- | --- |",
            ]
            usage = report["operations"]["usage"][split][role]["all_attempts"]
            for token, item in usage["tokens"].items():
                lines.append(
                    f"| {token} | {item['sum']} | {item['known_attempts']} | {item['unknown_attempts']} |"
                )
            for field in ("seconds", "reported_cost"):
                item = usage[field]
                lines.append(
                    f"- {field}: {item['sum']}; known attempts {item['known_attempts']}, unknown {item['unknown_attempts']}."
                )
            lines.append("")
    lines += [
        "## Jobs without a selected valid result",
        "",
        "| Role | Job | Split | Status | Terminal |",
        "| --- | --- | --- | --- | --- |",
    ]
    for job in report["operations"]["unselected_jobs"]:
        lines.append(
            "| "
            + " | ".join(
                str(job[key]) for key in ("role", "id", "split", "status", "terminal")
            )
            + " |"
        )
    if not report["operations"]["unselected_jobs"]:
        lines.append("\nNone.")
    lines += [
        "",
        "## Validator/transport failures",
        "",
        "| Role | Job | Attempt | Classification |",
        "| --- | --- | --- | --- |",
    ]
    for failure in report["operations"]["validator_failures"]:
        lines.append(
            "| "
            + " | ".join(
                str(failure[key])
                for key in ("role", "job", "attempt", "classification")
            )
            + " |"
        )
    lines += [
        "",
        "Full metadata, failure messages, first-attempt/retry usage, per-document denominators, and incomplete order-pair details are in `analysis.json`.",
        "",
        "## Interpretation and limitations",
        "",
    ]
    lines.extend(
        "- " + note for note in report["limitations"] + report["operations"]["notes"]
    )
    return "\n".join(lines) + "\n"


def write_reports(output, report):
    # Atomic replacement is restricted to these two regenerable reports.
    for name, text in (
        ("analysis.json", full.json_text(report)),
        ("analysis.md", markdown(report)),
    ):
        path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=output,
                prefix="." + name + ".",
                delete=False,
            ) as stream:
                path = Path(stream.name)
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(path, output / name)
        finally:
            if path is not None:
                path.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--bootstrap-samples",
        type=int,
        default=None,
        help="Default: frozen analysis_plan (10000); an explicit value must match the freeze",
    )
    args = parser.parse_args(argv)
    try:
        report = analyze(args.output, args.bootstrap_samples)
        write_reports(args.output, report)
    except (ValueError, OSError, KeyError, TypeError, StopIteration) as error:
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        print("Error: " + message, file=sys.stderr)
        return 1
    print(
        "Wrote analysis.json and analysis.md; recommendation: "
        + report["decision"]["recommendation"]
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
