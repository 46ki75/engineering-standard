"""Offline contract tests; quote provenance does not establish entailment."""

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path


_SPEC = importlib.util.spec_from_file_location(
    "judging_under_test",
    Path(__file__).resolve().parents[1] / "evals" / "documenting" / "judging.py",
)
assert _SPEC is not None and _SPEC.loader is not None
judging = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(judging)


def at(value, path):
    for key in path:
        value = value[key]
    return value


class JudgingTests(unittest.TestCase):
    def setUp(self):
        self.case: dict = {
            "requirements": [{"id": "req-timeout"}, {"id": "req-retry"}],
            "issues": [{"id": "issue-order"}, {"id": "issue-label"}],
        }
        self.texts = {
            "left": "## Left\nTimeout: **30 ms**.\nCafé 🚀\nRetry once.\n",
            "right": "## Right\nTimeout: **30 ms**.\nCafe\u0301 🌍\nRetry once.\n",
        }
        candidate = {
            "requirements": {
                "req-timeout": {
                    "status": "pass",
                    "quote": "Timeout: **30 ms**.",
                    "explanation": "The timeout and unit are stated together.",
                },
                "req-retry": {
                    "status": "pass",
                    "quote": "Retry once.",
                    "explanation": "The retry count is stated.",
                },
            },
            "issues": {
                identifier: {
                    "status": "resolved",
                    "quote": "Timeout: **30 ms**.",
                    "explanation": "The timeout is labeled before the retry rule.",
                }
                for identifier in ("issue-order", "issue-label")
            },
            "regressions": [
                {
                    "severity": "minor",
                    "quote": "Retry once.",
                    "explanation": "The original retry rationale was omitted.",
                }
            ],
            "organization": 5,
            "unnecessary_change": 0,
        }
        self.value = {
            "candidates": {side: deepcopy(candidate) for side in self.texts},
            "winner": "tie",
            "reason": "Both candidates retain the same operational details.",
        }
        self.object_paths = [(), ("candidates",)]
        self.evidence_paths = []
        self.enum_fields: list[tuple[tuple, tuple[str, ...]]] = [
            (("winner",), ("left", "right", "tie", "uncertain"))
        ]
        self.score_fields = []
        for side in self.texts:
            base = ("candidates", side)
            self.object_paths.append(base)
            for field, statuses in (
                ("requirements", ("pass", "fail", "uncertain")),
                ("issues", ("resolved", "partial", "unresolved", "uncertain")),
            ):
                self.object_paths.append(base + (field,))
                for entry in self.case[field]:
                    path = base + (field, entry["id"])
                    self.object_paths.append(path)
                    self.evidence_paths.append(path)
                    self.enum_fields.append((path + ("status",), statuses))
            path = base + ("regressions", 0)
            self.object_paths.append(path)
            self.evidence_paths.append(path)
            self.enum_fields.append(
                (path + ("severity",), ("critical", "major", "minor"))
            )
            self.score_fields.extend(
                [
                    (base + ("organization",), 1, 5),
                    (base + ("unnecessary_change",), 0, 3),
                ]
            )

    def replaced(self, path, replacement):
        value = deepcopy(self.value)
        if not path:
            return replacement
        at(value, path[:-1])[path[-1]] = replacement
        return value

    def validate(self, value):
        return judging.validate(
            value, self.case, self.texts["left"], self.texts["right"]
        )

    def test_schema_is_closed_with_exact_keys_types_enums_and_bounds(self):
        for empty_issues in (False, True):
            with self.subTest(empty_issues=empty_issues):
                case = deepcopy(self.case)
                if empty_issues:
                    case["issues"] = []
                schema = judging.schema_for(case)
                expected = deepcopy(self.value)
                if empty_issues:
                    for candidate in expected["candidates"].values():
                        candidate["issues"] = {}

                def check_objects(node, sample):
                    if isinstance(sample, dict):
                        self.assertEqual(node["type"], "object")
                        self.assertEqual(set(node["properties"]), set(sample))
                        self.assertCountEqual(node["required"], sample.keys())
                        self.assertIs(node["additionalProperties"], False)
                        for key, child in sample.items():
                            check_objects(node["properties"][key], child)
                    elif isinstance(sample, list):
                        self.assertEqual(node["type"], "array")
                        check_objects(node["items"], sample[0])

                def schema_at(path):
                    node = schema
                    for key in path:
                        node = (
                            node["items"]
                            if isinstance(key, int)
                            else node["properties"][key]
                        )
                    return node

                check_objects(schema, expected)
                for path, statuses in self.enum_fields:
                    if empty_issues and "issues" in path:
                        continue
                    self.assertEqual(
                        schema_at(path), {"type": "string", "enum": list(statuses)}
                    )
                for path, lower, upper in self.score_fields:
                    self.assertEqual(
                        schema_at(path),
                        {"type": "integer", "minimum": lower, "maximum": upper},
                    )
                for path in self.evidence_paths:
                    if empty_issues and "issues" in path:
                        continue
                    self.assertEqual(
                        schema_at(path + ("quote",)),
                        {"type": "string", "maxLength": 800},
                    )
                    self.assertEqual(
                        schema_at(path + ("explanation",)),
                        {"type": "string", "minLength": 1, "maxLength": 600},
                    )
                self.assertEqual(
                    schema_at(("reason",)),
                    {"type": "string", "minLength": 1},
                )

    def test_complete_assessments_and_empty_issues_are_valid(self):
        for empty_issues in (False, True):
            for empty_regressions in (False, True):
                with self.subTest(issues=empty_issues, regressions=empty_regressions):
                    case, value = deepcopy(self.case), deepcopy(self.value)
                    if empty_issues:
                        case["issues"] = []
                        for candidate in value["candidates"].values():
                            candidate["issues"] = {}
                    if empty_regressions:
                        for candidate in value["candidates"].values():
                            candidate["regressions"] = []
                    before = deepcopy(value)
                    self.assertIsNone(
                        judging.validate(value, case, *self.texts.values())
                    )
                    self.assertEqual(value, before)

    def test_all_documented_enums_and_integer_scores_are_accepted(self):
        fields = self.enum_fields + [
            (path, range(lower, upper + 1)) for path, lower, upper in self.score_fields
        ]
        for path, choices in fields:
            for choice in choices:
                with self.subTest(path=path, choice=choice):
                    self.assertIsNone(self.validate(self.replaced(path, choice)))

    def test_missing_extra_and_renamed_keys_are_rejected_at_every_object(self):
        for path in self.object_paths:
            original = at(self.value, path)
            variants = [("extra", dict(original, invented={}))]
            for key in original:
                missing = dict(original)
                removed = missing.pop(key)
                variants.append(("missing " + key, missing))
                variants.append(("renamed " + key, dict(missing, invented=removed)))
            for mutation, replacement in variants:
                with self.subTest(path=path, mutation=mutation):
                    with self.assertRaisesRegex(
                        ValueError, "Unexpected assessment keys"
                    ):
                        self.validate(self.replaced(path, replacement))

    def test_object_and_regression_array_types_are_validated(self):
        for path in self.object_paths:
            for invalid in (
                None,
                False,
                0,
                1.5,
                "object",
                [],
                [self.value],
                (),
                json.dumps(at(self.value, path)),
            ):
                with self.subTest(path=path, invalid=invalid):
                    with self.assertRaisesRegex(
                        ValueError, "Unexpected assessment keys"
                    ):
                        self.validate(self.replaced(path, invalid))
        for side in self.texts:
            path = ("candidates", side, "regressions")
            for invalid in (None, False, 0, 1.5, "array", {}, ()):
                with self.subTest(path=path, invalid=invalid):
                    with self.assertRaisesRegex(
                        ValueError, "Regressions must be an array"
                    ):
                        self.validate(self.replaced(path, invalid))

    def test_invalid_enums_raise_value_error_even_for_unhashable_values(self):
        for path, allowed in self.enum_fields:
            invalid_values = (
                "invented",
                "",
                allowed[0].upper(),
                None,
                True,
                0,
                1.5,
                [],
                [allowed[0]],
                {},
                {allowed[0]: True},
                "resolved" if "pass" in allowed else "pass",
            )
            for invalid in invalid_values:
                with self.subTest(path=path, invalid=invalid):
                    with self.assertRaisesRegex(ValueError, "Invalid"):
                        self.validate(self.replaced(path, invalid))

    def test_scores_reject_out_of_range_values_floats_and_booleans(self):
        for path, lower, upper in self.score_fields:
            for invalid in (
                lower - 1,
                upper + 1,
                float(lower),
                float(upper),
                2.5,
                True,
                False,
                str(lower),
                None,
                [],
                {},
                (),
            ):
                with self.subTest(path=path, invalid=invalid):
                    with self.assertRaisesRegex(ValueError, "Invalid assessment score"):
                        self.validate(self.replaced(path, invalid))

    def test_long_reasons_are_accepted_but_must_be_nonblank_strings(self):
        for reason in ("x", "é" * 1200, "é" * 1201, "Résumé:\n候補の比較 🚀\n" * 1000):
            with self.subTest(length=len(reason)):
                value = self.replaced(("reason",), reason)
                self.assertIsNone(self.validate(value))
                self.assertEqual(value["reason"], reason)
        for invalid in ("", " \n\t", None, True, 1, 1.5, [], {}, ()):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(
                    ValueError, "Invalid comparison explanation"
                ):
                    self.validate(self.replaced(("reason",), invalid))

    def test_explanations_require_nonblank_strings_within_length_limits(self):
        fields = [
            (path + ("explanation",), 600, "Invalid evidence explanation")
            for path in self.evidence_paths
        ]
        for path, limit, message in fields:
            for valid in ("x", "é" * limit):
                with self.subTest(path=path, valid_length=len(valid)):
                    self.assertIsNone(self.validate(self.replaced(path, valid)))
            for invalid in (
                "",
                " \n\t",
                "x" * (limit + 1),
                None,
                True,
                1,
                1.5,
                [],
                {},
                (),
            ):
                with self.subTest(path=path, invalid=invalid):
                    with self.assertRaisesRegex(ValueError, message):
                        self.validate(self.replaced(path, invalid))

    def test_quotes_validate_string_type_and_character_limit(self):
        for side in self.texts:
            self.texts[side] += "é" * 801
        for entry in self.evidence_paths:
            path = entry + ("quote",)
            with self.subTest(path=path, boundary=800):
                self.assertIsNone(self.validate(self.replaced(path, "é" * 800)))
            for invalid in ("é" * 801, None, True, 1, 1.5, [], {}, ()):
                with self.subTest(path=path, invalid=invalid):
                    with self.assertRaisesRegex(ValueError, "Invalid evidence quote"):
                        self.validate(self.replaced(path, invalid))

    def test_passing_requirements_need_nonblank_candidate_quotes(self):
        for entry in self.evidence_paths:
            if "requirements" not in entry:
                continue
            for quote in ("", " ", "\n", "\t\n "):
                with self.subTest(path=entry, quote=quote):
                    with self.assertRaisesRegex(
                        ValueError, "Passing requirement lacks candidate evidence"
                    ):
                        self.validate(self.replaced(entry + ("quote",), quote))

    def test_omission_failures_can_have_empty_quotes(self):
        value = deepcopy(self.value)
        for path in self.evidence_paths:
            entry = at(value, path)
            entry["quote"] = ""
            entry["explanation"] = "The original operational details are missing."
            if "requirements" in path:
                entry["status"] = "fail"
            elif "issues" in path:
                entry["status"] = "unresolved"
        self.assertIsNone(
            judging.validate(value, self.case, "## Overview\n", "## Summary\n")
        )

    def test_exact_multiline_markdown_and_unicode_quotes_are_preserved(self):
        value = deepcopy(self.value)
        for path in self.evidence_paths:
            quote = self.texts[path[1]].split("\n", 1)[1]
            at(value, path)["quote"] = quote
            at(value, path)["explanation"] = "Résumé:\n候補の引用 🚀"
        before = deepcopy(value)
        self.assertIsNone(self.validate(value))
        self.assertEqual(value, before)

    def test_nonexact_and_opposite_candidate_quotes_are_rejected(self):
        for entry in self.evidence_paths:
            side = entry[1]
            other = "right" if side == "left" else "left"
            wrong_unicode = "Cafe\u0301 🚀" if side == "left" else "Café 🌍"
            for quote in (
                self.texts[other],
                "Timeout: 30 ms.",
                "Timeout: **30 ms**. ... Retry once.",
                self.texts[side].replace("\n", " "),
                wrong_unicode,
            ):
                with self.subTest(path=entry, quote=quote):
                    with self.assertRaisesRegex(
                        ValueError, "Evidence quote is not an exact candidate substring"
                    ):
                        self.validate(self.replaced(entry + ("quote",), quote))

    def test_source_fact_quotes_cannot_support_a_passing_requirement(self):
        source_fact = "The timeout is thirty milliseconds."
        self.case["source_facts"] = source_fact
        for entry in self.evidence_paths:
            if "requirements" not in entry:
                continue
            with self.subTest(path=entry):
                self.assertNotIn(source_fact, self.texts[entry[1]])
                with self.assertRaisesRegex(
                    ValueError, "Evidence quote is not an exact candidate substring"
                ):
                    self.validate(self.replaced(entry + ("quote",), source_fact))

    def test_matching_a_quote_does_not_establish_semantic_entailment(self):
        self.case["requirements"][0]["text"] = "State the timeout duration and unit."
        for side in self.texts:
            with self.subTest(side=side):
                path = ("candidates", side, "requirements", "req-timeout", "quote")
                heading = self.texts[side].split("\n", 1)[0]
                # An unrelated heading passes provenance checks, not a semantic review.
                self.assertIsNone(self.validate(self.replaced(path, heading)))


if __name__ == "__main__":
    unittest.main()
