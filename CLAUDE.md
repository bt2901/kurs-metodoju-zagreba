# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Originally the engine behind [esperanto12.net](https://esperanto12.net/) / [kurso-zagreba-metodo](https://github.com/Esperanto/kurso-zagreba-metodo): an Esperanto course rendered from structured YAML into static HTML/EPUB/PDF/Anki decks, in 40+ target languages (see `agordoj/lingvoj.yml`).

This fork (`bt.uytya`/Viktor Bulatov) is **mid-conversion from Esperanto into an Interslavic (ISV) course**. Recent commits (`95fa738db remove non-slavic languages`, `a74110f8e remove vorto and ekzerco for now`, `eb1a7072e remove all lections >1 for now`, `fa99ceba9 PoC for EN`) have stripped the repo down to a single lesson (lesson 01) and a single target language (`en`) as a proof of concept while the content model is reworked. Do not treat the reduced state (`TOTAL_N` in [layout.py](layout.py): lessons `range(1, TOTAL_N)` are built) as accidental breakage — it's deliberate scope-narrowing during the port. `course.py new-lesson` bumps it as lessons come back.


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
- **Ragged (lesson × L1) coverage.** Current coverage is a single global `TOTAL_N` in `layout.py` (`range(1, TOTAL_N)`). The target is a per-**(lesson × L1)** status grid (`written | stub | absent`), so a lesson can exist for `ru`+`pl` but not yet for another L1; the build renders, per L1, only `written` cells. This supersedes the global-N model when implemented — until then `TOTAL_N` stays global (`course.py check` already prints a lesson × language status grid derived from the files).
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
python generate.py --lingvo en --eligformo md --printendaj-partoj ekzercoj solvoj --printendaj-unuoj cloze --printendaj-lecionoj 1
```

Check what a lesson or language still lacks, and scaffold new ones (see `python course.py --help`):

```bash
python course.py check                       # errors (would break the build), warnings, and a lesson x language grid; exit 1 on errors
python course.py check --lingvo hr --fast    # --fast skips the exercise check (it loads the ISV analyzer)
python course.py new-lesson 3 [--grammar]    # source stub + structure stub, bumps TOTAL_N; never overwrites
python course.py new-language pl --name Polski [--name-eo pola] [--from en]   # copies UI strings, adds a lingvoj.yml entry
```

There is no test suite and no linter configured in this repo currently; `course.py check` is the closest thing to a consistency test.

## Architecture

Where source files live is defined once in [layout.py](layout.py) (used by `generate.py`, `glosses.py` and `course.py`; also holds `TOTAL_N`). `generate.py` is the entry point of the build and orchestrates everything:

1. `load(language)` first regenerates any lesson text that has a Markdown source (see below), then reads YAML content from `enhavo/` and the ISV dictionary from `isv_nlp_utils`, and assembles one big `enhavo` (= "content") dict: `vortaro` (dictionary), `finajxoj` (endings), `ordoj` (numbers/months/seasons/weekdays), `fasado` (UI strings), `enkonduko`/`post` (intro/outro markdown), and `lecionoj` (a list of per-lesson dicts with `teksto`, `gramatiko`, `ekzercoj`, `vortoj`).
2. Content under `enhavo/netradukenda/` is language-independent (lesson texts, exercise skeletons, numbers/months tables); content under `enhavo/tradukenda/<lang>/` is per-target-language (grammar prose, UI strings/`fasado`, `en`'s legacy vocab files, `gramatiko`, `ekzercoj`).
3. Depending on `--eligformo`, either `html_generiloj.generi.generate_html(...)` or `leo_markdown.package.kreu_md(...)` renders the `enhavo` dict through Jinja2 templates (`html_generiloj/templates/*.html` or `leo_markdown/templates/*.md`).
4. `html_generiloj/generi.py` also builds an Anki deck via `genanki` (a git submodule at `genanki/`) and writes it to `<output>/<lang>/eksporto/<lang>.apkg`.

`html_generiloj/output/` is entirely build output and is gitignored — except that historically a handful of hand-maintained, language-independent site files (css/js/img/audio, `favicon.ico`, the site's root landing page) lived there anyway, force-added to git despite the ignore rule, because their relative URLs need to resolve under the served output tree. Those files now live in the normally-tracked `html_assets/` at the repo root instead; `generi.py`'s `copy_static_html_assets()` copies them into `html_generiloj/output/` on every HTML build (before the per-language `shutil.rmtree`, which only ever clears `output/<lang>/` and never touches this shared copy). Treat `html_assets/` as source — edit files there, not their copies under `output/`.

Per-lesson tabs in the generated site come from the lesson's unit list (see "Lesson units and exercises"). The Markdown output has a fixed book layout (text, new words, grammar, then all exercises, then collected solutions in two columns); the unit list decides which of those a lesson has, and exercises/solutions are rendered per unit, in unit order, by `leo_markdown/templates/ekzerco_<type>.md` / `solvo_<type>.md`. Everything the build reports goes to stderr, because stdout is the Markdown.

### Lesson-text source pipeline (`lesson_builder.py`)

For each lesson `NN`, if `enhavo/netradukenda/tekstoj/lessonNN_source.md` exists, `load()` treats it as the source of truth: [lesson_builder.py](lesson_builder.py) reads the `# Title` + body-paragraph Markdown, tokenizes it (`razdel`), runs every recognisable word through the ISV etymological-alphabet analyzer (`isv_nlp_utils.constants.create_analyzers_for_every_alphabet`), splits each word into stem + inflectional suffix via its pymorphy2 paradigm table, and rewrites `enhavo/netradukenda/tekstoj/NN.yml` with the result before the normal YAML-loading code runs. If no `_source.md` exists for a lesson, its `.yml` is used as-is (untouched) — this is how older/future lessons without a Markdown source keep working.

This replaces the manual workflow that used to live in `maintenance/uczebnik.ipynb` (write ISV prose in a notebook cell → run the tokenize/analyze cells → copy the printed YAML by hand into the `.yml` file → separately re-run an asset-inlining cell against the built HTML for lesson 1). The notebook's asset-inlining step (rewriting `<link>`/`<script src>` tags in `html_generiloj/output/en/01/**/*.html` into inline `<style>`/`<script>`) is **not** covered by `lesson_builder.py` and still needs to be run manually from the notebook if that self-contained-HTML behavior is still wanted. The purpose of asset-inlining step is making html self-contained, so it could be easily shared with people (the hosting of artifacts on the GH Pages is on the roadmap for the future development).

#### Choosing the right parse of a word (`wordsense.py`)

The analyzer returns every parse of a form (`mylo` = noun, or past tense of `myti`; `vidi` = 3per or imperative; `dobrogo` = acc or gen) and `parses[0]` is an arbitrary pick, so an occurrence can be disambiguated inline with grammemes in braces right after the word, in `lessonNN_source.md` and in `isv:` sentences of `translate-answer` units:

```
Žena vidi{3per} dobrogo{masc accs} mųža{accs}.      (attached or spaced: `vidi {3per}` also works)
```

An annotation keeps the first parse whose tag contains all the listed grammemes (case-insensitive; POS names like `verb`/`noun` work because matching uses `tag.grammemes`, not `tag.POS`). No match fails the build and lists the available parses; an annotation that doesn't directly follow a word is an error. Braces are stripped before tokenizing and never reach the output. Unannotated words whose parses differ in lemma/POS are listed on stderr (`[ambiguous] …`); case/number-only ambiguity is deliberately not reported. Two parses count as different analyses when `(POS, normal_form)` differs (`wordsense.analysis_key`); **temporarily**, particles, conjunctions, interjections and adverbs (`FUNCTION_WORD_POS`) count as one POS, because how the community distinguishes them is unsettled. The ISV dictionaries' `tag.POS` was reported to be unreliable upstream; the key falls back to the lemma alone if it is `None`. The lemma fix-ups (forced nominative etc.) live in `wordsense.lemma_of`, shared by texts and exercise hints.

#### Word overrides (`glosses.py`)

For words the analyzer or `slovnik` get wrong or lack (`kapučino` is read as an adjective and isn't in `slovnik`; `Nikola` is a name), one `glosses:` entry fixes the word everywhere it appears: text popovers, the new-words list, exercise hints and answers. Entries live under `glosses:` in `lessonNN_structure.yml` (that lesson) and in `enhavo/netradukenda/glosoj.yml` (whole course); the lesson's win. Each is keyed by a word as written (any inflected form, case-insensitive) or by a lemma:

```yaml
glosses:
  kapučino:
    lemma: kapučino                              # replaces the analyzer's lemma
    gloss: {en: cappuccino, ru: капучино}        # popover + exercise hint (and typed answer, unless `answer` is set)
    answer: {en: cappuccino}                     # optional: what a `translate` item expects typed
  nikola:
    gloss: male name                             # bare string = interface string, translated in tradukenda/<lang>/fasado/glosoj.yml
    scope: local                                 # popover only: not in the new-words list / dictionary
  necivilizovanogo:
    lemma: civilizovany
    morphemes: [ne, {civilizovan: stem}, ogo]    # forced split for the popover table; must spell the word
