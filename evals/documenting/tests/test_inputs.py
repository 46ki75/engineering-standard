"""Preservation proxies, real calibration fixtures, and treatment isolation."""

from copy import deepcopy
import json
import re
from unittest.mock import patch

from support import ArtifactTestCase, OfflineTestCase, run


class PreservationTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.cases = {case["family"]: case for case in run.load_cases()}

    def test_actual_drafts_pass_nonempty_preservation_checks(self):
        self.assertEqual(
            set(self.cases),
            {
                "incident-runbook",
                "api-configuration-reference",
                "independently-readable-procedures",
            },
        )
        for case in self.cases.values():
            with self.subTest(case=case["id"]):
                before = deepcopy(case)
                results = run.check_output(case, case["draft"])
                self.assertGreater(len(results), 0)
                self.assertTrue(all(item["passed"] for item in results))
                self.assertEqual(case, before)
                self.assertEqual(
                    {item["id"] for item in case["checks"]},
                    {item["id"] for item in results if "kind" in item},
                )
        self.assertEqual(self.cases["independently-readable-procedures"]["issues"], [])
        self.assertTrue(self.cases["incident-runbook"]["issues"])
        self.assertTrue(self.cases["api-configuration-reference"]["issues"])

    def test_removing_each_real_literal_is_detected_and_keeps_annotation_context(self):
        for case in self.cases.values():
            for check in case["checks"]:
                if check["kind"] != "contains":
                    continue
                with self.subTest(check=check["id"]):
                    damaged = case["draft"].replace(check["value"], "[omitted]")
                    result = next(
                        item
                        for item in run.check_output(case, damaged)
                        if item["id"] == check["id"]
                    )
                    self.assertEqual(result, dict(check, passed=False))

    def test_regex_proxies_accept_equivalent_units_casing_and_number_format(self):
        samples = {
            "C-QR-TOKEN-MODE": (["mode `0600`"], ["600", "10600", "06000"]),
            "C-QR-PAUSE-DURATION": (
                ["--wait 45s", "45 seconds", "45 second"],
                ["145s", "45ms", "45seconds", "450 seconds"],
            ),
            "C-QR-RECOVERY-RATE": (["--rate 120"], ["1200", "1120"]),
            "C-MICA-REQUEST-HEADER": (
                ["x-mica-timeout-ms", "X-MICA-TIMEOUT-MS"],
                ["X-Mica-Timeout-S"],
            ),
            "C-MICA-INPUT-DEFAULT": (
                ["262144 bytes", "262,144 bytes"],
                ["1262144", "2621440", "262,1440"],
            ),
            "C-MICA-TIMEOUT-STATUS": (["HTTP 504"], ["1504", "5040"]),
        }
        checks = {
            item["id"]: item
            for case in self.cases.values()
            for item in case["checks"]
            if item["kind"] == "regex"
        }
        self.assertEqual(set(checks), set(samples))
        for check_id, (accepted, rejected) in samples.items():
            for text, expected in [(s, True) for s in accepted] + [
                (s, False) for s in rejected
            ]:
                with self.subTest(check=check_id, text=text):
                    result = run.check_output({"checks": [checks[check_id]]}, text)
                    self.assertEqual(result[0]["passed"], expected)

    def test_count_proxies_detect_lost_local_context_but_do_not_prove_placement(self):
        case = self.cases["independently-readable-procedures"]
        for check in case["checks"]:
            if check["kind"] != "count_at_least":
                continue
            with self.subTest(check=check["id"]):
                for count, expected in ((0, False), (1, False), (2, True), (3, True)):
                    # Deliberately co-located: a proxy pass is not a semantic pass
                    # for the two independently usable procedures.
                    text = "Shared prerequisites: " + " ".join([check["value"]] * count)
                    result = run.check_output({"checks": [check]}, text)
                    self.assertEqual(result[0]["passed"], expected)

    def test_forbidden_content_and_unknown_check_kinds(self):
        check = {
            "id": "no-invented-command",
            "kind": "not_contains",
            "value": "restore --force",
        }
        self.assertTrue(
            run.check_output({"checks": [check]}, "Stop and escalate.")[0]["passed"]
        )
        self.assertFalse(
            run.check_output({"checks": [check]}, "Run restore --force.")[0]["passed"]
        )
        check["kind"] = "unimplemented-semantic-check"
        with self.assertRaisesRegex(ValueError, "Unknown check"):
            run.check_output({"checks": [check]}, "anything")

    def test_each_closed_json_fence_is_validated_without_parsing_other_languages(self):
        text = (
            '```json\n{"ok": true}\n```\n'
            "```sh\nnot JSON at all\n```\n"
            '```json\n{"broken": }\n```\n'
            "```json\n[1, 2]\n```\n"
            "```json\n\n```\n"
        )
        self.assertEqual(
            run.check_output({"checks": []}, text),
            [
                {"id": "json-block-0", "passed": True},
                {"id": "json-block-1", "passed": False},
                {"id": "json-block-2", "passed": True},
                {"id": "json-block-3", "passed": False},
            ],
        )

    def test_empty_output_fails_every_real_preservation_proxy(self):
        for case in self.cases.values():
            with self.subTest(case=case["id"]):
                self.assertTrue(
                    all(not item["passed"] for item in run.check_output(case, ""))
                )


