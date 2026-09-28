# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Originally the engine behind [esperanto12.net](https://esperanto12.net/) / [kurso-zagreba-metodo](https://github.com/Esperanto/kurso-zagreba-metodo): an Esperanto course rendered from structured YAML into static HTML/EPUB/PDF/Anki decks, in 40+ target languages (see `agordoj/lingvoj.yml`).

This fork (`bt.uytya`/Viktor Bulatov) is **mid-conversion from Esperanto into an Interslavic (ISV) course**. Recent commits (`95fa738db remove non-slavic languages`, `a74110f8e remove vorto and ekzerco for now`, `eb1a7072e remove all lections >1 for now`, `fa99ceba9 PoC for EN`) have stripped the repo down to a single lesson (lesson 01) and a single target language (`en`) as a proof of concept while the content model is reworked. Do not treat the reduced state (`TOTAL_N = 2` in [generate.py](generate.py) and [html_generiloj/generi.py](html_generiloj/generi.py), meaning "lessons range(1, 2)" = just lesson 1) as accidental breakage — it's deliberate scope-narrowing during the port. Expect both `TOTAL_N` constants to need updating together as more lessons come back.


### Positioning (why the content model is being reworked at all)

ISV is taught here as an **inter-Slavic** language, not a foreign one: the target audience are Slavs who already own most of the grammar, so teaching is a **diff against the learner's L1** ("locative works like in Russian, but X / like in Polish, but Y"), not a system built from scratch. This preserves the Esperanto12 niche — basics in one evening — and it's the reason per-L1 content is first-class rather than a translation afterthought.

A consequence used throughout: **text difficulty is L1-relative.** The same text is "hard" for an English speaker (all cases new) and "easy" for a case-having Slav (cases already installed).

### Architectural decisions — do not violate without asking

