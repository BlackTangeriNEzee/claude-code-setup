# Interview Helper

A Claude skill that helps you truly master your own coding assignment before an oral code interview (viva / code walkthrough / interview-style assessment).

Many courses (UQ, USYD, and others) check coding projects with an interview.
A tutor asks hard questions about your own code, and you fail if you cannot answer.
Asking AI to "explain my project to me" gives a false sense of understanding.
This skill takes the opposite approach: it makes you produce the answers yourself, then shows you exactly where you are weak.

## What it does

**Study mode** - guided understanding of your own project, five layers deep:
overview, modules, functions and lines, design decisions, edge cases.
You explain first; the AI only corrects and fills gaps. Each layer ends with a quiz gate.

**Interview mode** - a mock interview on your code, in English, at one of three levels:

| Level | Tests | Style |
|---|---|---|
| Easy | "What" | Code visible, surface questions, gentle. Answer in any language. |
| Hard | "Why" | Design decisions, edge cases, "what if we change X". Follow-ups. Answer in any language. |
| Hell | "Did you really write this" | Integrity interrogation, trap questions, live coding, follow-ups to the bottom. English answers required. |

No hints, no mid-round corrections, no answer keys - just like the real thing.
After each round you get a written report: per-question grades, weak points mapped to your code, a verdict, and what to study next.

## Install

Claude Code (recommended):

```bash
cp -R interview-helper ~/.claude/skills/interview-helper
```

claude.ai: upload the folder as a skill in your capabilities settings.

## Use

Just tell Claude about your interview - the skill triggers on phrases like
"I have a code interview on my assignment", "考考我", "拷打我", "quiz me on my project".
Or invoke it directly: `/interview-helper`.

Helpful extras you can provide (all optional):

- The assignment spec or marking rubric - questions will target the assessment points.
- A question list - past interview questions from other students, a course question bank, or your own worry list. These get asked first.

## Honest use

This skill is for understanding your own work, which is exactly what interview assessments exist to check.
It will not write or fix your assignment, and it refuses to hand out model answers to memorize - memorized answers die on the first follow-up anyway.
