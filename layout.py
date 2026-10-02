#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Where the course's source files live. The build (generate.py), the
checker and the scaffolder (course.py) all use these, so they can't drift.

Language-independent content is under enhavo/netradukenda/, per-language
content under enhavo/tradukenda/<lang>/.
"""

# Lessons 1 .. TOTAL_N-1 are built. A lesson's sources can exist beyond this
# (it is then simply not built yet); course.py new-lesson bumps it.
TOTAL_N = 3

NETRADUKENDA = 'enhavo/netradukenda/'
TRADUKENDA = 'enhavo/tradukenda/'
TEKSTOJ = NETRADUKENDA + 'tekstoj/'
LINGVOJ = 'agordoj/lingvoj.yml'
COURSE_GLOSSES = NETRADUKENDA + 'glosoj.yml'
TEMPLATE_DIRS = ('html_generiloj/templates/', 'leo_markdown/templates/')


def pad(n):
    return str(n).zfill(2)


def lessons():
    return range(1, TOTAL_N)


# --- per lesson (shared by all languages)

def source_md(n):
    """Plain ISV text, the source of the lesson text."""
    return TEKSTOJ + 'lesson' + pad(n) + '_source.md'


def text_yml(n):
    """The tagged text; a build artifact whenever source_md(n) exists."""
    return TEKSTOJ + pad(n) + '.yml'


def structure(n):
    """The lesson's units (tabs) and word overrides."""
    return TEKSTOJ + 'lesson' + pad(n) + '_structure.yml'


def extra_words(n):
    """Optional list of extra words for the new-words page."""
    return NETRADUKENDA + 'vortoj/' + pad(n) + '.yml'


def audio(n):
    return ['html_assets/ogg/%s.ogg' % pad(n), 'html_assets/mp3/%s.mp3' % pad(n)]


# --- per language

def lang_dir(lang):
    return TRADUKENDA + lang + '/'


def grammar(lang, n):
    return lang_dir(lang) + 'gramatiko/' + pad(n) + '.md'


def intro(lang):
    return lang_dir(lang) + 'enkonduko.md'


def outro(lang):
    return lang_dir(lang) + 'post.md'


def fasado_dir(lang):
    return lang_dir(lang) + 'fasado/'
