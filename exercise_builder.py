#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build a lesson's exercise data from a single per-lesson source file.

`enhavo/netradukenda/tekstoj/lessonNN_exercises.yml` replaces the pile of
per-type, per-language files that used to hold a lesson's exercises
(`tradukenda/<lang>/ekzercoj/<type>/NN.yml` plus
`netradukenda/ekzercoj/kompletigu-la-frazojn/NN.yml`). It is an ordered list
of typed units, shared across L1s. Translations are looked up in `slovnik`
(through the ISV morphological analyzer, so inflected forms resolve to their
lemma); anything spelled out in the file overrides the lookup, and anything
that is genuinely per-L1 (like the L1 sentence in `translate-answer`) is a
`{lang: value}` map. See `build_exercises` for the unit types.

The unit list is also the lesson's tab list: each unit is one tab/page, in
file order, and an exercise unit's `id` is its URL segment. Besides exercise
units it can hold the built-in `text`, `vocab` and `grammar` units (no other
fields), which are the lesson's text, new-words and grammar pages.
"""

import re
import sys

import yaml

# Exercise unit types. `label` is the fasado key naming the type (page
# heading; also the key of the by-type view the Markdown backend still uses),
# `numbered` types are captioned "Ekzerco N" in the tab bar, the others use
# their label. Each type is rendered by templates/ex_<type with _>.html.
EXERCISE_TYPES = {
    'translate': {'label': 'Traduku', 'numbered': True},
    'translate-answer': {'label': 'Traduku kaj respondu', 'numbered': True},
    'cloze': {'label': 'Kompletigu la frazojn', 'numbered': True},
    'choose': {'label': 'Elektu la ĝustan opcion', 'numbered': False},
}

# Built-in (non-exercise) units: unit `type` -> tab id, URL segment, template
# and fasado caption key. The text page is the lesson's root URL.
BUILTIN_UNITS = {
    'text': {'id': 'teksto', 'href': '', 'template': 'teksto', 'fasado_key': 'Teksto'},
    'vocab': {'id': 'vortoj', 'href': 'vortoj/', 'template': 'vortoj', 'fasado_key': 'Novaj vortoj'},
    'grammar': {'id': 'gramatiko', 'href': 'gramatiko/', 'template': 'gramatiko', 'fasado_key': 'Gramatiko'},
}

_ID_RE = re.compile(r'^[a-z][a-z0-9-]*$')

_TOKEN_RE = re.compile(r'\w+|[^\w\s]', re.UNICODE)
_GAP_RE = re.compile(r'\[([^\[\]]*)\]')


def _l1(value, language, where):
    """Pick `language`'s entry out of a {lang: value} map (None if absent)."""
    if not isinstance(value, dict):
        raise ValueError("%s: expected a {language: value} map, got %r" % (where, value))
    return value.get(language)


# ---------------------------------------------------------------- slovnik --

def split_synonyms(text):
    """'kafe, café, jedan (jedna, jedno)' -> ['kafe', 'café', 'jedan'].
    Splits on top-level commas and drops parenthetical remarks."""
    parts, depth, current = [], 0, ''
    for ch in text:
        if ch == '(':
            depth += 1
            continue
        if ch == ')':
            depth = max(depth - 1, 0)
            continue
        if depth:
            continue
        if ch == ',':
            parts.append(current)
            current = ''
        else:
            current += ch
    parts.append(current)
    return list(dict.fromkeys(p.strip() for p in parts if p.strip()))


class Glosser(object):
    """Looks ISV words up in `slovnik` (via `pymorphy2` lemmatization) and
    returns per-L1 translations, so exercises don't have to spell them out.

    Where a lemma has several senses the most frequent one wins; the report
    mentions the others so a wrong pick is easy to spot and override.
    """

    def __init__(self, slovnik, get_morph):
        self._slovnik = slovnik
        self._get_morph = get_morph   # called lazily: loading the analyzer is slow
        self._rows = None

    def _by_lemma(self):
        if self._rows is None:
            self._rows = {}
            ordered = self._slovnik.sort_values('frequency', ascending=False, kind='stable')
            for row in ordered.itertuples():
                self._rows.setdefault(row.isv, []).append(row)
        return self._rows

    def lemma(self, word, prefer_exact=False):
        """Headword for `word`, or None if slovnik knows neither the word
        itself nor its analyzer lemma. `prefer_exact` is for words that are
        already lemmas (vocabulary lists)."""
        rows = self._by_lemma()
        exact = word.lower().replace('dʒ', 'đ')
        if prefer_exact and exact in rows:
            return exact
        parses = self._get_morph().parse(word)
        if parses:
            lemma = parses[0].normal_form.replace('dʒ', 'đ').lower()
            if lemma in rows:
                return lemma
        return exact if exact in rows else None

    def senses(self, lemma, language):
        """[(part of speech, [synonyms])] for `lemma`, most frequent first."""
        result = []
        for row in self._by_lemma().get(lemma, []):
            value = getattr(row, language, None)
            if isinstance(value, str) and value.strip():
                result.append((row.partOfSpeech, split_synonyms(value)))
        return result


