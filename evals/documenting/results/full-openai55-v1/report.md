# Documentation-review evaluation: final report

## Decision

**Retain the existing short rule; do not make the longer reference mandatory.** The longer instruction did not meet the predeclared threshold for adoption. Keep its procedure as an evaluated candidate, not as a demonstrated improvement.

This is a decision about adding instruction complexity. The experiment also **does not establish that the short rule improves quality over the original guidelines**: that secondary comparison mostly tied and sometimes favored the original guidelines for editing restraint.

## Design and completion

The study used 36 synthetic documents in six categories: duplication, organization, consistency, necessary repetition, technical meaning, and clean controls. There were 12 development documents and 24 held-out documents, with separate template groups. A separate review checked the sources, drafts, 584 atomic requirements, 48 known issues, and 223 preservation proxies before freezing the suite.

| Arm | Instructions |
| --- | --- |
| A | Original engineering guidelines without the documentation-review rule |
| B | A plus the current short documentation-review rule |
| C | B plus the candidate reference's review procedure and examples |

Every document received three independent revisions per arm: **324 completed revisions** from `openai/gpt-6-astra`, with `high` reasoning. Final judging used `openai/gpt-5.5`, also with `high` reasoning, in fresh blinded sessions. It assessed A/B and B/C pairs plus 54 prespecified order swaps.

**269 of 270 final judging jobs produced valid assessments.** One B/C job remained invalid after its two permitted attempts: the judge spliced nonadjacent table passages into purportedly exact quotations. That job remains excluded rather than repaired into a favorable vote. All writer outputs are retained.

The candidate, inputs, schemas, schedule, and decision criteria were frozen before full-suite inference. The final manifest is `b23dcb8a583f222bd98f20c97574c2ca47c0a955e8897d7a3d7d92fccd341cba`.

## Held-out results

Only primary judgments appear below; order swaps are excluded from effect estimates.

| Comparison | First arm wins | Second arm wins | Ties | Invalid/missing |
| --- | ---: | ---: | ---: | ---: |
| A versus B | 9 | 0 | 63 | 0 |
| B versus C | 1 | 4 | 66 | 1 |

For the primary C-versus-B comparison, the equal-document net preference was **+0.0417**, with a **95% stratified-bootstrap interval of [0.0000, 0.0972]**. The predeclared adoption criterion required its lower bound to exceed zero. It did not.

Coverage passed: **71/72** primary B/C judgments were valid, and each of the 24 held-out documents had at least two valid repetitions. Paired requirement-failure fractions were zero for both arms according to the judge, and no critical regression was flagged. These other gates passing does not override the primary criterion.

The secondary A/B net preference for B was **−0.1250**, with interval **[−0.2083, −0.0556]**. This is a secondary, non-multiplicity-adjusted result. Review of the decisive cases indicates that it mainly reflects preferences for less rewriting, not correction of additional factual errors.

Development results were similarly close: C versus B had one C win, three B wins, and 32 ties. No instruction was tuned to these outputs before held-out execution.

### Other observations

- The final judge passed all scored atomic requirements. These repeated model assessments are not proof that every generated sentence is correct.
- Held-out known-issue resolution was scored as complete across the compared arms. The original-guideline baseline was already strong on these tasks.
- On held-out documents, mean output-to-input word ratios were **A: 0.973, B: 0.880, C: 0.893**. The extra review instructions produced shorter documents, but shorter output was not the quality metric.
- In the four held-out clean-control cases, all arms changed the drafts in all three repetitions. C's explicit permission to leave clean text unchanged was not sufficient to reliably prevent rewriting.
- Order checks agreed in **49/54** pairs. Five changed between a tie and a preference; none reversed from one decisive winner to the other.

## Secondary substantive review

Two label-aware AI-assisted reviews checked all **14 decisive held-out comparisons**, the invalid comparison, all regression flags, and six deterministically selected B/C ties—one per category. These were not independent human reviews and did not replace the original votes.

Findings:

