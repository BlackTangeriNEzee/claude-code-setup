# Post-Interview Report

Write the report as a markdown file in the student's project directory, named `interview-report-<YYYY-MM-DD>.md`.
If that file already exists, append `-2`, `-3`, and so on.
Report language: the student's language.
Every section below is REQUIRED, in this order. Fill every slot; write "none" rather than omitting a section.

## Template

```markdown
# Interview Report - <date> - <level>

## Round summary
Level, questions asked (X of budget Y), how many came from the custom list vs generated,
and how the round ended (budget spent / student stopped).

## Per-question record
For each question asked:
- **Q<n>** [list | generated] - the question as asked (English)
- Their answer, key points only
- Grade: mastered / fuzzy / failed
- What a strong answer includes - this is where the teaching happens
- Notes: answer requests refused, English slips, trap outcome, live-coding result (if any)

## Weak points
Aggregated and deduplicated across questions.
Each entry points at a concrete file/function/line and names the underlying concept
(e.g. "reference vs copy semantics - sell_item in inventory.py").

## Custom question list status
Which list questions were covered this round and which carry over.
If no list was provided, write: "No custom list provided."

## Verdict
Predicted performance at the real interview in the current state:
**pass comfortably / borderline / at risk**, with a one-sentence justification.

## What to do next
Which study-mode layers to revisit, which files or functions to focus on,
and whether to re-run the interview - at which level.
```

## Grading standard

- **mastered**: correct, specific, survived the follow-ups.
- **fuzzy**: partially correct, vague, or collapsed under a follow-up.
- **failed**: wrong, no answer, agreed with a false trap statement, or asked for the answer.

## After writing

Tell the student the file path, state the verdict in one sentence, and point at the single highest-value thing to fix next.
Do not paste the whole report into chat.