def _other_senses_note(senses):
    if len(senses) < 2:
        return None
    return "%d other sense(s): %s" % (len(senses) - 1, '; '.join(', '.join(s[1]) for s in senses[1:]))


def auto_answers(glosser, word, language):
    """(answers, note) for typing `word`'s translation; answers is None if
    slovnik has nothing for this word/L1. A single answer is returned as a
    string, several as a list (the shape the templates expect). English verbs
    are accepted both as 'to X' and as 'X'."""
    lemma = glosser.lemma(word, prefer_exact=True)
    senses = glosser.senses(lemma, language) if lemma else []
    if not senses:
        return None, None
    pos, answers = senses[0]
    if language == 'en' and pos.startswith('v.'):
        bare = [a[3:] if a.startswith('to ') else a for a in answers]
        answers = list(dict.fromkeys(['to ' + a for a in bare] + bare))
    return (answers[0] if len(answers) == 1 else answers), _other_senses_note(senses)


def auto_hint(glosser, token, language):
    """(hint, note) for a word token inside a sentence: the lemma's top
    translation, capitalised like the token."""
    lemma = glosser.lemma(token)
    senses = glosser.senses(lemma, language) if lemma else []
    if not senses:
        return None, None
    hint = senses[0][1][0]
    if token[:1].isupper():
        hint = hint[:1].upper() + hint[1:]
    return hint, _other_senses_note(senses)


class Report(object):
    """What was auto-filled vs. spelled out, which auto-picks had alternative
    senses, and what couldn't be filled at all."""

    def __init__(self):
        self.counts = {}
        self.notes = []
        self.missing = []

    def count(self, unit_id, kind):
        self.counts.setdefault(unit_id, {'auto': 0, 'override': 0})[kind] += 1

    def print(self, source_path, language):
        summary = ', '.join('%s: %d auto/%d override' % (unit_id, c['auto'], c['override'])
                            for unit_id, c in self.counts.items())
        print("[exercises] %s [%s] %s" % (source_path, language, summary), file=sys.stderr)
        for note in self.notes:
            print("    ? " + note, file=sys.stderr)


# ------------------------------------------------------------ unit types --

def parse_choice_items(raw, where):
    """Single-correct multiple-choice items.

    Compact, hand-authored shape: a list of {question, options} entries where
    exactly one string in `options` is prefixed with '+' to mark it correct.
    Returns [{'question': ..., 'options': [{'text', 'correct'}]}] with the
    '+' stripped and turned into a boolean.
    """
    exercises = []
    for item in raw or []:
        options = []
        for raw_option in item['options']:
            correct = raw_option.startswith('+')
            options.append({
                'text': raw_option[1:] if correct else raw_option,
                'correct': correct,
            })
        num_correct = sum(1 for option in options if option['correct'])
        if num_correct != 1:
            raise ValueError(
                "%s: question %r has %d options marked correct (leading "
                "'+'), expected exactly 1" % (where, item['question'], num_correct)
            )
        exercises.append({'question': item['question'], 'options': options})
    return exercises


def parse_cloze_sentence(sentence, where):
    """'Kako jest v[aš]e imę?' -> [{'videbla': 'Kako jest v'}, {'solvo': 'aš'},
    {'videbla': 'e imę?'}]. Brackets mark the part the learner types."""
    parts = []
    pos = 0
    for match in _GAP_RE.finditer(sentence):
        if match.start() > pos:
            parts.append({'videbla': sentence[pos:match.start()]})
        if not match.group(1).strip():
            raise ValueError("%s: empty gap in %r" % (where, sentence))
        parts.append({'solvo': match.group(1).strip()})
        pos = match.end()
    if pos < len(sentence):
        parts.append({'videbla': sentence[pos:]})
    if not any('solvo' in p for p in parts):
        raise ValueError("%s: no [gap] in cloze sentence %r" % (where, sentence))
    return parts


def tokenize_sentence(sentence):
    """Words and single punctuation marks, in order."""
    return _TOKEN_RE.findall(sentence)


def build_translate(unit, language, where, glosser, report):
    """`items`: bare ISV words, or {isv_word: {lang: answer | [answers]}}
    overrides -> [{isv_word: answer}]. A language missing from an override
    map is auto-filled from slovnik."""
    result = []
    unit_id = unit.get('id', 'translate')
    for item in unit['items']:
        if isinstance(item, str):
            isv, overrides = item, {}
        else:
            (isv, overrides), = item.items()
            if not isinstance(overrides, dict):
                raise ValueError("%s: item %r: expected a {language: answer} map" % (where, isv))
        if overrides.get(language) is not None:
            answer = overrides[language]
            report.count(unit_id, 'override')
        else:
            answer, note = auto_answers(glosser, isv, language)
            if answer is None:
                report.missing.append(
                    "%s: no %s translation for %r in slovnik; write `- %s: {%s: ...}`"
                    % (where, language, isv, isv, language))
                continue
            report.count(unit_id, 'auto')
            if note:
                shown = answer if isinstance(answer, str) else ' | '.join(answer)
                report.notes.append("%s -> %s  (%s)" % (isv, shown, note))
        result.append({isv: answer})
    return result


