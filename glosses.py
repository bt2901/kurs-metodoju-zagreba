#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Word-level overrides ("glosses") shared by lesson texts and exercises.

The analyzer and `slovnik` get some words wrong or don't have them at all
(`kapučino` is read as an adjective and isn't in the dictionary; `Nikola` is
a name). An override says what a word is, once, and every place that shows
or checks it -- text popovers, the new-words list, exercise hints and
answers -- uses it. Overrides live in a `glosses:` map in
`lessonNN_structure.yml` (applies to that lesson) and in
`enhavo/netradukenda/glosoj.yml` (the whole course); the lesson's entries
win. Each entry is keyed by a word as written (any inflected form,
case-insensitive) or by a lemma:

    glosses:
      kapučino:
        lemma: kapučino                  # replaces the analyzer's lemma
        gloss: {en: coffee drink, ru: кофейный напиток}
        answer: {en: cappuccino, ru: капучино}   # what `translate` expects typed
      nikola:
        gloss: male name                 # bare string: an interface string,
        scope: local                     #   translated in fasado/glosoj.yml
      necivilizovanogo:
        lemma: civilizovany
        morphemes: [ne, {civilizovan: stem}, ogo]

`gloss`/`answer` are a bare string (an interface string, looked up in the
language's `fasado` like "Dodatak" for "Appendix"; the text itself is the
English fallback) or a `{lang: text | [texts]}` map. `scope: local` keeps the
word out of the new-words list and the shared dictionary (popovers only).
An entry may also be just the gloss: `vladimir: male name` or
`vladimir: {en: ..., ru: ...}`.
"""

import os
import re

import yaml

import layout

ENTRY_FIELDS = {'gloss', 'answer', 'lemma', 'morphemes', 'scope'}
SCOPES = ('course', 'local')
_LANG_RE = re.compile(r'^[a-z]{2,3}$')
COURSE_PATH = layout.COURSE_GLOSSES


def normalize(raw, where):
    """Validate a raw `glosses` map; returns {lowercase key: entry dict}."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("%s: `glosses` must be a map of word -> entry" % where)
    result = {}
    for key, value in raw.items():
        here = "%s: gloss %r" % (where, key)
        if isinstance(value, dict) and not value:
            raise ValueError("%s: empty entry" % here)
        if isinstance(value, dict) and set(value) & ENTRY_FIELDS:
            entry = dict(value)
        elif isinstance(value, str) or (isinstance(value, dict) and all(_LANG_RE.match(str(k)) for k in value)):
            entry = {'gloss': value}   # shorthand: just the gloss
        elif isinstance(value, dict):
            raise ValueError("%s: unknown field(s) %s (known: %s; a {language: text} map needs "
                             "language codes as keys)" % (here, ', '.join(sorted(map(str, value))),
                                                          ', '.join(sorted(ENTRY_FIELDS))))
        else:
            raise ValueError("%s: expected a gloss or an entry map, got %r" % (here, value))
        unknown = set(entry) - ENTRY_FIELDS
        if unknown:
            raise ValueError("%s: unknown field(s) %s (known: %s)"
                             % (here, ', '.join(sorted(unknown)), ', '.join(sorted(ENTRY_FIELDS))))
        entry.setdefault('scope', 'course')
        if entry['scope'] not in SCOPES:
            raise ValueError("%s: scope must be one of %s" % (here, ', '.join(SCOPES)))
        if 'morphemes' in entry:
            entry['morphemes'] = _normalize_morphemes(entry['morphemes'], here)
        if not (entry.keys() - {'scope'}):
            raise ValueError("%s: entry has no gloss, answer, lemma or morphemes" % here)
        result[str(key).lower()] = entry
    return result


def _normalize_morphemes(raw, where):
    """[ne, {civilizovan: stem}, ogo] -> [('ne', ''), ('civilizovan', 'stem'), ('ogo', '')]"""
    if not isinstance(raw, list) or not raw:
        raise ValueError("%s: morphemes must be a non-empty list" % where)
    pieces = []
    for item in raw:
        if isinstance(item, str):
            pieces.append((item, ''))
        elif isinstance(item, dict) and len(item) == 1:
            (morpheme, tags), = item.items()
            pieces.append((str(morpheme), str(tags or '')))
        else:
            raise ValueError("%s: a morpheme is a string or a {morpheme: tags} map, got %r" % (where, item))
    return pieces


def load_overrides(structure_path=None, course_path=COURSE_PATH):
    """Course-wide overrides, updated by the lesson's `glosses:` (if its
    structure file exists)."""
    merged = {}
    if course_path and os.path.exists(course_path):
        raw = yaml.load(open(course_path, encoding='utf8').read(), yaml.Loader)
        merged.update(normalize(raw, course_path))
    if structure_path and os.path.exists(structure_path):
        spec = yaml.load(open(structure_path, encoding='utf8').read(), yaml.Loader) or {}
        merged.update(normalize(spec.get('glosses'), structure_path))
    return merged


def lookup(overrides, surface, lemma=None):
    """(key, entry) for a word occurrence: by the form as written, else by
    its lemma; (None, None) if there is no override."""
    for candidate in (surface, lemma):
        if candidate and candidate.lower() in overrides:
            return candidate.lower(), overrides[candidate.lower()]
    return None, None


def text(raw, language, fasado, missing=None):
    """The `gloss`/`answer` text for `language` (a string, a list of strings,
    or None if the entry says nothing for that language).

    A bare string is an interface string: translated through `fasado` (the
    language's UI strings); when there is no translation the string itself
    is used, as English, and noted in `missing` (a set of (string, language)).
    """
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw.get(language)
    if isinstance(raw, list):
        return raw
    translated = fasado.get(raw)
    if translated is None:
        if language != 'en' and missing is not None:
            missing.add((raw, language))
        return raw
    return translated


def apply_morphemes(word, pieces, where):
    """Cut `word` into the given morphemes (keeping its capitalisation) and
    return them as [{piece: tags}], as the text YAML stores them."""
    if ''.join(p for p, _ in pieces).lower() != word.lower():
        raise ValueError("%s: morphemes %s don't spell %r"
                         % (where, '+'.join(p for p, _ in pieces), word))
    result = []
    position = 0
    for piece, tags in pieces:
        result.append({word[position:position + len(piece)]: tags})
        position += len(piece)
    return result