class FixtureValidationTests(ArtifactTestCase):
    def setUp(self):
        super().setUp()
        self.cases = run.load_cases()
        self.fixtures = self.output / "cases" / "calibration"
        self.fixtures.mkdir(parents=True)

    def validate_copies(self, cases):
        for old in self.fixtures.glob("*.json"):
            old.unlink()
        for index, case in enumerate(cases):
            (self.fixtures / (str(index) + ".json")).write_text(json.dumps(case))
        with patch.object(run, "HERE", self.output):
            return run.load_cases()

    def test_wrong_case_count_and_duplicate_case_identity_rejected(self):
        for cases in (
            self.cases[:2],
            self.cases + [self.cases[0]],
            [self.cases[0]] * 3,
        ):
            with self.subTest(ids=[case["id"] for case in cases]):
                with self.assertRaisesRegex(ValueError, "three distinct cases"):
                    self.validate_copies(cases)

    def test_blank_or_nonstring_source_fields_rejected(self):
        for field in ("id", "family", "task", "source_facts", "draft"):
            for value in (" \n\t", None, 123):
                with self.subTest(field=field, value=value):
                    cases = deepcopy(self.cases)
                    cases[0][field] = value
                    with self.assertRaisesRegex(ValueError, "Missing case field"):
                        self.validate_copies(cases)

    def test_duplicate_annotation_ids_rejected_in_each_namespace(self):
        for field in ("requirements", "issues", "checks"):
            with self.subTest(field=field):
                cases = deepcopy(self.cases)
                case = next(c for c in cases if c[field])
                case[field].append(deepcopy(case[field][0]))
                with self.assertRaisesRegex(ValueError, "Duplicate annotation IDs"):
                    self.validate_copies(cases)

    def test_unknown_requirement_reference_rejected(self):
        cases = deepcopy(self.cases)
        cases[0]["checks"][0]["requirement"] = "R-NOT-SUPPLIED"
        with self.assertRaisesRegex(ValueError, "unknown requirement"):
            self.validate_copies(cases)

    def test_original_draft_must_pass_proxies_before_any_arm_runs(self):
        cases = deepcopy(self.cases)
        cases[0]["draft"] = (
            "A plausible-looking draft with all protected facts missing."
        )
        with self.assertRaisesRegex(ValueError, "Original draft fails"):
            self.validate_copies(cases)


class PromptIsolationTests(ArtifactTestCase):
    def test_real_arms_differ_only_by_assigned_documentation_guidance(self):
        inputs = run.load_inputs()
        a, b, c = (inputs["systems"][arm] for arm in ("A", "B", "C"))
        common = (run.HERE / "prompts" / "writer.md").read_text()
        skill = run.SKILL.read_text()
        rule = next(
            line for line in skill.splitlines() if line.startswith(run.RULE_PREFIX)
        )
        self.assertNotIn(rule, a)
        self.assertEqual(b, common + "\n" + skill)
        # The rule need not be last; filtering it must preserve surrounding order.
        self.assertEqual(a, b.replace(rule + "\n", "", 1))
        self.assertEqual(b.count(rule), 1)
        self.assertTrue(c.startswith(b))
        self.assertEqual(c.count(rule), 1)
        for system in (a, b, c):
            self.assertTrue(system.startswith(common))
            self.assertEqual(system.count(common), 1)
            for line in skill.splitlines():
                if line and line != rule:
                    self.assertIn(line, system)

        reference = run.REFERENCE.read_text()
        # Assert the actual instructions/examples, rather than rebuilding the
        # runner's heading-split algorithm as an expected value.
        guidance = [
            line
            for line in reference.splitlines()
            if re.match(r"(?:[1-6]\. |\- \*\*)", line)
        ]
        self.assertEqual(len(guidance), 10)
        for line in guidance:
            self.assertIn(line, c)
            self.assertNotIn(line, a)
            self.assertNotIn(line, b)
        for excluded in (
            reference.splitlines()[0],
            reference.splitlines()[2],
            "## Sources",
            *re.findall(r"https://[^)\s]+", reference),
        ):
            for system in (a, b, c):
                self.assertNotIn(excluded, system)

    def test_writers_receive_facts_and_draft_without_scoring_annotations(self):
        for case in run.load_cases():
            with self.subTest(case=case["id"]):
                prompt = run.writer_prompt(case)
                for field in ("task", "source_facts", "draft"):
                    self.assertIn(case[field], prompt)
                for item in case["requirements"] + case["issues"] + case["checks"]:
                    self.assertNotIn(item["id"], prompt)

    def test_missing_or_duplicated_treatment_rule_aborts_assembly(self):
        path = self.output / "SKILL.md"
        rule = run.RULE_PREFIX + " synthetic test rule."
        for content in ("## Guidelines\n", rule + "\n" + rule + "\n"):
            with self.subTest(content=content):
                path.write_text(content)
                with patch.object(run, "SKILL", path):
                    with self.assertRaisesRegex(
                        ValueError, "Expected one documentation rule"
                    ):
                        run.load_inputs()
