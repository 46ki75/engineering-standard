"""Judge contract failures that can change pairwise conclusions."""

from copy import deepcopy

from support import OfflineTestCase, judgment, run


class JudgmentTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.case = next(case for case in run.load_cases() if len(case["issues"]) > 1)

    def test_all_real_ids_accepted_in_any_order_including_clean_case(self):
        for case in run.load_cases():
            with self.subTest(case=case["id"]):
                value = judgment(case)
                for kind in ("requirements", "issues"):
                    value["candidates"]["right"][kind].reverse()
                before = deepcopy(value)
                run.validate_judgment(value, case)
                self.assertEqual(value, before)

    def test_every_supplied_id_required_exactly_once_on_each_side(self):
        for side in ("left", "right"):
            for kind in ("requirements", "issues"):
                for defect in ("missing", "duplicate", "invented", "replacement"):
                    with self.subTest(side=side, kind=kind, defect=defect):
                        value = judgment(self.case)
                        items = value["candidates"][side][kind]
                        if defect == "missing":
                            items.pop()
                        elif defect == "duplicate":
                            items.append(deepcopy(items[0]))
                        elif defect == "invented":
                            items.append(dict(items[0], id="NOT-SUPPLIED"))
                        else:
                            items[-1]["id"] = "NOT-SUPPLIED"
                        with self.assertRaisesRegex(ValueError, "annotation IDs"):
                            run.validate_judgment(value, self.case)

    def test_clean_case_cannot_be_given_an_invented_issue(self):
        case = next(case for case in run.load_cases() if not case["issues"])
        for side in ("left", "right"):
            with self.subTest(side=side):
                value = judgment(case)
                value["candidates"][side]["issues"] = [
                    {
                        "id": "I-INVENTED",
                        "status": "resolved",
                        "evidence": "Changed wording.",
                    }
                ]
                with self.assertRaisesRegex(ValueError, "annotation IDs"):
                    run.validate_judgment(value, case)

    def test_valid_statuses_preserve_uncertainty_without_forcing_a_winner(self):
        for kind, statuses in (
            ("requirements", ("pass", "fail", "uncertain")),
            ("issues", ("resolved", "partial", "unresolved", "uncertain")),
        ):
            for status in statuses:
                for winner in ("left", "right", "tie", "uncertain"):
                    with self.subTest(kind=kind, status=status, winner=winner):
                        value = judgment(self.case)
                        value["candidates"]["left"][kind][0]["status"] = status
                        value["winner"] = winner
                        run.validate_judgment(value, self.case)
                        self.assertEqual(value["winner"], winner)

    def test_invalid_and_cross_namespace_statuses_rejected(self):
        for side in ("left", "right"):
            for kind, statuses in (
                ("requirements", ("resolved", "PASS", "pass|fail|uncertain", "", None)),
                ("issues", ("pass", "fixed", "resolved|partial", "", None)),
            ):
                for status in statuses:
                    with self.subTest(side=side, kind=kind, status=status):
                        value = judgment(self.case)
                        value["candidates"][side][kind][0]["status"] = status
                        with self.assertRaisesRegex(ValueError, "Invalid assessment"):
                            run.validate_judgment(value, self.case)

    def test_assessments_need_nonblank_text_evidence_on_both_sides(self):
        for side in ("left", "right"):
            for kind in ("requirements", "issues"):
                for evidence in ("", " \n\t", None, 0, ["quote"]):
                    with self.subTest(side=side, kind=kind, evidence=evidence):
                        value = judgment(self.case)
                        value["candidates"][side][kind][0]["evidence"] = evidence
                        with self.assertRaisesRegex(
                            ValueError, "Missing assessment evidence"
                        ):
                            run.validate_judgment(value, self.case)

    def test_scores_accept_endpoints_and_reject_out_of_range_or_noninteger_values(self):
        for side in ("left", "right"):
            for field, valid, invalid in (
                ("organization", (1, 5), (0, 6, True, False, 3.0, "3", None)),
                ("unnecessary_change", (0, 3), (-1, 4, True, False, 1.0, "1", None)),
            ):
                for score in valid + invalid:
                    with self.subTest(side=side, field=field, score=repr(score)):
                        value = judgment(self.case)
                        value["candidates"][side][field] = score
                        if type(score) is int and score in valid:
                            run.validate_judgment(value, self.case)
                        else:
                            with self.assertRaisesRegex(
                                ValueError, "Invalid judge score"
                            ):
                                run.validate_judgment(value, self.case)

    def test_missing_and_extra_fields_rejected_at_every_object_level(self):
        for location in ("root", "candidates", "candidate", "assessment", "regression"):
            for defect in ("missing", "extra"):
                with self.subTest(location=location, defect=defect):
                    value = judgment(self.case)
                    candidate = value["candidates"]["right"]
                    candidate["regressions"] = [
                        {
                            "severity": "major",
                            "description": "Guard lost.",
                            "evidence": "Original requires the guard; right omits it.",
                        }
                    ]
                    target, required = {
                        "root": (value, "reason"),
                        "candidates": (value["candidates"], "right"),
                        "candidate": (candidate, "organization"),
                        "assessment": (candidate["requirements"][0], "evidence"),
                        "regression": (candidate["regressions"][0], "evidence"),
                    }[location]
                    if defect == "missing":
                        del target[required]
                    else:
                        target["unrequested_field"] = "extra"
                    with self.assertRaises(ValueError):
                        run.validate_judgment(value, self.case)

    def test_invalid_winner_or_nontext_reason_rejected(self):
        for field, invalid in (
            ("winner", ("A", "B", "both", "left|right|tie|uncertain", "", None)),
            ("reason", (None, 1, ["explanation"])),
        ):
            for replacement in invalid:
                with self.subTest(field=field, replacement=replacement):
                    value = judgment(self.case)
                    value[field] = replacement
                    with self.assertRaisesRegex(ValueError, "Invalid winner or reason"):
                        run.validate_judgment(value, self.case)

    def test_regression_severity_is_not_an_unrestricted_label(self):
        for severity in ("critical", "major", "minor", "severe", "", None):
            with self.subTest(severity=severity):
                value = judgment(self.case)
                value["candidates"]["left"]["regressions"] = [
                    {
                        "severity": severity,
                        "description": "Guard removed.",
                        "evidence": "Original had a guard; candidate does not.",
                    }
                ]
                if severity in ("critical", "major", "minor"):
                    run.validate_judgment(value, self.case)
                else:
                    with self.assertRaisesRegex(
                        ValueError, "Invalid regression severity"
                    ):
                        run.validate_judgment(value, self.case)

    def test_regression_requires_text_description_and_evidence(self):
        for field in ("description", "evidence"):
            for invalid in (None, " \n", [], 0):
                with self.subTest(field=field, invalid=invalid):
                    value = judgment(self.case)
                    regression: dict = {
                        "severity": "critical",
                        "description": "Guard removed.",
                        "evidence": "Original has a guard; candidate does not.",
                    }
                    regression[field] = invalid
                    value["candidates"]["right"]["regressions"] = [regression]
                    with self.assertRaises(ValueError):
                        run.validate_judgment(value, self.case)

    def test_empty_issues_and_regressions_must_be_arrays(self):
        case = next(case for case in run.load_cases() if not case["issues"])
        for field in ("issues", "regressions"):
            with self.subTest(field=field):
                value = judgment(case)
                value["candidates"]["right"][field] = {}
                with self.assertRaises(ValueError):
                    run.validate_judgment(value, case)