```

A bare string or `{lang: text | [texts]}` is shorthand for `gloss:`. A string gloss with no translation in that language's `fasado` falls back to the English text and is reported on stderr (`[glosses] …`). `lesson_builder` applies `lemma`/`morphemes` and stamps the token with a language-independent `gloss_key` in `NN.yml`; `generate.load()` resolves the per-language text into `leciono['glosoj']` (popovers, via `tradukajxo.html`) and, for `scope: course`, into `enhavo['vortaro']`; `exercise_builder.Glosser` consults the same entries before `slovnik`. Item-level overrides inside a unit (`{word: {lang: answer}}`, `gloss:` on a `translate-answer` sentence) are still the most specific and win.

### Lesson units and exercises (`exercise_builder.py`)

If `enhavo/netradukenda/tekstoj/lessonNN_structure.yml` exists, its ordered `units` list **is the lesson's tab list** and the single source of all its exercises (lessons 1 and 2). A lesson without one just gets its built-in pages (text, new words, and grammar if `tradukenda/<lang>/gramatiko/NN.md` exists). Lessons 3–12 still have Esperanto-era files (`tradukenda/<lang>/gramatiko/NN.md`, `netradukenda/ekzercoj/kompletigu-la-frazojn/NN.yml`, `netradukenda/vortoj/NN.yml`) that are not built; treat them as raw material, not ISV content.

- **Built-in units:** `grammar`, `text`, `vocab` (bare strings) are the grammar/text/new-words pages; list them wherever you want them in the tab order. The grammar notes file is read only for a lesson with a `grammar` unit, and `netradukenda/vortoj/NN.yml` (the optional "extra words" list) only if it exists.
- **Exercise units:** `translate`, `translate-answer`, `cloze` (`[gap]` brackets), `choose` (`+correct`). Each needs an `id`, which is its URL (`NN/<id>/`); optional `title` (string or `{lang: str}`) overrides the tab caption; optional `for: [lang, ...]` restricts a unit to some L1s. For any exercise type, `items` may be a `{lang: [items]}` map when the exercise itself differs per L1 (different sentences or questions); the unit then drops out for any L1 without an entry. Any number of units of any type per lesson.
- **Translations** are looked up in `slovnik` (lemma via the etymological `pymorphy2` analyzer, most frequent sense wins) and only need writing out where `slovnik` lacks the word or the contextual form matters (`gloss: {ru: {jest: есть}}` per token, or `{word: {lang: answer}}` for `translate`). The build prints what it auto-filled, flags auto-picks that had other senses, and fails listing every word it can't fill. The L1 sentence in `translate-answer` (`prompt`) is always hand-written.
- **Rendering:** [generate.py](generate.py)'s `build_tabs()` makes one tab per unit; exercise tabs render `html_generiloj/templates/ex_<type>.html` (extending `ekzerco_base.html`). Numbered types are captioned "Ekzerco N" by position (`choose` uses its label). To add an exercise type: register it in `EXERCISE_TYPES` + a `build_<type>` in `exercise_builder.py`, and add `ex_<type>.html`.
- **Markdown selection:** `--printendaj-partoj` takes `teksto vortoj gramatiko ekzercoj solvoj`; `--printendaj-lecionoj` takes lesson numbers; `--printendaj-unuoj` takes exercise unit ids (all by default).

`generate.py` currently hardcodes a debug pickle dump to `C:\dev\kurso-zagreba-metodo\leciono.pkl` inside `load()` — this is a leftover debugging artifact tied to this specific machine path, along with `enhavo.pkl` (written unconditionally at the end of `load()`) and `slovnik.pkl`. These `.pkl` files are build-time debug output, not source content — don't treat them as data to edit or commit.

## Licensing (relevant when touching content)

- Esperanto lesson texts under `enhavo/netradukenda/tekstoj` are CC BY-ND (must stay unchanged) — see `enhavo/netradukenda/tekstoj/PERMESILO.md`. As ISV content replaces these, confirm with the user what license applies to the new material.
- Everything else is CC BY 4.0 ([PERMESILO.md](PERMESILO.md)), attributing [AUTHORS.md](AUTHORS.md).
