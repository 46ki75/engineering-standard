# Documentation review — evaluation candidate

This procedure is a candidate for evaluation; improvement over the short documentation rule has not been established.

## Review and revise

1. **Read the whole document against its task.** Establish the audience, purpose, requested scope, and supplied source facts. Follow the reader's path through headings, prerequisites, explanations, examples, and next steps before editing individual sentences.
2. **Identify genuine issues.** For each proposed change, locate the problem and identify its effect on correctness or task usability. Look for misplaced prerequisites, disconnected explanations, contradictory claims, missing required context, and duplication that adds no value. Preference for different wording alone is insufficient.
3. **Fix organization first.** Move prerequisites before dependent steps, group related explanations, and give each section a clear purpose. Consolidate duplicate explanations only when readers can still find the information where needed. Preserve useful summaries, standalone instructions, and repeated warnings at relevant actions.
4. **Check meaning against sources.** Reconcile terminology, commands, values, conditions, and examples using supplied evidence. Preserve necessary details, exceptions, qualifications, and uncertainty. Do not resolve a contradiction by guessing or making every section repeat an unsupported claim. If sources conflict or leave a gap, state the specific uncertainty when relevant to the task.
5. **Improve wording where justified.** Remove filler, clarify ambiguous references, and split overloaded sentences or use lists when that helps readers. Preserve technical meaning and requested scope; shorter is not automatically better.
6. **Check the complete revision.** Confirm that each identified issue was addressed without losing requirements, breaking references, or introducing contradictions. Continue only when you can identify another supported improvement. Stop when none remains. A clean draft may legitimately be returned unchanged.

## Short examples

- **Organization:** Move “Create an account” before the first sign-in step when the task requires an account.
- **Repetition:** Merge adjacent identical definitions; retain a necessary warning beside each independently followed destructive procedure.
- **Consistency:** If supplied facts specify seconds, correct a conflicting “milliseconds” label. If the unit is unknown, do not invent it.
- **Wording:** “Is able to export” → “can export”; retain “only administrators” if it limits who can export.

## Sources

- [Google: LLMs in technical writing](https://developers.google.com/tech-writing/two/llms) recommends organization before grammar/style, source constraints, and checking generated responses; it does not validate this candidate.
- [Google: Self-editing](https://developers.google.com/tech-writing/two/editing) offers iterative, audience-centered editing techniques, not a measured guarantee for LLM self-review.
- [Google: Short sentences](https://developers.google.com/tech-writing/one/short-sentences) recommends focused sentences and removing extraneous words; essential meaning still matters.
- [Self-Refine, NeurIPS 2023](https://proceedings.neurips.cc/paper_files/paper/2023/hash/91edff07232fb1b55a505a9e9f6c0ff3-Abstract-Conference.html) reports gains from iterative self-feedback on its evaluated tasks/models. That multi-step protocol does not establish gains from this single-session documentation instruction.
