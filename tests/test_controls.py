"""Offline omission-control construction, transport boundaries, and denominators."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evals.documenting import controls


class ControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = controls.build_manifest()
        cls.by_id = {c["id"]: c for c in cls.manifest["controls"]}

    def gold(self, job):
        control = self.by_id[job["control"]]
        candidates = {}
        for side, letter in zip(("left", "right"), job["order"]):
            role = "preserved" if letter == "P" else "omitted"
            candidates[side] = {
                "requirements": {
                    atom: {
                        "status": status,
                        "quote": control["witnesses"][atom] if status == "pass" else "",
                        "explanation": "Required fact is communicated."
                        if status == "pass"
                        else "Required fact is absent.",
                    }
                    for atom, status in control["expected"][role].items()
                },
                "issues": {},
                "regressions": [],
                "organization": 5,
                "unnecessary_change": 0,
            }
        return {
            "candidates": candidates,
            "winner": "left" if job["order"] == "PN" else "right",
            "reason": "One candidate retains the required fact.",
        }

    def test_independent_mutations_complexity_provenance_and_blinding(self):
        self.assertEqual(set(self.by_id), {"M1", "M2", "Q1", "Q2", "F1", "F2"})
        self.assertEqual(len(self.manifest["jobs"]), 12)
        for control in self.by_id.values():
            self.assertEqual(len(control["case"]["requirements"]), 16)
            self.assertEqual(control["case"]["issues"], [])
            negative = control["case"]["draft"]
            for deletion in control["deletions"]:
                self.assertEqual(negative.count(deletion), 1)
                negative = negative.replace(deletion, "", 1)
            self.assertEqual(negative, control["omitted"])
            self.assertEqual(
                sum(s == "fail" for s in control["expected"]["omitted"].values()), 1
            )
            first, second = (controls.inputs(control, order) for order in ("PN", "NP"))
            self.assertEqual(first["candidates"]["left"], second["candidates"]["right"])
            self.assertEqual(first["candidates"]["right"], second["candidates"]["left"])
            self.assertEqual(
                set(first),
                {
                    "task",
                    "source_facts",
                    "draft",
                    "requirements",
                    "issues",
                    "candidates",
                },
            )
            self.assertNotIn("expected", controls.encoded(control["schema"]))
            self.assertNotIn("preserved", controls.encoded(control["schema"]))
        self.assertIn(controls.MEANINGS, self.by_id["M1"]["case"]["source_facts"])
        self.assertIn("provenance", self.by_id["M1"]["case"]["source_facts"])
        self.assertEqual(len(self.by_id["Q2"]["deletions"]), 2)
        for base in "MQF":
            self.assertEqual(
                self.by_id[base + "1"]["case"], self.by_id[base + "2"]["case"]
            )

    def test_semantic_mistake_stays_valid_but_bad_evidence_does_not(self):
        job = {"id": "M1-PN", "control": "M1", "order": "PN"}
        control, value = self.by_id["M1"], self.gold(job)
        entry = value["candidates"]["right"]["requirements"][control["target"]]
        entry.update(status="pass", quote="template_id")
        self.assertEqual(controls.assess(job, control, value)["status"], "valid")
        for quote in ("", controls.TEMPLATE):
            entry["quote"] = quote
            self.assertEqual(
                controls.assess(job, control, value)["status"], "evidence_error"
            )
            self.assertEqual(entry["quote"], quote)
        del value["winner"]
        self.assertEqual(controls.assess(job, control, value)["status"], "schema_error")

    def test_swap_normalization_missing_failures_and_untouched_metrics(self):
        rows = [
            controls.assess(j, self.by_id[j["control"]], self.gold(j))
            for j in self.manifest["jobs"]
        ]
        report = controls.summarize(self.manifest, rows)
        self.assertEqual(report["metrics"]["swap_winner_agrees"], controls.rate(6, 6))
        self.assertEqual(report["metrics"]["end_to_end_success"], controls.rate(12, 12))
        self.assertEqual(report["metrics"]["untouched_pass"], controls.rate(360, 360))
        rows = {r["trial_id"]: r for r in rows}
        rows["M1-PN"]["winner"] = "tie"
        target = self.by_id["M1"]["target"]
        rows["M1-PN"]["requirements"]["omitted"][target] = "pass"
        untouched = next(
            a for a in rows["M1-PN"]["requirements"]["preserved"] if a != target
        )
        rows["M1-PN"]["requirements"]["preserved"][untouched] = "fail"
        for ident, status in (("Q1-PN", "schema_error"), ("F1-NP", "missing")):
            job = next(j for j in self.manifest["jobs"] if j["id"] == ident)
            rows[ident] = controls.row(job, status)
        report = controls.summarize(self.manifest, list(rows.values()))
        self.assertEqual(report["metrics"]["response_failure"], controls.rate(1, 11))
        self.assertEqual(report["metrics"]["omission_false_pass"], controls.rate(1, 10))
        self.assertEqual(report["metrics"]["untouched_fail"], controls.rate(1, 300))
        self.assertEqual(
            report["metrics"]["swap_winner_disagrees"], controls.rate(1, 4)
        )
        self.assertEqual(sum(s["winner_agrees"] is None for s in report["swaps"]), 2)

    def test_attempt_artifacts_no_retry_and_offline_modes(self):
        def fake(folder, system, prompt, schema, **settings):
            payload = json.loads(prompt)
            job = next(
                j
                for j in self.manifest["jobs"]
                if controls.inputs(self.by_id[j["control"]], j["order"]) == payload
            )
            self.assertEqual(
                settings,
                {"model": controls.run.JUDGE_MODEL, "variant": "high", "timeout": 600},
            )
            folder.mkdir()
            native = {"status": "completed", "failures": []}
            value = self.gold(job)
            if job["id"] == "M1-PN":
                native = {
                    "status": "failed",
                    "failures": ["Assistant variant mismatch"],
                }
                value = None
            elif job["id"] == "M2-PN":
                target = self.by_id["M2"]["target"]
                value["candidates"]["right"]["requirements"][target]["quote"] = (
                    controls.RECORD
                )
            elif job["id"] == "Q1-PN":
                del value["winner"]
            elif job["id"] == "Q2-PN":
                raise RuntimeError("Simulated interrupted transport")
            controls.save(folder / "result.json", native)
            return native, value

        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(
                controls.structured, "call_structured", side_effect=fake
            ) as transport,
        ):
            output = Path(temporary) / "run"
            controls.execute(output, self.manifest, 3)
            self.assertEqual(transport.call_count, 12)
            with self.assertRaises(FileExistsError):
                controls.execute(output, self.manifest, 3)
            rows = controls.collect(output, self.manifest)
            failed = next(r for r in rows if r["trial_id"] == "M1-PN")
            self.assertEqual(failed["status"], "transport_error")
            self.assertEqual(failed["failures"], ["Assistant variant mismatch"])
            by_id = {r["trial_id"]: r for r in rows}
            self.assertEqual(by_id["M2-PN"]["status"], "evidence_error")
            self.assertEqual(by_id["Q1-PN"]["status"], "schema_error")
            self.assertEqual(by_id["Q2-PN"]["status"], "transport_error")
            invalid = controls.run.read_json(output / "trials/M2-PN/judgment.json")
            target = self.by_id["M2"]["target"]
            self.assertEqual(
                invalid["candidates"]["right"]["requirements"][target]["quote"],
                controls.RECORD,
            )
            native = controls.run.read_json(output / "trials/M2-PN/native/result.json")
            self.assertEqual(native["status"], "completed")
            self.assertTrue((output / "trials/M1-PN/attempt.json").exists())
            self.assertTrue((output / "trials/M1-NP/judgment.json").exists())
            with redirect_stdout(io.StringIO()):
                self.assertEqual(controls.main(["--validate-only"]), 0)
                self.assertEqual(
                    controls.main(["--summarize", "--output", str(output)]), 1
                )
            self.assertEqual(transport.call_count, 12)
            frozen = controls.run.read_json(output / "manifest.json")
            frozen["manifest"]["variant"] = "changed"
            controls.save(output / "manifest.json", frozen)
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                controls.main(["--summarize", "--output", str(output)])

    def test_unstarted_and_incomplete_trials_have_no_votes(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            partial = output / "trials/M1-PN"
            partial.mkdir(parents=True)
            controls.save(partial / "attempt.json", {"attempt": 1})
            report = controls.summarize(
                self.manifest, controls.collect(output, self.manifest)
            )
            self.assertEqual(report["counts"]["missing"], 11)
            self.assertEqual(report["counts"]["transport_error"], 1)
            self.assertEqual(
                report["metrics"]["paired_semantic_success"], controls.rate(0, 0)
            )
            self.assertEqual(
                report["metrics"]["end_to_end_success"], controls.rate(0, 12)
            )
            self.assertEqual(
                report["metrics"]["swap_winner_disagrees"], controls.rate(0, 0)
            )


if __name__ == "__main__":
    unittest.main()
