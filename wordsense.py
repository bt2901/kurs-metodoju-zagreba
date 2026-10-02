#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Choosing the right analysis of an ISV word, shared by the lesson-text
pipeline (lesson_builder.py) and the exercise glosser (exercise_builder.py)
so that a word gets the same lemma in a popover and in an exercise hint.

The analyzer returns *every* parse of a form (`mylo` is a noun and, as the
past tense of `myti`, a verb; `dobrogo` is accusative or genitive) and
nothing ranks them, so taking `parses[0]` is an arbitrary choice. Authors
disambiguate an occurrence inline, with grammemes in braces right after the
word:

    Žena vidi{3per} dobrogo{masc accs} mųža{accs}.

An annotation keeps the first parse whose tag contains all the listed
grammemes (compared case-insensitively; part-of-speech names such as `verb`
work too). Braces are stripped before tokenizing and never reach the output.
"""

import re
import sys

# Spaces/tabs before the braces are swallowed, so `vidi {3per} dobrogo` and
# `vidi{3per} dobrogo` both become `vidi dobrogo`.
_ANNOTATION_RE = re.compile(r'[ \t]*\{([^{}\n]*)\}')


def parse_grammemes(spec):
    """'masc, accs' / 'masc accs' -> frozenset({'masc', 'accs'})."""
    return frozenset(g.lower() for g in re.split(r'[\s,]+', spec) if g)


def strip_annotations(text, where):
    """Remove `{grammemes}` annotations from `text`.

    Returns (clean_text, notes) where `notes` maps the offset in `clean_text`
    at which the annotated word ENDS to its grammeme set; match it against
    the `stop` offset of a token.
    """
    notes = {}
    pieces = []
    removed = 0
    last = 0
    for match in _ANNOTATION_RE.finditer(text):
        grammemes = parse_grammemes(match.group(1))
        if not grammemes:
            raise ValueError("%s: empty {} annotation" % where)
        pieces.append(text[last:match.start()])
        last = match.end()
        position = match.start() - removed
        removed += match.end() - match.start()
        if position in notes:
            raise ValueError("%s: two annotations on one word: %r" % (where, match.group(0).strip()))
        notes[position] = grammemes
    pieces.append(text[last:])
    return ''.join(pieces), notes


def check_all_attached(notes, where):
    """Call once every token has claimed its annotation (`notes.pop`)."""
    if notes:
        raise ValueError("%s: a {annotation} doesn't directly follow a word "
                         "(clean-text offsets %s)" % (where, sorted(notes)))


def tag_grammemes(parse):
    return frozenset(g.lower() for g in parse.tag.grammemes)


def analysis_key(parse):
    """What makes two parses 'really' different words. The ISV dictionaries
    currently report POS=None for everything, so for now this is the lemma
    alone; it gets sharper by itself once that is fixed upstream."""
    return (parse.tag.POS, parse.normal_form)


def choose_parse(word, parses, grammemes, where, ambiguities=None):
    """The parse to use for one occurrence of `word`."""
    if not grammemes:
        if ambiguities is not None:
            ambiguities.note(word, parses)
        return parses[0]
    matching = [p for p in parses if grammemes <= tag_grammemes(p)]
    if not matching:
        raise ValueError(
            "%s: no parse of %r has {%s}; available parses:\n%s"
            % (where, word, ' '.join(sorted(grammemes)), format_parses(parses)))
    if len(set(analysis_key(p) for p in matching)) > 1:
        print("[ambiguous] %s: {%s} still fits several analyses of %r, using the first:\n%s"
              % (where, ' '.join(sorted(grammemes)), word, format_parses(matching)),
              file=sys.stderr)
    return matching[0]


def format_parses(parses):
    return '\n'.join('    %s | %s' % (p.normal_form, str(p.tag).replace(',', ' ')) for p in parses)


def format_analyses(parses, max_tags=2):
    """One line per distinct analysis (lemma/POS), with a few of its tags."""
    groups = {}
    for p in parses:
        groups.setdefault(analysis_key(p), []).append(str(p.tag).replace(',', ' '))
    lines = []
    for (_, lemma), tags in groups.items():
        more = ' (+%d more)' % (len(tags) - max_tags) if len(tags) > max_tags else ''
        lines.append('    %s | %s%s' % (lemma, '; '.join(tags[:max_tags]), more))
    return '\n'.join(lines)


class Ambiguities(object):
    """Collects words whose parses differ in more than inflection (different
    lemma or part of speech), so the author knows where an annotation is
    needed. Case/number ambiguity (`dobrogo`) is deliberately not reported."""

    def __init__(self):
        self._seen = {}

    def note(self, word, parses):
        if len(set(analysis_key(p) for p in parses)) < 2:
            return
        key = (word.lower(), tuple(analysis_key(p) for p in parses))
        entry = self._seen.setdefault(key, {'word': word, 'parses': parses, 'count': 0})
        entry['count'] += 1

    def print(self, where):
        for entry in self._seen.values():
            print("[ambiguous] %s: %r (x%d) has several analyses, using the first; "
                  "write %s{...} to choose:\n%s"
                  % (where, entry['word'], entry['count'], entry['word'], format_analyses(entry['parses'])),
                  file=sys.stderr)
        self._seen = {}


def lemma_of(word, word_parse, morph):
    """Dictionary form for an occurrence of `word` parsed as `word_parse`.

    The ISV dictionaries' `normal_form` is not reliably a nominative, and
    some indeclinable/special words come out wrong, so this patches it up
    (moved here unchanged from lesson_builder so that exercises and texts
    resolve words alike).
    """
    # dirty fix: manually force word to be in a nominative
    # for some reason it tends to not work with ISV pymorphy2 dictionaries
    lemma = word_parse.normal_form
    lemma_tags = morph.parse(lemma)[0].tag
    if any(pos in lemma_tags.grammemes for pos in ['adj', 'noun', 'pron']):
        # dirty fix: manually select a 'correct' parse >_>
        if word.lower() == "jedno":
            lemma = 'jedin'
        elif word.lower() == "sę":
            lemma = 'sę'
        elif word.lower() == "ljudi":
            lemma = 'ljudi'
        #elif word.lower() == "začto":  #TODO: no adverbs in pymorphy for now...
        #    lemma = 'začto'
        elif word.lower() in ["ja", "mně"]:
            lemma = 'ja'
        elif "nom" not in lemma_tags.grammemes and "indecl" not in lemma_tags.grammemes:
            target = {"nom"}
            if "int" in lemma_tags.grammemes:
                target = {"nom"}
            if "prs" in lemma_tags.grammemes:
                target = {"nom", "sing"}
            if "adj" in lemma_tags.grammemes:
                target = {"nom", "sing", "masc"}
            if "noun" in lemma_tags.grammemes:
                target = {"nom", "sing"}
            tmp = word_parse.inflect(target)
            if tmp is None:  # print debug info before crashing
                print(word)
                print([lemma, lemma_tags])
                print(word_parse)
            lemma = tmp.word
    return lemma.replace('dʒ', 'đ')  # dʒ -> đ