def build_translate_answer(unit, language, where, glosser, report):
    """`items`: {isv: sentence, prompt: {lang: str}, gloss: {lang: {token: hint}}}
    -> [{'demando': prompt, 'rektatraduko': [{isv_word: hint} | punctuation]}].

    `prompt` (the L1 sentence the learner reads) has to be written by hand;
    the per-word hints come from slovnik unless `gloss` overrides a token
    (keyed by the token as written in `isv`, applied to every occurrence)."""
    result = []
    unit_id = unit.get('id', 'translate-answer')
    for item in unit['items']:
        isv = item['isv']
        here = "%s %r" % (where, isv)
        prompt = _l1(item['prompt'], language, here + ' prompt')
        if prompt is None:
            raise ValueError("%s: no prompt for %r" % (here, language))
        overrides = (item.get('gloss') or {}).get(language) or {}
        tokens = tokenize_sentence(isv)
        unknown = set(overrides) - set(tokens)
        if unknown:
            raise ValueError("%s: gloss override for %s names words not in the sentence: %s"
                             % (here, language, ', '.join(sorted(unknown))))
        pairs = []
        for token in tokens:
            if not re.match(r'\w', token):
                pairs.append(token)
            elif token in overrides:
                pairs.append({token: overrides[token]})
                report.count(unit_id, 'override')
            else:
                hint, note = auto_hint(glosser, token, language)
                if hint is None:
                    report.missing.append(
                        "%s: no %s gloss for %r in slovnik; write `gloss: {%s: {%s: ...}}`"
                        % (here, language, token, language, token))
                    continue
                pairs.append({token: hint})
                report.count(unit_id, 'auto')
                if note:
                    report.notes.append("%s: %s -> %s  (%s)" % (isv, token, hint, note))
        result.append({'demando': prompt, 'rektatraduko': pairs})
    return result


def build_cloze(unit, language, where, glosser, report):
    return [parse_cloze_sentence(sentence, where) for sentence in unit['items']]


def build_choose(unit, language, where, glosser, report):
    raw = _l1(unit['items'], language, where + ' items')
    return parse_choice_items(raw, where)


BUILDERS = {
    'translate': build_translate,
    'translate-answer': build_translate_answer,
    'cloze': build_cloze,
    'choose': build_choose,
}


def build_units(source_path, language, glosser):
    """Read a lessonNN_exercises.yml and return the lesson's ordered unit list
    for `language`: [{'id', 'type', 'title', 'items'}], with `items` compiled
    to the shapes the templates use (`items`/`title` are absent on built-in
    units).

    Unit fields: `type` (an EXERCISE_TYPES key, or a BUILTIN_UNITS key, which
    may be written as a bare string), `id` (exercise units only: lowercase
    letters/digits/dashes, becomes the page's URL), `items` (shape depends on
    type; translations come from slovnik unless an item overrides them),
    optional `title` (tab caption; a string or {lang: string}), optional
    `for: [lang...]` to restrict the unit to some L1s. A `choose` unit is
    skipped for an L1 whose key is missing from its `items` map.

    Prints a short report of what was auto-filled, and raises (listing every
    problem at once) if some translation can neither be found nor overridden.
    """
    spec = yaml.load(open(source_path, encoding='utf8').read(), yaml.Loader) or {}
    units = []
    report = Report()
    seen_ids = set(b['id'] for b in BUILTIN_UNITS.values())
    seen_builtin = set()
    for index, unit in enumerate(spec.get('units', []), start=1):
        if isinstance(unit, str):
            unit = {'type': unit}
        unit_type = unit['type']
        where = "%s: unit %d (%s)" % (source_path, index, unit.get('id', unit_type))
        allowed_for = unit.get('for')
        if allowed_for and language not in allowed_for:
            continue
        if unit_type in BUILTIN_UNITS:
            if unit_type in seen_builtin:
                raise ValueError("%s: duplicate built-in unit" % where)
            seen_builtin.add(unit_type)
            units.append({'id': BUILTIN_UNITS[unit_type]['id'], 'type': unit_type})
            continue
        if unit_type not in EXERCISE_TYPES:
            raise ValueError("%s: unknown type (expected one of %s)"
                             % (where, ', '.join(list(EXERCISE_TYPES) + list(BUILTIN_UNITS))))
        unit_id = unit.get('id')
        if not unit_id or not _ID_RE.match(unit_id):
            raise ValueError("%s: needs an `id` (it is the page's URL): lowercase letters, digits, dashes" % where)
        if unit_id in seen_ids:
            raise ValueError("%s: duplicate or reserved id %r" % (where, unit_id))
        seen_ids.add(unit_id)
        if unit_type == 'choose' and language not in unit['items']:
            continue
        title = unit.get('title')
        if isinstance(title, dict):
            title = title.get(language)
        units.append({
            'id': unit_id,
            'type': unit_type,
            'title': title,
            'items': BUILDERS[unit_type](unit, language, where, glosser, report),
        })
    if report.missing:
        raise ValueError('\n'.join(report.missing))
    report.print(source_path, language)
    return units