- Thirteen of the 14 decisive preferences primarily concerned presentation, wording, or restraint. Both candidates generally preserved the required facts and fixed the known issues.
- One short-rule output introduced a localized “validates the source” imprecision, while correctly describing request validation elsewhere. This supports a minor qualification, not a major operational error.
- An alleged cancellation-behavior regression was not substantiated: the candidate retained the HTTP status and the statement that produced results were not removed.
- The six tied comparisons preserved the checked meanings, conditions, boundaries, and necessary local context. A “reusable crate” source detail was absent in both the original and revised documents; that was a preexisting gap, not revision-induced loss.
- A scoped-edit case differed in its terminal newline outside the editable section. Automated passes overlooked that byte-exact requirement; no words or technical meaning were lost.

These checks support a restrained interpretation: the experiment mainly measured marginal editorial preferences among already-capable revisions. It does not validate all 324 documents exhaustively. Evidence and reviewed job IDs are recorded in [adjudication.json](adjudication.json).

## Judge recovery and reliability

The original cross-family judge, Copilot's Claude Sonnet 5, became unavailable with **HTTP 402** responses marked non-retryable. That incomplete study remains in `../full-v1/`. Its judgments were not selectively mixed into the final comparison.

A replacement-model control test rejected GPT-5.6 Luna because only 6/12 responses met the contract. GPT-5.5 passed **12/12 omission controls**, detected every deliberately omitted fact, and passed all 360 untouched-atom checks. It was selected on control reliability, not on which instruction variant it favored. All 270 judgments were then rerun consistently against the exact saved writer outputs. See [RECOVERY.md](../../RECOVERY.md).

The final study contains **325 retained writer attempts and 280 judge attempts**. The latter include six attempts interrupted by the shell's wall-clock limit, subsequently resumed within the frozen two-attempt bound. One original writer attempt also lacked a completed response. All failed/interrupted attempts remain visible.

The [integrity audit](audit.json) found **zero known mismatches and zero duplicate observed sessions**. It verified 324 writer session exports and 274 native judge session records, including all selected results. Seven failed/interrupted attempts lacked session evidence; overall all-attempt integrity is therefore explicitly **unknown**, not a blanket pass. Their usage is also unknown.

Known token telemetry for the reused writers plus final judging totals **3,529,239 tokens** across input, output, reasoning, and cache buckets. This excludes unknown interrupted usage, controls, and the unsuccessful earlier judging pass. Writer reuse must not be counted as a second set of generation calls. Dollar estimates were not used as a stopping criterion under the user's fixed-rate plan.

## Limitations

- Both final models are from the same provider, so correlated errors remain possible. Omission controls establish sensitivity on specific examples, not universal judge reliability.
- Documents were synthetic and AI-authored. Replacement fixture authors were isolated from candidate prompts and results; an earlier exposed fixture batch was excluded before inference.
- The task was finalizing supplied drafts with source facts. It did not test initial drafting, normal coding-agent tools, reference discovery, or the claim that irreversible token generation causes redundancy.
- The original guidelines already included conciseness and verification instructions, and the common task explicitly asked for a finalized document. The resulting strong baseline limits conclusions about whether review is useful in less guided workflows.
- The statistical unit was the document. Repetitions and swaps were not counted as independent samples. The primary interval applies to these documents, models, and rubric; it is not a universal performance guarantee.

## Deliverables and verification

- [Detailed computed analysis](analysis.md); full machine-readable results are in the local `analysis.json` artifact. See the [artifact-storage policy](../README.md).
- [Frozen full-suite protocol](../../FULL-EVALUATION.md), including selection criteria.
- Native inputs, outputs, schemas, judgments, attempt histories, and provenance in this run directory.
- **182 offline tests passed** across the runner, transport, controls, analysis, audit, and recovery components.
- No global OpenCode configuration was changed, and no containers were needed.

Recompute the analysis without model calls:

```sh
python3 -B evals/documenting/full_analysis.py \
  --output evals/documenting/results/full-openai55-v1 \
  --bootstrap-samples 10000
```

The practical outcome is to keep the standard compact. Treat “avoid unnecessary rewriting” as an important consideration for future instruction experiments rather than claiming that a longer review checklist has already earned its place.