- **Stay static.** Content is generated ahead of time by Python; the output is static HTML (or MD/EPUB/PDF/Anki `.apkg` via `genanki`). Don't introduce a runtime backend as the default.
- **Morphology runs at build time**, not runtime, via the external `isv_nlp_utils` package (`from isv_nlp_utils.slovnik import get_slovnik, download_slovnik, prepare_slovnik` in [generate.py](generate.py)), installed separately from [github.com/bt2901/isv_nlp_utils](https://github.com/bt2901/isv_nlp_utils) (see Commands below). It's **not** in [requirements.txt](requirements.txt) yet — that's a pending decision, not an oversight to "fix" unilaterally.
- **Keep the existing frontend stack** (Bootstrap + jQuery, server-rendered Jinja2 templates). Don't modernize or rewrite it.

### How ISV differs from Esperanto (breaks assumptions baked into the old engine)

- Esperanto is agglutinative (one morpheme = one meaning); the old per-morpheme YAML vocab files under `enhavo/tradukenda/<lang>/vortaro/*.yml` (`radiko.yml`, `prefikso.yml`, `sufikso.yml`, ...) assumed clean morpheme splits.
- ISV is fusional (endings fuse case+number+gender per declension class), so the lesson-text source format has already changed: `enhavo/netradukenda/tekstoj/01.yml` now stores each token as a `lemma` plus a `morfemes` list with grammeme tags, e.g. `PARK: stem` / `U: masc NOUN sing loct` — this is pymorphy2-shaped output, not a manual morpheme split. Lexical translation now goes through an ISV↔target-language dictionary (`slovnik`, loaded via `isv_nlp_utils`) keyed by lemma, not the old per-word YAML vocab files.
- **`enhavo/netradukenda/tekstoj/NN.yml` is a generated build artifact, not the source of truth, whenever a matching `lessonNN_source.md` sits next to it.** The actual source is plain ISV prose (`# Title` line + body paragraphs); [lesson_builder.py](lesson_builder.py) tokenizes it, runs it through the ISV morphological analyzer, and regenerates the tagged YAML on every `generate.py` run (see Architecture below). Edit the `_source.md` file, not the `.yml`, for lesson 1 — a hand-edit to `01.yml` will be silently overwritten on the next build.
- Three alphabets apply to ISV content: Latin, Cyrillic, and the etymological "Medžuslovjansky Plus" spelling. Diacritics are **optionally** dropped by learners (`zena` accepted where `žena` is correct) but never the reverse — this asymmetry matters for any input/exercise-checking logic (see [TASK-01-input-method.md](TASK-01-input-method.md)).

### Pedagogy note

ISV grammar can't be deferred the way Esperanto's can, so **grammar drives lesson ordering; word frequency (from `isv_nlp_utils`/pymorphy2 over an ISV corpus) chooses which vocabulary fills each grammar slot** — this is a human/pedagogical call, not something to infer from code. 

- **Lesson 1 is the etymological-alphabet L1 bridge**, not a grammar lesson: it teaches how ISV letters decode into the learner's L1 via regular correspondences — the purest form of the diff positioning, and it aligns with the engine's original alphabet-first Lesson 1. It is delivered as a **staged reveal** (see recursive units below): (A) letters identical to the L1, read for free; (B) familiar sounds under diacritics (`č š ž ě`), "ignore the mark to read"; (C) the payload — etymologically loaded letters (`å ě ę ų ȯ ė ć đ ŕ …`) that encode a correspondence into the L1, with the **Y/Ы caveat** as a per-L1 aside for the languages that need it. Lesson-1 illustrative vocabulary is `scope: local` (see below).
- **The Lipson "Cultural Park" story is NOT Lesson 1** (an earlier assumption). It exercises all seven cases, both numbers, short/long adjectives, clitic/full pronouns — near the whole grammar. It moves to a **later lesson and doubles as a recurring spine text** (chunks appear early, full read as the payoff). For a case-having Slavic L1 taught by diff, its effective placement is ~L3–L5, not Lipson's original 15.

### Near-term scope

The current PoC target is `en`, but that is a **pipeline smoke test only** — English has no etymological bridge to ISV, so it cannot exercise the L1-bridge pedagogy. The first *pedagogically real* slice L1 is Slavic: **`ru` first, `pl` as the immediate fan-out** (an east/west pair proves the diff isn't one-language-specific). Build one Slavic L1 end-to-end before fanning out. Per-L1 alphabet content for `cs/ru/sk/sh/bg/pl/uk` is largely pre-written (see Licensing), so fan-out is cheap — but it should follow a working pipe, not precede it.

## Target content model (design decisions — NOT all implemented yet)

These are agreed directions for the reworked model. Where they aren't in the code yet, they're goals, not current behavior — don't assume the mechanism exists until you see it.

- **Per-L1 content** extends the existing per-target-language split (`enhavo/tradukenda/<lang>/`, already language-keyed). Each grammar/section cell holds a *contrastive note* ("like Russian, but…"), not a translation. Popover glosses come per-L1 from the Medžuslovnik translations.
- **Recursive content units.** A lesson is a tree of typed units (`prose | exercise | image | interactive`) and units **nest**; a "subsection" is just a nested unit, not a new type. This generalizes the current fixed tabs (Teksto / Vortoj / Gramatiko / three exercise types). Staging (e.g. Lesson 1's A/B/C) = ordered child units.
- **Conditional asides.** Any unit may carry a `for="…"` L1-visibility set; the per-language build includes or drops it. This is how "a case/aspect primer only for `bg`/`mk`" works without forking lessons — shared lessons with optional sections, not per-L1 lessons.
- **Vocab scope: `local` vs `course`.** The Zagreb premise is a cumulative, frequency-ranked `course` word list, reused across lessons and in the shared gloss pool. `local` vocab is scoped to **(lesson, L1)**, illustrative, and must **not** enter the cumulative list or the reuse pool. Lesson 1's alphabet-decoding words are `local`. Tag entries accordingly so throwaway bridge-vocab doesn't pollute frequency stats.
- **Ragged (lesson × L1) coverage.** Current coverage is a single global `TOTAL_N` (`range(1, TOTAL_N)`). The target is a per-**(lesson × L1)** status grid (`written | stub | absent`), so a lesson can exist for `ru`+`pl` but not yet for another L1; the build renders, per L1, only `written` cells. This supersedes the global-N model when implemented — until then `TOTAL_N` stays global and both constants move together.
- **Coverage matrix + policy asserts (build tooling, not yet present; there's no test suite).** Derive the coverage map from source so it can't drift. A hand-written landing-page "highlights" caption references block IDs; the build **fails** on a dead reference (a caption pointing at a deleted block) and **warns** on an undescribed conditional block. Captions are authored (editorial voice); coordinates are derived (checked). Never hand-maintain the map itself.

### Division of labor

- **Human decides — do not invent:** pedagogy, lesson sequencing, which grammar goes in which lesson, input-method philosophy, tagset/grammeme design, which L1s are in scope.
- **Agent handles:** format conversion, build glue, wiring `isv_nlp_utils` output into generation, the coverage-matrix/aside/scope plumbing above, making things build and render, tests.

## Commands

Run from the repo root.

```bash
pip install -r requirements.txt
pip install git+https://github.com/bt2901/isv_nlp_utils
```

(`isv_nlp_utils` isn't in `requirements.txt` yet — undecided whether it should be added there; ask before changing that.)

If any lesson has a `lessonNN_source.md` (currently just lesson 1), regenerating its YAML also needs the ISV pymorphy2 dictionaries (`out_isv_lat`/`out_isv_etm`/`out_isv_cyr`) — these are **not** part of this repo, `requirements.txt`, or the `isv_nlp_utils` package. Point `ISV_DICT_PATH` at the local directory that has them (e.g. an `ISV_data_gathering` checkout) before running `generate.py`:

```bash
export ISV_DICT_PATH="/path/to/ISV_data_gathering/"
```

Without it, `generate.py` fails fast with a clear `FileNotFoundError` naming the missing directory.

Generate HTML (writes to `html_generiloj/output/<lang>/`):

```bash
python generate.py --lingvo en --eligformo html
```

Generate Markdown (prints the whole course to stdout) — needed as an intermediate step for PDF/EPUB via [Pandoc](https://pandoc.org) (v2+):

```bash
python generate.py --lingvo en --eligformo md
python generate.py --lingvo en --eligformo md | pandoc --latex-engine=xelatex -o en.pdf
python generate.py --lingvo en --eligformo md | pandoc -o en.epub
```

Limit output to specific parts/lessons (see `--help` for all choices):

```bash
python generate.py --lingvo en --eligformo md --printendaj-partoj ekzerco2 solvo2 --printendaj-lecionoj 1 2 3
```

There is no test suite and no linter configured in this repo currently.

## Architecture

`generate.py` is the single entry point and orchestrates everything:

1. `load(language)` first regenerates any lesson text that has a Markdown source (see below), then reads YAML content from `enhavo/` and the ISV dictionary from `isv_nlp_utils`, and assembles one big `enhavo` (= "content") dict: `vortaro` (dictionary), `finajxoj` (endings), `ordoj` (numbers/months/seasons/weekdays), `fasado` (UI strings), `enkonduko`/`post` (intro/outro markdown), and `lecionoj` (a list of per-lesson dicts with `teksto`, `gramatiko`, `ekzercoj`, `vortoj`).
2. Content under `enhavo/netradukenda/` is language-independent (lesson texts, exercise skeletons, numbers/months tables); content under `enhavo/tradukenda/<lang>/` is per-target-language (grammar prose, UI strings/`fasado`, `en`'s legacy vocab files, `gramatiko`, `ekzercoj`).
3. Depending on `--eligformo`, either `html_generiloj.generi.generate_html(...)` or `leo_markdown.package.kreu_md(...)` renders the `enhavo` dict through Jinja2 templates (`html_generiloj/templates/*.html` or `leo_markdown/templates/*.md`).
4. `html_generiloj/generi.py` also builds an Anki deck via `genanki` (a git submodule at `genanki/`) and writes it to `<output>/<lang>/eksporto/<lang>.apkg`.

`html_generiloj/output/` is entirely build output and is gitignored — except that historically a handful of hand-maintained, language-independent site files (css/js/img/audio, `favicon.ico`, the site's root landing page) lived there anyway, force-added to git despite the ignore rule, because their relative URLs need to resolve under the served output tree. Those files now live in the normally-tracked `html_assets/` at the repo root instead; `generi.py`'s `copy_static_html_assets()` copies them into `html_generiloj/output/` on every HTML build (before the per-language `shutil.rmtree`, which only ever clears `output/<lang>/` and never touches this shared copy). Treat `html_assets/` as source — edit files there, not their copies under `output/`.

Per-lesson tabs in the generated site are: Teksto (text), Vortoj (new words), Gramatiko (grammar), and three exercise types (Traduku / Traduku kaj respondu / Kompletigu la frazojn), each with a `solvoN` (solution) counterpart in the Markdown output.

### Lesson-text source pipeline (`lesson_builder.py`)

For each lesson `NN`, if `enhavo/netradukenda/tekstoj/lessonNN_source.md` exists, `load()` treats it as the source of truth: [lesson_builder.py](lesson_builder.py) reads the `# Title` + body-paragraph Markdown, tokenizes it (`razdel`), runs every recognisable word through the ISV etymological-alphabet analyzer (`isv_nlp_utils.constants.create_analyzers_for_every_alphabet`), splits each word into stem + inflectional suffix via its pymorphy2 paradigm table, and rewrites `enhavo/netradukenda/tekstoj/NN.yml` with the result before the normal YAML-loading code runs. If no `_source.md` exists for a lesson, its `.yml` is used as-is (untouched) — this is how older/future lessons without a Markdown source keep working.

This replaces the manual workflow that used to live in `maintenance/uczebnik.ipynb` (write ISV prose in a notebook cell → run the tokenize/analyze cells → copy the printed YAML by hand into the `.yml` file → separately re-run an asset-inlining cell against the built HTML for lesson 1). The notebook's asset-inlining step (rewriting `<link>`/`<script src>` tags in `html_generiloj/output/en/01/**/*.html` into inline `<style>`/`<script>`) is **not** covered by `lesson_builder.py` and still needs to be run manually from the notebook if that self-contained-HTML behavior is still wanted. The purpose of asset-inlining step is making html self-contained, so it could be easily shared with people (the hosting of artifacts on the GH Pages is on the roadmap for the future development).

`generate.py` currently hardcodes a debug pickle dump to `C:\dev\kurso-zagreba-metodo\leciono.pkl` inside `load()` — this is a leftover debugging artifact tied to this specific machine path, along with `enhavo.pkl` (written unconditionally at the end of `load()`) and `slovnik.pkl`. These `.pkl` files are build-time debug output, not source content — don't treat them as data to edit or commit.

## Licensing (relevant when touching content)

- Esperanto lesson texts under `enhavo/netradukenda/tekstoj` are CC BY-ND (must stay unchanged) — see `enhavo/netradukenda/tekstoj/PERMESILO.md`. As ISV content replaces these, confirm with the user what license applies to the new material.
- Everything else is CC BY 4.0 ([PERMESILO.md](PERMESILO.md)), attributing [AUTHORS.md](AUTHORS.md).
