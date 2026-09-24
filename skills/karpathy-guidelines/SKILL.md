---
name: karpathy-guidelines
description: Behavioral guidelines to reduce common LLM coding mistakes. Use when writing, reviewing, or refactoring code to avoid overcomplication, make surgical changes, surface assumptions, define verifiable success criteria, and pick the simplest solution via the solution ladder (YAGNI, reuse, stdlib, native platform, one line).
license: MIT
---

# Karpathy Guidelines

Behavioral guidelines to reduce common LLM coding mistakes, derived from [Andrej Karpathy's observations](https://x.com/karpathy/status/2015883857489522876) on LLM coding pitfalls.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

No features beyond what was asked, no abstractions for single-use code, no speculative flexibility, no error handling for impossible scenarios.
If you write 200 lines and it could be 50, rewrite it.
Pick the solution via the ladder in section 5.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. The Solution Ladder

Adapted from [ponytail](https://github.com/DietrichGebert/ponytail) (MIT). Stop at the first rung that holds:

1. Does this need to exist at all? Speculative need = skip it, say so in one line. (YAGNI)
2. Already in this codebase? A helper, util, type, or pattern that already lives here: reuse it. Look before you write.
3. Stdlib does it? Use it.
4. Native platform feature covers it? `<input type="date">` over a picker lib, CSS over JS, DB constraint over app code.
5. Already-installed dependency solves it? Use it. Never add a new one for what a few lines can do.
6. Can it be one line? One line.
7. Only then: the minimum code that works.

Run the ladder after understanding the problem, not instead of it: read the code the change touches and trace the real flow first.
Two rungs work: take the higher one and move on.

Bug fix = root cause, not symptom.
Before editing, grep every caller of the function you are about to touch.
One guard in the shared function beats a guard in every caller, and patching only the reported path leaves sibling callers broken.

Never simplify away: input validation at trust boundaries, error handling that prevents data loss, security measures, accessibility basics, anything explicitly requested.
