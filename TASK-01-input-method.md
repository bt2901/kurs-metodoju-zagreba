# TASK-01 — Diacritic-tolerant input for exercise fields

## Context

Exercises 1 and 3 ask the learner to type ISV answers. Many learners won't have
an ISV keyboard and can't type diacritics or etymological letters
(č š ž ě å ę ų ń ŕ ľ …). We must not gatekeep beginners on input, but we do want
them to learn the correct spelling. Exercises have a **known expected answer**,
so the MVP needs no dictionary or morphology at runtime.

## Goal

When a learner types an answer without (or with partial) diacritics, accept it
if it matches the expected answer *modulo diacritics*, then display the
correctly-spelled form so the learner sees the target orthography.

## MVP approach (static, self-contained, client-side JS is fine here)

1. Implement a JS **normalisation** function mapping ISV text
   (Latin / Cyrillic / etymological) to a common diacritic-stripped ASCII-ish
   key. Respect the **asymmetry rule**: stripping diacritics is allowed for the
   *accept* comparison, but the *displayed* correct answer always uses full
   orthography — a user's bare `e` may satisfy an expected `ě` for acceptance,
   never the reverse in display.
2. On submit, compare `normalise(userInput)` with `normalise(expectedAnswer)`.
   Equal → mark correct.
3. On correct, render the expected answer in full correct orthography next to the
   user's input, so they see e.g. `zena → žena`.

## Reference / inspiration

- https://www.lexilogos.com/keyboard/diacritics.htm — a "magic key" style
  diacritic-insertion virtual keyboard, relevant to the nice-to-have below
  (not the MVP itself).
- https://isv.miraheze.org/wiki/MediaWiki:Gadget-im.js — source code of JS gadget 
  reponsible for diacritic-management on the ISV wiki
- http://luki.sdf-eu.org/txt/cs-encodings-faq.html — a table summarizing various semi-official standards (TeX and RFC 1345) for representing Czech and Slovak characters in an ASCII-friendly way


## Nice-to-have (separate, do NOT do now)

- A "magic key" (Alt/Ctrl + letter) that inserts the diacritical variant while
  typing.
- Dictionary-backed reconciliation for *free-form* input (would use pymorphy2
  diacritic restoration). Out of scope: exercises have fixed answers.

## Out of scope — hard boundaries

- Do NOT touch lesson content or the YAML/build pipeline.
- Do NOT modify the frontend framework (Bootstrap + jQuery stays).
- Do NOT implement Cyrillic↔Latin transliteration (that is a separate task).

## Acceptance criteria

- A field whose expected answer is `žena` accepts `zena` and `žena` (and, if
  reasonable, `zhena`); rejects clearly unrelated input.
- On acceptance, the full correct spelling `žena` is shown.
- Normalisation lives in one small, testable JS function with a handful of unit
  examples covering all three alphabets and the asymmetry rule.
- Behaviour for answers already typed with correct diacritics is unchanged.

## Verify

Rebuild the static site, open a lesson with Exercise 1, and test the cases above
in the browser. Add the unit examples for the normalisation function and run them.

## Suggested workflow for the agent

Plan first (no edits), show the plan, wait for approval. Then implement on a
branch, commit in small steps, and show diffs before anything destructive.
