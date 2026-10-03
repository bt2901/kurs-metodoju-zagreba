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

An annotation may also say which dictionary sense of the word is meant, by
its English translation as slovnik writes it (a full translation, or a single
word of it that identifies the sense), alone or after the grammemes:

    Ty jesi imal{sense: must, have to} znati, že my imamo{sense: have, possess, own} tut lavky.
"""

import re
import sys
from collections import namedtuple

# Spaces/tabs before the braces are swallowed, so `vidi {3per} dobrogo` and
# `vidi{3per} dobrogo` both become `vidi dobrogo`.
_ANNOTATION_RE = re.compile(r'[ \t]*\{([^{}\n]*)\}')


Annotation = namedtuple('Annotation', 'grammemes sense')

# `sense:` starts the English text of a sense (which may itself contain commas
# and spaces); whatever precedes it are grammemes.
_SENSE_RE = re.compile(r'(?:^|[\s,])sense\s*:')


def parse_annotation(spec, where):
    """'3per sense: have, own' -> Annotation({'3per'}, 'have, own')."""
    sense = None
    match = _SENSE_RE.search(spec)
    if match:
        sense = spec[match.end():].strip()
        spec = spec[:match.start()]
        if not sense:
            raise ValueError("%s: `sense:` needs the English text of a sense" % where)
    grammemes = parse_grammemes(spec)
    if not grammemes and sense is None:
        raise ValueError("%s: empty {} annotation" % where)
    return Annotation(grammemes, sense)


def describe(annotation):
    """The annotation as the author would write it, for messages."""
    parts = sorted(annotation.grammemes)
    if annotation.sense:
        parts.append('sense: ' + annotation.sense)
    return ' '.join(parts)


# Words that slovnik lists only as one of these never inflect, so the
# analyzer has nothing to say about them -- and the ISV dictionaries are
# missing many of them, which makes it guess (`i` as the bare adjective ending
# `y`; `poka` has no conjunction parse at all). For such a word the slovnik
# spelling itself is the lemma.
INDECLINABLE_POS = frozenset({'adv.', 'prep.', 'intj.', 'conj.', 'particle'})
# Annotations that ask for that reading explicitly: `poka{conj}`.
INDECLINABLE_TAGS = frozenset({'adv', 'advb', 'prep', 'intj', 'conj', 'prcl', 'part', 'particle'})


def split_variants(headword):
    """'iměti, imati' -> ['iměti', 'imati']: a slovnik headword may list
    several spellings; parenthetical remarks are dropped."""
    text = re.sub(r'\([^)]*\)', '', headword)
    return [v.strip() for v in text.split(',') if v.strip()]


def indeclinable_words(slovnik):
    """Lowercase spellings (variants included) that slovnik lists only as an
    adverb, preposition, interjection, conjunction or particle."""
    parts = {}
    for headword, pos in zip(slovnik['isv'].astype(str), slovnik['partOfSpeech'].astype(str)):
        for variant in split_variants(headword):
            parts.setdefault(variant.lower(), set()).add(pos)
    return frozenset(word for word, found in parts.items() if found <= INDECLINABLE_POS)


def use_dictionary_form(word, grammemes, indeclinable):
    """Should `word` be taken as its slovnik spelling instead of being parsed?
    Yes if slovnik knows it only as an indeclinable word -- unless the author
    asked for a particular parse with grammemes (`vse{pron}`); a part-of-speech
    annotation like `{conj}` asks for exactly this reading."""
    if not indeclinable or word.lower() not in indeclinable:
        return False
    return not grammemes or grammemes <= INDECLINABLE_TAGS


def parse_grammemes(spec):
    """'masc, accs' / 'masc accs' -> frozenset({'masc', 'accs'})."""
    return frozenset(g.lower() for g in re.split(r'[\s,]+', spec) if g)


def strip_annotations(text, where):
    """Remove `{grammemes / sense: ...}` annotations from `text`.

    Returns (clean_text, notes) where `notes` maps the offset in `clean_text`
    at which the annotated word ENDS to its Annotation; match it against the
    `stop` offset of a token.
    """
    notes = {}
    pieces = []
    removed = 0
    last = 0
    for match in _ANNOTATION_RE.finditer(text):
        annotation = parse_annotation(match.group(1), where)
        pieces.append(text[last:match.start()])
        last = match.end()
        position = match.start() - removed
        removed += match.end() - match.start()
        if position in notes:
            raise ValueError("%s: two annotations on one word: %r" % (where, match.group(0).strip()))
        notes[position] = annotation
    pieces.append(text[last:])
    return ''.join(pieces), notes


def check_all_attached(notes, where):
    """Call once every token has claimed its annotation (`notes.pop`)."""
    if notes:
        raise ValueError("%s: a {annotation} doesn't directly follow a word "
                         "(clean-text offsets %s)" % (where, sorted(notes)))


def tag_grammemes(parse):
    return frozenset(g.lower() for g in parse.tag.grammemes)


# TEMPORARY: the community hasn't settled how particles, conjunctions,
# interjections (and the adverb reading of words like `ne`) differ, so for
# deciding whether a form is ambiguous they all count as one part of speech.
# Words whose only competing parses are in this group are not reported.
FUNCTION_WORD_POS = frozenset({'PRCL', 'CONJ', 'INTJ', 'ADVB'})


def analysis_key(parse):
    """What makes two parses 'really' different words: (POS, lemma), with the
    function-word POS merged (see FUNCTION_WORD_POS). If the dictionary
    reports no POS (None), the lemma alone decides."""
    pos = parse.tag.POS
    if pos in FUNCTION_WORD_POS:
        pos = 'OTHER'
    return (pos, parse.normal_form)


def choose_parse(word, parses, grammemes, where, ambiguities=None):
    """The parse to use for one occurrence of `word`."""
    if not grammemes:
        if ambiguities is not None:
            ambiguities.note(word, parses)
        return parses[0]
    matching = [p for p in parses if grammemes <= tag_grammemes(p)]
    if not matching:
        raise ValueError(
            "%s: no parse of %r has {%s}; available parses:\n%s\n"
            "(If the analyzer simply lacks the word, give it a `glosses:` entry: `%s: {lemma: ...}`.)"
            % (where, word, ' '.join(sorted(grammemes)), format_parses(parses), word.lower()))
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
