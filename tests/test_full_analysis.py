"""Synthetic-only tests: never load repository fixtures or recorded results."""

import contextlib
import copy
from fractions import Fraction
import importlib.util
import io
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[1] / "evals/documenting/full_analysis.py"
SPEC = importlib.util.spec_from_file_location("_test_full_analysis", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise ValueError("Cannot import analyzer")
analysis = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = analysis
SPEC.loader.exec_module(analysis)
full = analysis.full


def synthetic_cases(include_development=True):
    routing = [
        ("h-clean", "holdout", "clean-controls"),
        ("h-issues", "holdout", "organization"),
    ]
    if include_development:
        routing.append(("d-clean", "development", "clean-controls"))
    cases, metadata = [], {}
    for ident, split, category in routing:
        case = {
            "id": ident,
            "split": split,
            "family": "synthetic-" + ident,
            "task": "Keep synthetic facts.",
            "source_facts": "Alpha stays. Beta stays.",
            "draft": "Alpha stays.\nBeta stays.",
            "requirements": [
                {"id": "r" + str(n), "text": "Synthetic requirement."} for n in range(4)
            ],
            "issues": []
            if category == "clean-controls"
            else [{"id": "i" + str(n), "text": "Synthetic issue."} for n in range(4)],
            "checks": [],
        }
        cases.append(case)
        metadata[ident] = {
            "split": split,
            "category": category,
            "embedded_sha256": full.json_hash(case),
            "source": "not-a-live-fixture.json",
            "source_sha256": "recorded-only",
        }
    return cases, metadata


class SyntheticRun:
    def __init__(
        self, root, include_development=True, swap_pairs=("AB", "BC"), case_data=None
    ):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        cases, metadata = (
            synthetic_cases(include_development) if case_data is None else case_data
        )
        self.cases = {case["id"]: case for case in cases}
        self.frozen = full.make_manifest(
            {
                "cases": cases,
                "case_metadata": metadata,
                "systems": {arm: "Synthetic unused prompt." for arm in "ABC"},
                "judge_system": "Synthetic unused judge.",
                "judge_schemas": {},
                "source_hashes": {"nonexistent-live-source.py": "frozen-source-hash"},
            },
            seed=19,
        )
        primaries = [
            job for job in self.frozen["jobs"]["judges"] if job["kind"] == "primary"
        ]
        swaps = [
            {
                **job,
                "id": job["id"].replace("-primary", "-swap"),
                "kind": "swap",
                "left": job["right"],
                "right": job["left"],
                "left_writer": job["right_writer"],
                "right_writer": job["left_writer"],
            }
            for job in primaries
            if job["pair"] in swap_pairs
        ]
        self.frozen["jobs"]["judges"] = primaries + swaps
        self.save_manifest()
        self.writers = {job["id"]: job for job in self.frozen["jobs"]["writers"]}
        self.judges = {job["id"]: job for job in self.frozen["jobs"]["judges"]}
        self.writer_attempts = {}

    def save_manifest(self):
        self.frozen.pop("manifest_sha256", None)
        self.frozen["manifest_sha256"] = full.json_hash(self.frozen)
        self.write_json(self.root / "manifest.json", self.frozen)

    @staticmethod
    def write_json(path, value):
        path.write_text(full.json_text(value), encoding="utf-8")

    @staticmethod
    def metrics(observed=True):
        return {
            "seconds": 1.25,
            "observed_model_steps": int(observed),
            "reported_cost": 0.125 if observed else 0,
            "tokens": {
                token: (n + 1) * 10 if observed else 0
                for n, token in enumerate(full.TOKENS)
            },
            "output_words": 4,
            "check_count": 2,
            "failed_check_count": 1,
        }

    def attempt(
        self,
        role,
        ident,
        number=1,
        status="valid",
        kind=None,
        failures=None,
        artifacts=None,
        observed=True,
    ):
        folder = self.root / role / ident / ("attempt-" + str(number))
        folder.mkdir(parents=True, exist_ok=True)
        for name, value in (artifacts or {}).items():
            if isinstance(value, str):
                (folder / name).write_text(value, encoding="utf-8")
            else:
                self.write_json(folder / name, value)
        full.finalize_attempt(
            folder, self.metrics(observed), status, kind, failures or [], 1.5
        )
        return folder

    def writer(self, ident, text=None, number=1):
        job = self.writers[ident]
        if text is None:
            text = self.cases[job["case"]]["draft"]
        self.attempt("writers", ident, number, artifacts={"output.md": text})
        self.writer_attempts.setdefault(ident, number)

    def judgment(self, job, winner=None, candidate=None):
        candidates = {}
        for side in ("left", "right"):
            case = self.cases[job["case"]]
            item = {
                "requirements": {
                    entry["id"]: {
                        "status": "pass",
                        "quote": "Alpha",
                        "explanation": "Synthetic evidence.",
                    }
                    for entry in case["requirements"]
                },
                "issues": {
                    entry["id"]: {
                        "status": "resolved",
                        "quote": "Alpha",
                        "explanation": "Synthetic evidence.",
                    }
                    for entry in case["issues"]
                },
                "regressions": [],
                "organization": 5,
                "unnecessary_change": 0,
            }
            if candidate is not None:
                candidate(job, job[side], item)
            candidates[side] = item
        winner = job["pair"][1] if winner is None else winner
        return {
            "candidates": candidates,
            "winner": next(
                (side for side in ("left", "right") if job[side] == winner), winner
            ),
            "reason": "Synthetic comparison only.",
        }

    def judge(self, ident, winner=None, number=1, candidate=None):
        job = self.judges[ident]
        mapping = {
            key: job[key]
            for key in (
                "case",
                "repetition",
                "pair",
                "kind",
                "primary_id",
                "left",
                "right",
            )
        }
        mapping["writers"] = {}
        for side in ("left", "right"):
            writer = job[side + "_writer"]
            attempt = self.writer_attempts[writer]
            output = (
                self.root
                / "writers"
                / writer
                / ("attempt-" + str(attempt))
                / "output.md"
            )
            mapping["writers"][side] = {
                "job": writer,
                "attempt": attempt,
                "output_sha256": full.file_hash(output),
            }
        judgment = self.judgment(job, winner, candidate)
        self.attempt(
            "judges",
            ident,
            number,
            artifacts={"judgment.json": judgment, "mapping.json": mapping},
        )
        return judgment

    def populate(self, skip=(), winners=None, candidate=None):
        for ident in self.writers:
            self.writer(ident)
        for ident, job in self.judges.items():
            if ident not in skip:
                self.judge(
                    ident, winner=winners(job) if winners else None, candidate=candidate
                )


class FullAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="full-analysis-synthetic-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def run_fixture(self, **options):
        return SyntheticRun(self.root, **options)

    def test_manifest_integrity_and_analysis_ignore_live_sources(self):
        run = self.run_fixture()
        with (
            mock.patch.object(
                full, "load_inputs", side_effect=AssertionError("No live inputs")
            ),
            mock.patch.object(
                full,
                "load_frozen",
                side_effect=AssertionError("No live freeze comparison"),
            ),
            mock.patch.object(
                full.base, "call_model", side_effect=AssertionError("No inference")
            ),
        ):
            report = analysis.analyze(self.root)
        self.assertEqual(report["settings"]["bootstrap_seed"], 46075)
        self.assertNotEqual(report["settings"]["bootstrap_seed"], run.frozen["seed"])
        self.assertEqual(report["settings"]["bootstrap_samples"], 10000)
        self.assertEqual(report["decision"]["recommendation"], "retain_B")
        self.assertFalse(report["all_jobs_terminal"])
        self.assertIsNone(report["comparisons"]["holdout"]["BC"]["effect"])
        self.assertEqual(
            len(report["operations"]["unselected_jobs"]),
            sum(map(len, run.frozen["jobs"].values())),
        )
        run.frozen["seed"] += 1
        run.write_json(self.root / "manifest.json", run.frozen)
        with self.assertRaisesRegex(ValueError, "Manifest hash mismatch"):
            analysis.analyze(self.root)

    def test_frozen_plan_is_authoritative_and_rejects_semantic_overrides(self):
        run = self.run_fixture()
        plan = copy.deepcopy(run.frozen["analysis_plan"])
        plan["uncertainty"] = (
            plan["uncertainty"].replace("10000", "80").replace("46075", "91")
        )
        plan["coverage_gate"] = plan["coverage_gate"].replace("90%", "95%")
        settings = analysis.settings_from_plan(plan, 80)
        self.assertEqual(settings["bootstrap_samples"], 80)
        self.assertEqual(settings["bootstrap_seed"], 91)
        self.assertEqual(settings["minimum_valid_fraction"], 0.95)
        with self.assertRaisesRegex(ValueError, "must match"):
            analysis.settings_from_plan(plan, 10000)
        plan["primary_score"] = "Pool repetitions and treat missing as zero"
        with self.assertRaisesRegex(ValueError, "Unsupported frozen analysis policy"):
            analysis.settings_from_plan(plan)

    def test_stratified_bootstrap_determinism_ties_and_positive_preference(self):
        settings = analysis.settings_from_plan(
            self.run_fixture().frozen["analysis_plan"]
        )
        documents = [
            {"category": category, "score": score}
            for category in full.CATEGORIES
            for score in (-1, 1)
        ]
        result = analysis.bootstrap(documents, settings)
        self.assertEqual(result, analysis.bootstrap(documents, settings))
        self.assertEqual(
            result["documents_by_category"], dict.fromkeys(full.CATEGORIES, 2)
        )
        # Twelve independently sampled document positions, each +/-1: the central
        # P(K <= 2)=79/4096 < .025; P(K <= 3)=299/4096 > .025.
        # The 95% binomial percentile interval is [-1/2, 1/2].
        self.assertEqual(result["interval"], [-0.5, 0.5])
        for score, interval in ((0, [0, 0]), (1, [1, 1])):
            for document in documents:
                document["score"] = score
            self.assertEqual(
                analysis.bootstrap(documents, settings)["interval"], interval
            )
        documents[0]["score"] = documents[1]["score"] = None
        self.assertIsNone(analysis.bootstrap(documents, settings)["interval"])
        # Unequal strata preserve document weights and category composition;
        # pooling the resampling or weighting categories equally changes this CI.
        unequal = [{"category": "clean-controls", "score": 1}] + [
            {"category": "organization", "score": -1} for _ in range(3)
        ]
        self.assertEqual(
            analysis.bootstrap(unequal, settings)["interval"], [-0.5, -0.5]
        )

    def test_equal_case_weighting_missing_tie_uncertainty_and_orientation(self):
        run = self.run_fixture()
        missing = {"h-clean-r2-BC-primary", "h-clean-r3-BC-primary"}

        def winner(job):
            if job["kind"] == "swap":
                return job["pair"][0]
            if job["pair"] == "BC" and job["case"] == "h-issues":
                return {1: "tie", 2: "uncertain", 3: "B"}[job["repetition"]]
            return job["pair"][1]

        run.populate(skip=missing, winners=winner)
        report = analysis.analyze(self.root)
        primary = report["comparisons"]["holdout"]["BC"]
        self.assertEqual(
            {job["left"] for job in run.judges.values() if job["pair"] == "BC"},
            {"B", "C"},
        )
        self.assertAlmostEqual(primary["effect"], 1 / 3)
        self.assertEqual(primary["job_score_sum"], 0)
        self.assertEqual(
            [
                primary[key]
                for key in (
                    "planned_jobs",
                    "valid_jobs",
                    "missing_jobs",
                    "ties",
                    "uncertain",
                )
            ],
            [6, 4, 2, 1, 1],
        )
        self.assertEqual(primary["case_coverage"], analysis.fraction(2, 2))
        self.assertEqual(report["comparisons"]["development"]["BC"]["effect"], 1)
        self.assertEqual(report["comparisons"]["holdout"]["AB"]["effect"], 1)
        self.assertEqual(primary["confidence_family"], "confirmatory")
        self.assertEqual(
            report["comparisons"]["holdout"]["AB"]["confidence_family"],
            "secondary_descriptive",
        )
        gates = report["decision"]["gates"]
        self.assertFalse(gates["coverage"]["passed"])
        self.assertEqual(
            gates["coverage"]["insufficient_cases"],
            [{"case": "h-clean", "valid_repetitions": 1}],
        )
        clean = primary["documents"][0]
        self.assertIsNone(clean["repetitions"][1]["score"])
        self.assertEqual(primary["documents"][1]["repetitions"][1]["score"], 0)

    def test_paired_fractions_clean_null_and_no_double_counting_B(self):
        run = self.run_fixture(include_development=False)

        def candidate(job, arm, item):
            if job["pair"] == "AB" and arm == "B":
                statuses = ["fail"] * 4
            elif arm == "C":
                statuses = ["pass", "fail", "uncertain", "pass"]
            else:
                statuses = ["fail", "pass", "pass", "pass"]
            for entry, status in zip(item["requirements"].values(), statuses):
                entry["status"] = status
            for entry, status in zip(
                item["issues"].values(),
                ("resolved", "partial", "unresolved", "uncertain"),
            ):
                entry["status"] = status
            # Extra/regional fields remain raw and never replace recognized scores.
            item["regional_quality"] = {
                "known_issue_resolution": 999,
                "organization": -99,
            }

        run.populate(candidate=candidate)
        report = analysis.analyze(self.root)
        bc = report["comparisons"]["holdout"]["BC"]
        ab = report["comparisons"]["holdout"]["AB"]
        self.assertEqual(ab["paired"]["requirement_failure_fraction"]["B"], 1)
        self.assertEqual(bc["paired"]["requirement_failure_fraction"]["B"], 0.25)
        self.assertEqual(bc["paired"]["requirement_failure_fraction"]["C"], 0.25)
        self.assertEqual(bc["paired"]["requirement_uncertainty_fraction"]["C"], 0.25)
        self.assertEqual(bc["paired"]["requirement_uncertainty_fraction"]["B"], 0)
        self.assertEqual(bc["paired"]["known_issue_resolution"]["C"], 0.375)
        self.assertEqual(
            bc["paired"]["known_issue_resolution"]["contributing_cases"], 1
        )
        self.assertIsNone(bc["documents"][0]["paired"]["known_issue_resolution"]["C"])
        counts = bc["documents"][1]["repetitions"][0]["assessments"]["C"]["counts"]
        self.assertEqual(
            counts["requirements"], {"pass": 2, "fail": 1, "uncertain": 1, "total": 4}
        )
        self.assertEqual(
            counts["issues"],
            {"resolved": 1, "partial": 1, "unresolved": 1, "uncertain": 1, "total": 4},
        )
        self.assertEqual(bc["paired"]["organization"]["C"], 5)
        self.assertEqual(
            report["decision"]["recommendation"], "eligible_pending_critical_review"
        )
        raw = report["raw_selected_findings"][0]["judgment"]["candidates"]["left"]
        self.assertEqual(raw["regional_quality"]["known_issue_resolution"], 999)

    def test_paired_fractions_average_atoms_then_repetitions_then_documents(self):
        run = self.run_fixture(include_development=False, swap_pairs=())
        case = run.cases["h-issues"]
        case["requirements"] = case["requirements"][:2]
        run.frozen["inputs"]["case_metadata"][case["id"]]["embedded_sha256"] = (
            full.json_hash(case)
        )
        run.save_manifest()

        def candidate(job, arm, item):
            if arm != "C":
                return
            failures = 1 if job["case"] == "h-clean" else 3 - job["repetition"]
            for position, entry in enumerate(item["requirements"].values()):
                entry["status"] = "fail" if position < failures else "pass"
            if job["case"] == "h-clean":
                item["requirements"]["r3"]["status"] = "uncertain"

        run.populate(
            skip={"h-clean-r2-BC-primary", "h-clean-r3-BC-primary"}, candidate=candidate
        )
        paired = analysis.analyze(self.root)["comparisons"]["holdout"]["BC"]["paired"]
        failures = paired["requirement_failure_fraction"]
        # Case means: 1/4 and mean(2/2, 1/2, 0/2)=1/2. This is neither
        # a pooled atom fraction (4/10) nor a pooled repetition mean (7/16).
        self.assertEqual(failures["C"], 3 / 8)
        self.assertEqual(failures["B"], 0)
        self.assertEqual(failures["right_minus_left"], 3 / 8)
        self.assertEqual(failures["document_value_sums"]["C"], 3 / 4)
        self.assertEqual(failures["contributing_cases"], 2)
        self.assertEqual(failures["contributing_jobs"], 4)
        self.assertEqual(paired["requirement_uncertainty_fraction"]["C"], 1 / 8)
        self.assertEqual(paired["known_issue_resolution"]["C"], 1)
        self.assertEqual(paired["known_issue_resolution"]["contributing_cases"], 1)
        self.assertEqual(paired["known_issue_resolution"]["contributing_jobs"], 3)

    def test_equal_exact_fidelity_roundoff_preserves_adoption_eligibility(self):
        templates, _ = synthetic_cases(include_development=False)
        cases, metadata = [], {}
        for category in full.CATEGORIES:
            for _ in range(4):
                case = copy.deepcopy(templates[0])
                case["id"] = "h-roundoff-" + str(len(cases)).zfill(2)
                case["family"] = "synthetic-" + case["id"]
                case["requirements"] = [
                    {"id": "r" + str(n), "text": "Synthetic requirement."}
                    for n in range(10)
                ]
                cases.append(case)
                metadata[case["id"]] = {
                    "split": "holdout",
                    "category": category,
                    "embedded_sha256": full.json_hash(case),
                    "source": "not-a-live-fixture.json",
                    "source_sha256": "recorded-only",
                }
        run = self.run_fixture(swap_pairs=(), case_data=(cases, metadata))
        failure_counts = {"B": (0, 0, 3), "C": (1, 1, 1)}

        def candidate(job, arm, item):
            if job["case"] != cases[0]["id"] or arm not in failure_counts:
                return
            failures = failure_counts[arm][job["repetition"] - 1]
            for position, entry in enumerate(item["requirements"].values()):
                entry["status"] = "fail" if position < failures else "pass"

        run.populate(candidate=candidate)
        report = analysis.analyze(self.root)
        primary = report["comparisons"]["holdout"]["BC"]
        fidelity = primary["paired"]["requirement_failure_fraction"]
        for arm, counts in failure_counts.items():
            # Independent rational arithmetic establishes equality; keep the
            # original floating-point statistics rather than rounding reports.
            exact = sum(Fraction(count, 10) for count in counts) / 3 / 24
            self.assertEqual(exact, Fraction(1, 240))
            unrounded = analysis.mean(
                [analysis.mean(count / 10 for count in counts)] + [0] * 23
            )
            self.assertEqual(fidelity[arm], unrounded)
        self.assertGreater(fidelity["C"], fidelity["B"])
        self.assertEqual(primary["bootstrap"]["interval"], [1, 1])
        self.assertEqual(primary["valid_fraction"], analysis.fraction(72, 72))
        decision = report["decision"]
        self.assertTrue(decision["gates"]["positive_primary_interval"]["passed"])
        self.assertTrue(decision["gates"]["coverage"]["passed"])
        gate = decision["gates"]["paired_requirement_nonincrease"]
        self.assertTrue(gate["passed"])
        self.assertEqual(decision["recommendation"], "eligible_pending_critical_review")
        self.assertFalse(decision["automatic_adoption"])
        self.assertEqual(gate["absolute_roundoff_tolerance"], 1e-12)
        self.assertEqual(gate["relative_roundoff_tolerance"], 0.0)
        self.assertIn("not a material noninferiority margin", gate["tolerance_note"])
        self.assertIn(gate["tolerance_note"], analysis.markdown(report))

    def test_fidelity_roundoff_tolerance_is_tight_and_absolute_only(self):
        settings = analysis.settings_from_plan(
            self.run_fixture().frozen["analysis_plan"]
        )
        primary = {
            "bootstrap": {"interval": [1, 1]},
            "valid_fraction": analysis.fraction(72, 72),
            "documents": [
                {"case": "synthetic-" + str(n), "valid_jobs": 3} for n in range(24)
            ],
            "paired": {},
        }
        for b, c, passed in (
            (0.0, 1e-12, True),
            (0.0, math.nextafter(1e-12, math.inf), False),
            (0.5, 0.5 + 2e-12, False),
            (0.5, 0.5, True),
            (0.5, 0.25, True),
            (None, 0.0, False),
            (0.0, None, False),
        ):
            with self.subTest(B=b, C=c):
                primary["paired"]["requirement_failure_fraction"] = {
                    "B": b,
                    "C": c,
                    "contributing_cases": 24,
                    "right_minus_left": c - b
                    if b is not None and c is not None
                    else None,
                }
                decision = analysis.adoption_decision(
                    {"holdout": {"BC": primary}}, {"all_flags_for_review": []}, settings
                )
                self.assertEqual(
                    decision["gates"]["paired_requirement_nonincrease"]["passed"],
                    passed,
                )
                self.assertEqual(
                    decision["recommendation"],
                    "eligible_pending_critical_review" if passed else "retain_B",
                )

    def test_worse_secondary_fidelity_blocks_positive_primary(self):
        run = self.run_fixture()

        def candidate(job, arm, item):
            if arm == "C":
                item["requirements"]["r0"]["status"] = "fail"

        run.populate(candidate=candidate)
        decision = analysis.analyze(self.root)["decision"]
        self.assertEqual(
            decision["gates"]["positive_primary_interval"]["interval"], [1, 1]
        )
        self.assertTrue(decision["gates"]["coverage"]["passed"])
        self.assertFalse(decision["gates"]["paired_requirement_nonincrease"]["passed"])
        self.assertEqual(
            decision["gates"]["paired_requirement_nonincrease"]["C_minus_B"], 0.25
        )
        self.assertEqual(decision["recommendation"], "retain_B")

    def test_coverage_gate_requires_rate_and_every_case_independently(self):
        run = self.run_fixture()
        run.populate()
        report = analysis.analyze(self.root)
        comparisons = copy.deepcopy(report["comparisons"])
        primary = comparisons["holdout"]["BC"]
        primary["valid_fraction"] = analysis.fraction(65, 72)
        primary["documents"][0]["valid_jobs"] = 1
        decision = analysis.adoption_decision(
            comparisons, report["regression_flags"], report["settings"]
        )
        self.assertFalse(decision["gates"]["coverage"]["passed"])
        primary["documents"][0]["valid_jobs"] = 2
        self.assertTrue(
            analysis.adoption_decision(
                comparisons, report["regression_flags"], report["settings"]
            )["gates"]["coverage"]["passed"]
        )
        primary["valid_fraction"] = analysis.fraction(64, 72)
        self.assertFalse(
            analysis.adoption_decision(
                comparisons, report["regression_flags"], report["settings"]
            )["gates"]["coverage"]["passed"]
        )

    def test_regression_counts_deduplicate_writers_and_preserve_swap_flags(self):
        run = self.run_fixture()

        def candidate(job, arm, item):
            if arm == "B":
                item["regressions"] = [
                    {
                        "severity": severity,
                        "quote": "Alpha",
                        "explanation": "Synthetic new problem.",
                    }
                    for severity in ("critical", "critical", "minor")
                ]
            if arm == "C" and job["id"] == "h-clean-r1-BC-swap":
                item["regressions"] = [
                    {
                        "severity": "critical",
                        "quote": "",
                        "explanation": "Synthetic omitted fact.",
                    }
                ]

        run.populate(candidate=candidate)
        report = analysis.analyze(self.root)
        flags = report["regression_flags"]
        critical = flags["primary"]["all"]["B"]["critical"]
        self.assertEqual(critical["flagged_writer_fraction"], analysis.fraction(9, 9))
        self.assertEqual(critical["flag_occurrences"], 36)
        self.assertEqual(
            flags["primary"]["all"]["C"]["critical"]["flagged_writer_fraction"][
                "numerator"
            ],
            0,
        )
        self.assertEqual(len(flags["all_flags_for_review"]), 109)
        decision = report["decision"]
        self.assertEqual(decision["recommendation"], "eligible_pending_critical_review")
        self.assertFalse(decision["automatic_adoption"])
        self.assertTrue(
            decision["gates"]["critical_review"]["secondary_adjudication_required"]
        )
        self.assertIsNone(decision["gates"]["critical_review"]["passed"])
        self.assertIsNone(
            decision["gates"]["critical_review"]["confirmed_new_critical_regressions"]
        )

    def test_order_selected_retries_only_and_incomplete_is_not_disagreement(self):
        run = self.run_fixture(include_development=False, swap_pairs=("BC",))
        for ident in run.writers:
            run.writer(ident)
        primaries = sorted(
            (
                job
                for job in run.judges.values()
                if job["kind"] == "primary" and job["pair"] == "BC"
            ),
            key=lambda j: j["id"],
        )
        outcomes = [
            ("C", "C"),
            ("B", "C"),
            ("tie", "uncertain"),
            ("uncertain", "uncertain"),
            (None, "C"),
            ("C", None),
        ]
        failed_folder = None
        for index, (job, (primary, swap)) in enumerate(zip(primaries, outcomes)):
            if primary is not None:
                if index == 1:
                    failed_folder = run.attempt(
                        "judges",
                        job["id"],
                        status="failed",
                        kind="schema_or_evidence",
                        failures=["Judge schema or quote evidence validation failed"],
                        artifacts={
                            "judgment.json": run.judgment(job, "C"),
                            "raw-response.json": {"winner": "C"},
                        },
                    )
                run.judge(job["id"], primary, number=2 if index == 1 else 1)
            if swap is not None:
                run.judge(job["id"].replace("-primary", "-swap"), swap)
        run.write_json(
            self.root / "jobindex.json", {"stale": True, "selected_first_valid": 1}
        )
        original_read = Path.read_bytes

        def guarded_read(path):
            if path.parent == failed_folder and path.name != "outcome.json":
                raise AssertionError("Failed native payload must not be read")
            return original_read(path)

        with mock.patch.object(Path, "read_bytes", guarded_read):
            report = analysis.analyze(self.root)
        order = report["order_consistency"]
        self.assertEqual(
            [
                order[key]
                for key in (
                    "planned",
                    "eligible",
                    "incomplete",
                    "agreements",
                    "disagreements",
                    "decisive_reversals",
                )
            ],
            [6, 4, 2, 2, 2, 1],
        )
        self.assertEqual(order["agreement_fraction"], analysis.fraction(2, 4))
        self.assertTrue(
            all(
                row["agreement"] is None
                for row in order["pairs"]
                if not row["eligible"]
            )
        )
        recovered = next(
            row
            for row in report["raw_selected_findings"]
            if row["job"]["id"] == primaries[1]["id"]
        )
        self.assertEqual(recovered["attempt"], 2)
        self.assertEqual(
            analysis.normalized_winner(recovered["job"], recovered["judgment"]), "B"
        )

    def test_first_valid_selection_does_not_use_later_valid_attempt(self):
        run = self.run_fixture(include_development=False, swap_pairs=())
        run.populate()
        run.judge("h-clean-r1-BC-primary", "B", number=2)
        report = analysis.analyze(self.root)
        self.assertEqual(report["comparisons"]["holdout"]["BC"]["effect"], 1)
        usage = report["operations"]["usage"]["holdout"]["judges"]
        self.assertEqual(usage["all_attempts"]["attempts"], 13)
        self.assertEqual(usage["selected_first_valid"]["attempts"], 12)
        self.assertEqual(usage["retained_retries"]["attempts"], 1)

    def test_failure_class_transport_kind_overrides_structuredoutput_errors(self):
        attempt = {
            "status": "failed",
            "failure_kind": "transport",
            "retryable": False,
            "failures": ["API HTTP 402 error", "Expected exactly one StructuredOutput"],
        }
        original = copy.deepcopy(attempt)
        self.assertEqual(analysis.failure_class(attempt), "transport")
        self.assertEqual(attempt, original)

    def test_failure_class_refines_schema_evidence_only_for_declared_kind(self):
        for kind in (
            None,
            "transport",
            "local_failure",
            "interrupted",
            "timeout",
            "schema_or_evidence",
        ):
            for message, refinement in (
                ("Expected exactly one StructuredOutput", "schema"),
                ("Quote evidence invalid", "evidence"),
                (
                    "Judge schema or quote evidence validation failed",
                    "schema_or_evidence",
                ),
                ("Validation failed", "schema_or_evidence"),
                ("Request timed out", "schema_or_evidence"),
            ):
                with self.subTest(kind=kind, message=message):
                    attempt = {
                        "status": "failed",
                        "failure_kind": kind,
                        "failures": [message],
                    }
                    expected = (
                        refinement
                        if kind == "schema_or_evidence"
                        else kind or "unknown"
                    )
                    self.assertEqual(analysis.failure_class(attempt), expected)

    def test_operational_failure_counts_keep_transport_structuredoutput_errors(self):
        run = self.run_fixture(include_development=False, swap_pairs=())
        failures = ["API HTTP 402 error", "Expected exactly one StructuredOutput"]
        for number in (1, 2):
            run.attempt(
                "judges",
                "h-clean-r1-BC-primary",
                number,
                status="failed",
                kind="transport",
                failures=failures,
                observed=False,
            )
        run.attempt(
            "judges",
            "h-clean-r2-BC-primary",
            status="failed",
            kind="schema_or_evidence",
            failures=["Expected exactly one StructuredOutput"],
        )
        operations = analysis.analyze(self.root)["operations"]
        self.assertEqual(
            operations["validator_failure_counts"], {"transport": 2, "schema": 1}
        )
        transports = [
            row
            for row in operations["validator_failures"]
            if row["failure_kind"] == "transport"
        ]
        self.assertEqual(len(transports), 2)
        for row in transports:
            self.assertEqual(row["classification"], "transport")
            self.assertEqual(row["failures"], failures)

    def test_usage_failures_recovery_and_all_unfinished_states(self):
        run = self.run_fixture(include_development=False, swap_pairs=())
        run.attempt(
            "writers",
            "h-clean-r1-A",
            status="failed",
            kind="transport",
            failures=["Request timed out"],
            observed=False,
        )
        run.writer("h-clean-r1-A", number=2)
        for number in (1, 2):
            run.attempt(
                "writers",
                "h-clean-r1-B",
                number,
                status="failed",
                kind="transport",
                failures=["Transport error"],
            )
        marker = self.root / "writers/h-clean-r1-C/attempt-1.started.json"
        marker.parent.mkdir(parents=True)
        run.write_json(marker, {})
        run.attempt(
            "judges",
            "h-clean-r2-AB-primary",
            status="failed",
            kind="schema_or_evidence",
            failures=["Judge schema or quote evidence validation failed"],
        )
        run.attempt(
            "judges",
            "h-clean-r2-AB-primary",
            2,
            status="failed",
            kind="schema_or_evidence",
            failures=["Quote evidence invalid"],
        )
        run.attempt(
            "judges",
            "h-clean-r3-AB-primary",
            status="failed",
            kind="schema_or_evidence",
            failures=["Invalid JSON schema"],
        )
        run.attempt(
            "judges",
            "h-clean-r3-AB-primary",
            2,
            status="failed",
            kind="semantic",
            failures=["Synthetic unfavorable judgment"],
        )
        report = analysis.analyze(self.root)
        operations = report["operations"]
        usage = operations["usage"]["all"]["writers"]["all_attempts"]
        self.assertEqual(usage["attempts"], 5)
        self.assertEqual(
            set(usage["tokens"]),
            {"input", "output", "reasoning", "cache_read", "cache_write"},
        )
        for n, token in enumerate(full.TOKENS):
            self.assertEqual(
                usage["tokens"][token],
                {"sum": 3 * (n + 1) * 10, "known_attempts": 3, "unknown_attempts": 2},
            )
        self.assertEqual(
            usage["reported_cost"],
            {"sum": 0.375, "known_attempts": 3, "unknown_attempts": 2},
        )
        reliability = operations["reliability"]["all"]["writers"]
        self.assertEqual(reliability["first_attempt_validity"], analysis.fraction(0, 3))
        self.assertEqual(reliability["retry_recovery"], analysis.fraction(1, 3))
        self.assertEqual(reliability["valid_coverage"], analysis.fraction(1, 18))
        self.assertEqual(
            operations["validator_failure_counts"],
            {
                "transport": 3,
                "interrupted": 1,
                "schema_or_evidence": 1,
                "evidence": 1,
                "schema": 1,
            },
        )
        self.assertEqual(len(operations["non_validator_failures"]), 1)
        self.assertEqual(
            {job["status"] for job in operations["unselected_jobs"]},
            {"blocked", "pending", "incomplete", "failed"},
        )
        self.assertGreater(usage["failed_check_count"]["sum"], 0)
        self.assertEqual(
            operations["usage"]["all"]["writers"]["selected_first_valid"]["valid"], 1
        )

    def test_clean_control_literal_vs_final_newline_word_counts(self):
        run = self.run_fixture()
        for ident, job in run.writers.items():
            draft = run.cases[job["case"]]["draft"]
            suffix = {"A": "", "B": "\n", "C": " \n"}[job["arm"]]
            run.writer(ident, draft + suffix)
        report = analysis.analyze(self.root)
        arms = report["word_counts"]["by_split"]["holdout"]
        for arm, literal, final_lf, only in (
            ("A", 3, 3, 0),
            ("B", 0, 3, 3),
            ("C", 0, 0, 0),
        ):
            clean = arms[arm]["by_category"]["clean-controls"]
            self.assertEqual(clean["unchanged_literal"], analysis.fraction(literal, 3))
            self.assertEqual(
                clean["unchanged_ignoring_one_final_lf"], analysis.fraction(final_lf, 3)
            )
            self.assertEqual(clean["final_lf_only_change"], analysis.fraction(only, 3))
            self.assertEqual(clean["equal_case_mean_word_ratio"], 1)
            self.assertEqual(clean["equal_case_mean_words"], 4)

    def test_selected_artifact_integrity_and_exact_native_paths(self):
        run = self.run_fixture(include_development=False, swap_pairs=())
        run.populate()
        index = full.build_index(self.root, run.frozen)
        for role, ident, name in (
            ("writers", "h-clean-r1-B", "output.md"),
            ("judges", "h-clean-r1-BC-primary", "judgment.json"),
            ("judges", "h-clean-r1-BC-primary", "result.json"),
            ("judges", "h-clean-r1-BC-primary", "mapping.json"),
        ):
            with self.subTest(artifact=name):
                job = (run.writers if role == "writers" else run.judges)[ident]
                entry = index["jobs"][role][ident]
                entry["attempts"][0]["folder"] = "wrong-cache-folder"
                path = analysis.selected_artifact(self.root, role, job, entry, name)
                original = path.read_bytes()
                path.write_bytes(original + b" ")
                with self.assertRaisesRegex(
                    ValueError, "Selected artifact hash mismatch"
                ):
                    analysis.analyze(self.root)
                path.write_bytes(original)
        outcome_path = self.root / "writers/h-clean-r1-B/attempt-1/outcome.json"
        outcome = full.read_json(outcome_path)
        outcome["metrics"]["output_words"] += 1
        run.write_json(outcome_path, outcome)
        with self.assertRaisesRegex(ValueError, "native result/outcome mismatch"):
            analysis.analyze(self.root)

    def test_cli_regenerates_only_two_reports_deterministically(self):
        run = self.run_fixture()
        run.populate(winners=lambda job: "tie")
        run.write_json(self.root / "jobindex.json", {"stale": "retained"})
        before = {
            path.relative_to(self.root): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                analysis.main(
                    ["--output", str(self.root), "--bootstrap-samples", "10000"]
                ),
                0,
            )
        after = {
            path.relative_to(self.root): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(
            set(after) - set(before), {Path("analysis.json"), Path("analysis.md")}
        )
        self.assertTrue(all(after[path] == content for path, content in before.items()))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(analysis.main(["--output", str(self.root)]), 0)
        self.assertEqual(
            (self.root / "analysis.json").read_bytes(), after[Path("analysis.json")]
        )
        self.assertEqual(
            (self.root / "analysis.md").read_bytes(), after[Path("analysis.md")]
        )
        report = full.read_json(self.root / "analysis.json")
        self.assertEqual(
            report["comparisons"]["holdout"]["BC"]["bootstrap"]["interval"], [0, 0]
        )
        self.assertEqual(report["decision"]["recommendation"], "retain_B")
        self.assertTrue(report["all_jobs_valid"])
        self.assertTrue(report["all_jobs_terminal"])
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(
                analysis.main(["--output", str(self.root), "--bootstrap-samples", "1"]),
                1,
            )
        self.assertEqual(
            (self.root / "analysis.json").read_bytes(), after[Path("analysis.json")]
        )


if __name__ == "__main__":
    unittest.main()
