#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Course tooling: see what a lesson or language still lacks, and create the
files for a new one.

    python course.py check [--lingvo en ru ...] [--lecionoj 1 2 ...] [--fast] [-v]
    python course.py new-lesson N [--grammar]
    python course.py new-language CODE --name "Polski" [--name-eo pola] [--from en]

`check` reports what would break the build (ERROR), what the build lets
through but the reader would notice (warn), and a lesson x language grid.
It reuses the build's own code (exercise_builder, glosses, ...) so it can't
disagree with it about what is an error. Exit status 1 if there are errors.
Where the files live is defined once, in layout.py.
"""

import argparse
import contextlib
import io
import os
import re
import sys
from collections import namedtuple

import yaml

import yamlsetup  # noqa: F401 (YAML On/Off/Yes/No stay strings)
import exercise_builder
import glosses
import layout

ERROR, WARN, INFO = 'ERROR', 'warn', 'info'
Problem = namedtuple('Problem', 'level lesson lang message')

_FASADO_KEY_RE = re.compile(r"""fasado\[\s*['"]([^'"]+)['"]\s*\]""")


def load_yaml(path):
    with open(path, encoding='utf8') as f:
        return yaml.load(f.read(), yaml.Loader)


def read_lingvoj():
    return load_yaml(layout.LINGVOJ) or {}


def load_fasado(lang):
    """The language's UI strings (all fasado/*.yml merged), as the build does."""
    merged = {}
    directory = layout.fasado_dir(lang)
    if os.path.isdir(directory):
        for name in sorted(os.listdir(directory)):
            if name.endswith('.yml'):
                merged.update(load_yaml(directory + name) or {})
    return merged


def template_fasado_keys():
    """UI strings the templates ask for (literal `fasado['...']` lookups),
    plus the ones the build looks up by variable."""
    keys = set()
    for directory in layout.TEMPLATE_DIRS:
        for name in os.listdir(directory):
            if not name.endswith(('.html', '.md', '.js')) or not os.path.isfile(directory + name):
                continue
            with open(directory + name, encoding='utf8') as f:
                keys.update(_FASADO_KEY_RE.findall(f.read()))
    keys.update(t['label'] for t in exercise_builder.EXERCISE_TYPES.values())
    return keys


def required_fasado_keys():
    """UI strings whose absence crashes the build (tab captions)."""
    keys = {b['fasado_key'] for b in exercise_builder.BUILTIN_UNITS.values()}
    keys.add('Ekzerco 1')
    return keys


# ------------------------------------------------------------------- check --

def check_language(lang, entry, slovnik_languages, reference_fasado):
    """Problems that affect every lesson of one language."""
    out = []

    def add(level, message):
        out.append(Problem(level, None, lang, message))

    if not isinstance(entry, dict):
        add(ERROR, "no entry in %s" % layout.LINGVOJ)
    else:
        nomo = entry.get('nomo') or {}
        for field in ('fontlingve', 'esperante'):
            if not nomo.get(field):
                add(ERROR, "%s: nomo.%s is missing" % (layout.LINGVOJ, field))
        if entry.get('stato') not in ('preta', 'testa'):
            add(WARN, "%s: stato should be 'preta' or 'testa' (it decides whether the language is "
                      "listed in the site's language menu)" % layout.LINGVOJ)
        if 'aŭtoroj' not in entry:
            add(ERROR, "%s: aŭtoroj (a list, may be empty) is missing" % layout.LINGVOJ)
    if slovnik_languages is not None and lang not in slovnik_languages:
        add(ERROR, "%r is not a column of slovnik, so no word can be translated into it" % lang)

    if not os.path.isdir(layout.lang_dir(lang)):
        add(ERROR, "directory %s does not exist" % layout.lang_dir(lang))
        return out
    for path in (layout.intro(lang), layout.outro(lang)):
        if not os.path.exists(path):
            add(ERROR, "%s is missing" % path)
    fasado = load_fasado(lang)
    if not fasado:
        add(ERROR, "no UI strings found in %s" % layout.fasado_dir(lang))
        return out
    missing_required = sorted(required_fasado_keys() - set(fasado))
    if missing_required:
        add(ERROR, "UI strings missing (the build needs them for tab captions): %s"
            % '; '.join(missing_required))
    missing_other = sorted((template_fasado_keys() - required_fasado_keys()) - set(fasado))
    if missing_other:
        add(WARN, "%d UI string(s) used by the templates are missing and render as empty text: %s%s"
            % (len(missing_other), '; '.join(missing_other[:6]), ' ...' if len(missing_other) > 6 else ''))
    if reference_fasado is not None and lang != reference_fasado[0]:
        same = [k for k, v in fasado.items() if reference_fasado[1].get(k) == v and len(str(v)) > 3]
        if same:
            add(INFO, "%d UI string(s) are identical to %s (untranslated?)" % (len(same), reference_fasado[0]))
    return out


def structure_spec(n, languages):
    """(spec or None, problems) for the lesson's structure file."""
    path = layout.structure(n)
    out = []
    if not os.path.exists(path):
        return None, [Problem(INFO, n, None, "no %s: only the built-in pages (text, new words%s)"
                              % (os.path.basename(path), ', grammar if notes exist'))]
    try:
        spec = load_yaml(path) or {}
        glosses.normalize(spec.get('glosses'), path)
        units = spec.get('units')
        if not isinstance(units, list):
            raise ValueError("%s: `units` must be a list" % path)
    except (ValueError, yaml.YAMLError) as error:
        return None, [Problem(ERROR, n, None, str(error).replace('\n', ' '))]
    known = set(languages)
    seen_builtin = set()
    for index, unit in enumerate(units, start=1):
        unit = {'type': unit} if isinstance(unit, str) else unit
        label = "unit %d (%s)" % (index, unit.get('id', unit.get('type')))
        if unit.get('type') in exercise_builder.BUILTIN_UNITS:
            if unit['type'] in seen_builtin:
                out.append(Problem(ERROR, n, None, "%s: built-in unit listed twice" % label))
            seen_builtin.add(unit['type'])
        elif unit.get('type') not in exercise_builder.EXERCISE_TYPES:
            out.append(Problem(ERROR, n, None, "%s: unknown type %r" % (label, unit.get('type'))))
            continue
        mentioned = set(unit.get('for') or [])
        items = unit.get('items')
        if isinstance(items, dict):   # per-L1 items: {lang: [items]}
            mentioned |= set(items)
            lists = [i for i in items.values() if isinstance(i, list)]
        else:
            lists = [items] if isinstance(items, list) else []
        for item in (item for items_list in lists for item in items_list):
            if isinstance(item, dict) and isinstance(item.get('prompt'), dict):
                mentioned |= set(item['prompt'])
        unknown = sorted(c for c in mentioned if c not in known)
        if unknown:
            out.append(Problem(WARN, n, None, "%s mentions language(s) not in %s: %s"
                               % (label, layout.LINGVOJ, ', '.join(unknown))))
    return spec, out


def effective_units(spec, lang):
    """The units a lesson has for `lang`: ([builtin types], [exercise units])."""
    builtin, exercises = [], []
    for unit in (spec or {}).get('units', []):
        unit = {'type': unit} if isinstance(unit, str) else unit
        if unit.get('for') and lang not in unit['for']:
            continue
        if unit.get('type') in exercise_builder.BUILTIN_UNITS:
            builtin.append(unit['type'])
        elif isinstance(unit.get('items'), dict) and lang not in unit['items']:
            continue
        elif unit.get('type') in exercise_builder.EXERCISE_TYPES:
            exercises.append(unit)
    return builtin, exercises


def check_lesson(n, languages):
    """(problems shared by all languages, spec)."""
    out = []
    source, text = layout.source_md(n), layout.text_yml(n)
    if not os.path.exists(source) and not os.path.exists(text):
        out.append(Problem(ERROR, n, None, "no text: neither %s nor %s exists" % (source, text)))
    elif os.path.exists(source):
        with open(source, encoding='utf8') as f:
            if not re.match(r'^#\s*\S', f.read()):
                out.append(Problem(ERROR, n, None, "%s must start with a '# Title' line" % source))
        dependencies = [source, layout.structure(n), layout.COURSE_GLOSSES]
        newest = max((os.path.getmtime(p) for p in dependencies if os.path.exists(p)), default=0)
        if not os.path.exists(text):
            out.append(Problem(WARN, n, None, "%s hasn't been generated yet (run a build)" % text))
        elif os.path.getmtime(text) < newest:
            out.append(Problem(WARN, n, None, "%s is older than its sources (run a build); the "
                                              "translation checks below use the old text" % text))
    spec, structure_problems = structure_spec(n, languages)
    out.extend(structure_problems)
    for path in layout.audio(n):
        if not os.path.exists(path):
            out.append(Problem(WARN, n, None, "audio file %s is missing (the text page links to it)" % path))
    return out, spec


def text_words(n):
    """[{'lemma', 'key', 'sense'}] for every analysed word of the lesson text."""
    path = layout.text_yml(n)
    if not os.path.exists(path):
        return []
    teksto = load_yaml(path)
    words = []
    for paragraph in [teksto.get('titolo') or []] + (teksto.get('paragrafoj') or []):
        for item in paragraph:
            token = item['token'] if item else None
            if isinstance(token, dict):
                words.append({'lemma': token['lemma'].replace('dʒ', 'đ'),
                              'key': token.get('gloss_key'), 'sense': token.get('sense')})
    return words


def check_cell(n, lang, spec, overrides, fasado, slovnik_words, glosser, deep, lexicon=None):
    """Problems of one lesson in one language."""
    out = []

    def add(level, message):
        out.append(Problem(level, n, lang, message))

    builtin, exercises = effective_units(spec, lang)
    grammar_path = layout.grammar(lang, n)
    if spec is None:
        has_grammar = os.path.exists(grammar_path)
    else:
        has_grammar = 'grammar' in builtin
    if has_grammar and not os.path.exists(grammar_path):
        add(ERROR, "the lesson has a grammar page but %s is missing" % grammar_path)
    elif not has_grammar and os.path.exists(grammar_path):
        add(INFO, "%s exists but the lesson has no `grammar` unit for %s (not built)" % (grammar_path, lang))
    for unit in exercises:
        exercise_type = exercise_builder.EXERCISE_TYPES[unit['type']]
        if not exercise_type['numbered'] and exercise_type['label'] not in fasado and not unit.get('title'):
            add(ERROR, "unit %r is captioned by the UI string %r, which %s lacks"
                % (unit.get('id'), exercise_type['label'], lang))

    if deep and spec is not None and glosser is not None:
        buffer = io.StringIO()
        try:
            with contextlib.redirect_stderr(buffer):
                exercise_builder.build_units(layout.structure(n), lang, glosser)
        except ValueError as error:
            for line in str(error).split('\n'):
                add(ERROR, "exercises: " + line)
        except Exception as error:  # a crash the build would hit too
            add(ERROR, "exercises: %s: %s" % (type(error).__name__, error))

    if slovnik_words is not None:
        missing = []
        sense_problems = []
        for word in text_words(n):
            lemma, key = word['lemma'], word['key']
            entry = overrides.get(key) if key else None
            sense = word['sense']
            if sense is None and entry is not None:
                if glosses.text(entry.get('gloss'), lang, fasado) is not None:
                    continue
                sense = entry.get('sense')
            if sense is not None and lexicon is not None:
                try:
                    if lexicon.entry(lemma, lang, sense) is not None:
                        continue
                except exercise_builder.SenseError as error:
                    if str(error) not in sense_problems:
                        sense_problems.append(str(error))
                    continue
            elif lemma in slovnik_words.get(lang, ()):
                continue
            if lemma not in missing:
                missing.append(lemma)
        for problem in sense_problems:
            add(ERROR, "sense: " + problem)
        if missing:
            add(WARN, "%d word(s) of the text show no translation in popovers: %s%s"
                % (len(missing), ', '.join(missing[:10]), ' ...' if len(missing) > 10 else ''))
    return out


def load_slovnik(languages):
    """(column names, {lang: set of ISV lemmas that have a translation})."""
    from isv_nlp_utils.slovnik import get_slovnik, prepare_slovnik
    with contextlib.redirect_stdout(io.StringIO()):
        slovnik = get_slovnik()['words']
        prepare_slovnik(slovnik)
    words = {}
    for lang in languages:
        if lang in slovnik.columns:
            column = slovnik[lang]
            present = column.notna() & (column.astype(str).str.strip() != '')
            words[lang] = set(slovnik.loc[present, 'isv'])
    return set(slovnik.columns), words, slovnik


def check(args):
    lingvoj = read_lingvoj()
    languages = args.lingvo or list(lingvoj)
    unknown = [lang for lang in languages if lang not in lingvoj]
    if unknown:
        print("not in %s: %s" % (layout.LINGVOJ, ', '.join(unknown)), file=sys.stderr)
        return 2
    lessons = args.lecionoj or list(layout.lessons())

    columns, slovnik_words, slovnik = load_slovnik(languages)
    reference = ('en', load_fasado('en')) if os.path.isdir(layout.lang_dir('en')) else None
    problems = []
    for lang in languages:
        problems += check_language(lang, lingvoj[lang], columns, reference)

    lexicon = exercise_builder.Glosser(slovnik, lambda: None)   # dictionary lookups only
    etm_morph = None
    for n in lessons:
        shared, spec = check_lesson(n, list(lingvoj))
        problems += shared
        overrides = glosses.load_overrides(layout.structure(n)) if spec is not None else glosses.load_overrides(None)
        # a structure error is already reported once; don't repeat it per language
        structure_ok = not any(p.level == ERROR and p.lang is None for p in shared)
        for lang in languages:
            glosser = None
            if not args.fast and spec is not None and structure_ok and lang in columns:
                if etm_morph is None:
                    import lesson_builder
                    etm_morph = lesson_builder.get_etm_analyzer()
                fasado = load_fasado(lang)
                glosser = exercise_builder.Glosser(slovnik, lambda: etm_morph, overrides, fasado)
            problems += check_cell(n, lang, spec, overrides, load_fasado(lang), slovnik_words, glosser,
                                   not args.fast, lexicon)

    built = set(layout.lessons())
    on_disk = sorted(
        {int(m.group(1)) for name in os.listdir(layout.TEKSTOJ)
         for m in [re.match(r'lesson(\d+)_(?:source\.md|structure\.yml)$', name)] if m} - built)
    if on_disk:
        problems.append(Problem(INFO, None, None, "lesson(s) %s have sources but are not built (TOTAL_N = %d in layout.py)"
                                % (', '.join(map(str, on_disk)), layout.TOTAL_N)))
    print_report(problems, languages, lessons, args.verbose)
    return 1 if any(p.level == ERROR for p in problems) else 0


def print_report(problems, languages, lessons, verbose):
    shown = [p for p in problems if verbose or p.level != INFO]

    def where(p):
        if p.lesson is None and p.lang is None:
            return 'course'
        parts = []
        if p.lesson is not None:
            parts.append('lesson %s' % layout.pad(p.lesson))
        if p.lang is not None:
            parts.append(p.lang)
        return ' / '.join(parts)

    order = {ERROR: 0, WARN: 1, INFO: 2}
    for p in sorted(shown, key=lambda p: (p.lesson is not None, p.lesson or 0, p.lang or '', order[p.level])):
        print("%-5s  %-16s %s" % (p.level, where(p), p.message))

    def cell(n, lang):
        mine = [p for p in problems if (p.lesson in (None, n)) and (p.lang in (None, lang))
                and not (p.lesson is None and p.lang is None)]
        if any(p.level == ERROR for p in mine):
            return 'FAIL'
        return 'warn' if any(p.level == WARN for p in mine) else 'ok'

    print()
    print("lesson   " + ''.join('%-6s' % lang for lang in languages))
    for n in lessons:
        print("%-9s" % layout.pad(n) + ''.join('%-6s' % cell(n, lang) for lang in languages))
    errors = sum(p.level == ERROR for p in problems)
    warnings = sum(p.level == WARN for p in problems)
    print("\n%d error(s), %d warning(s)%s" % (errors, warnings, '' if verbose else ' (-v also shows notes)'))


# ---------------------------------------------------------------- scaffold --

SOURCE_STUB = """# TITLE

Text of lesson {n}.
"""

STRUCTURE_STUB = """# Lesson {n}: what it consists of (see lesson01_structure.yml for the format
# and the options).
#
# Draft. Add exercise units, e.g.
#
#   - id: words              # becomes the page's URL: {nn}/words/
#     type: translate
#     items: [kafe, imę]
#
# and word overrides under `glosses:` (see glosses.py).
units:

- text
- vocab
{grammar}"""


def write_new(path, content, created, skipped):
    if os.path.exists(path):
        skipped.append(path)
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf8', newline='\n') as f:
        f.write(content)
    created.append(path)


def new_lesson(args):
    n = args.number
    if n < 1:
        print("lesson numbers start at 1", file=sys.stderr)
        return 2
    if n > layout.TOTAL_N:
        print("lesson %d would leave a gap: create lesson %d first (TOTAL_N = %d)"
              % (n, layout.TOTAL_N, layout.TOTAL_N), file=sys.stderr)
        return 2
    if os.path.exists(layout.source_md(n)) or os.path.exists(layout.structure(n)):
        print("lesson %d already has a source or structure file" % n, file=sys.stderr)
        return 2
    created, skipped = [], []
    write_new(layout.source_md(n), SOURCE_STUB.format(n=n), created, skipped)
    write_new(layout.structure(n), STRUCTURE_STUB.format(
        n=n, nn=layout.pad(n), grammar='- grammar\n' if args.grammar else ''), created, skipped)
    if args.grammar:
        for lang in read_lingvoj():
            if os.path.isdir(layout.lang_dir(lang)):
                write_new(layout.grammar(lang, n), "# TODO\n", created, skipped)
    if n == layout.TOTAL_N:
        with open('layout.py', encoding='utf8') as f:
            source = f.read()
        updated = re.sub(r'^TOTAL_N = \d+', 'TOTAL_N = %d' % (n + 1), source, count=1, flags=re.M)
        with open('layout.py', 'w', encoding='utf8', newline='') as f:
            f.write(updated)
        print("layout.py: TOTAL_N = %d" % (n + 1))
    for path in created:
        print("created  " + path)
    for path in skipped:
        print("KEPT     %s already exists -- not overwritten. Make sure it is not old Esperanto-era "
              "content: it would be built as this lesson's grammar page as it is." % path)
    print("""
Next:
  1. Write the lesson text in %s (the build generates %s from it).
  2. Edit %s: add exercise units and `glosses:`.%s
  3. python course.py check      -- what is still missing
  4. python generate.py --lingvo <lang> --eligformo html""" % (
        layout.source_md(n), layout.text_yml(n), layout.structure(n),
        "\n     Write the grammar notes in each language's gramatiko/%s.md." % layout.pad(n) if args.grammar else
        "\n     (Add `- grammar` and a gramatiko/%s.md per language when it has grammar notes.)" % layout.pad(n)))
    return 0


def new_language(args):
    import shutil
    code = args.code
    if not re.match(r'^[a-z]{2,3}$', code):
        print("language code must be 2-3 lowercase letters", file=sys.stderr)
        return 2
    lingvoj = read_lingvoj()
    if code in lingvoj or os.path.exists(layout.lang_dir(code)):
        print("%r already exists (in %s or as %s)" % (code, layout.LINGVOJ, layout.lang_dir(code)), file=sys.stderr)
        return 2
    reference = args.source
    if not os.path.isdir(layout.lang_dir(reference)):
        print("reference language %r has no directory %s" % (reference, layout.lang_dir(reference)), file=sys.stderr)
        return 2
    if not args.force:
        columns, _, _ = load_slovnik([code])
        if code not in columns:
            print("%r is not a column of slovnik, so no word could be translated into it "
                  "(use --force to create it anyway)" % code, file=sys.stderr)
            return 2

    created, skipped = [], []
    os.makedirs(layout.fasado_dir(code))
    for name in sorted(os.listdir(layout.fasado_dir(reference))):
        shutil.copyfile(layout.fasado_dir(reference) + name, layout.fasado_dir(code) + name)
        created.append(layout.fasado_dir(code) + name)
    for source, target in ((layout.intro(reference), layout.intro(code)),
                           (layout.outro(reference), layout.outro(code))):
        if os.path.exists(source):
            shutil.copyfile(source, target)
            created.append(target)
    for n in layout.lessons():
        spec = load_yaml(layout.structure(n)) if os.path.exists(layout.structure(n)) else None
        if spec is not None and 'grammar' in effective_units(spec, code)[0]:
            write_new(layout.grammar(code, n), "# TODO\n", created, skipped)

    with open(layout.LINGVOJ, encoding='utf8', newline='') as f:
        text = f.read()
    newline = '\r\n' if '\r\n' in text else '\n'
    entry = newline.join([
        '', '%s:' % code,
        '  nomo:',
        '    fontlingve: %s' % args.name,
        '    esperante: %s' % (args.name_eo or args.name),
        '  stato: testa',
        '  komentejo: 0',
        '  aŭtoroj: []', ''])
    with open(layout.LINGVOJ, 'w', encoding='utf8', newline='') as f:
        f.write(text.rstrip('\r\n') + newline + entry)

    print("added %r to %s (stato: testa)" % (code, layout.LINGVOJ))
    for path in created:
        print("created  " + path)
    for path in skipped:
        print("KEPT     %s already exists -- not overwritten" % path)
    print("""
Next:
  1. Translate the copied UI strings in %s*.yml and the intro/outro (they are copies of %s).
  2. Write the grammar notes for each lesson that has a `grammar` unit (stubs were created).
  3. Add `%s:` to the per-language maps in the lesson structure files: `prompt:` of every
     translate-answer sentence, `choose` items, and any `glosses:` that need your language.
  4. python course.py check --lingvo %s
  5. Add a link in html_assets/index.html (hand-maintained landing page), and set
     `stato: preta` in %s when it is ready for the language menu.""" % (
        layout.fasado_dir(code), reference, code, code, layout.LINGVOJ))
    return 0


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='command', required=True)

    p = sub.add_parser('check', help="report what is missing or would break the build")
    p.add_argument('--lingvo', nargs='*', help="languages to check (default: all in lingvoj.yml)")
    p.add_argument('--lecionoj', nargs='*', type=int, help="lesson numbers (default: all built)")
    p.add_argument('--fast', action='store_true',
                   help="skip the exercise check (it loads the ISV analyzer, which takes a few seconds)")
    p.add_argument('-v', '--verbose', action='store_true', help="also show notes")
    p.set_defaults(run=check)

    p = sub.add_parser('new-lesson', help="create the files for lesson N (the next one, or a gap)")
    p.add_argument('number', type=int)
    p.add_argument('--grammar', action='store_true', help="also add a grammar unit and a stub per language")
    p.set_defaults(run=new_lesson)

    p = sub.add_parser('new-language', help="create a language from a copy of another")
    p.add_argument('code', help="language code; must be a column of slovnik")
    p.add_argument('--name', required=True, help="the language's own name, e.g. Polski")
    p.add_argument('--name-eo', help="its name in Esperanto-style romanisation (default: --name)")
    p.add_argument('--from', dest='source', default='en', help="language to copy UI strings from (default: en)")
    p.add_argument('--force', action='store_true', help="don't require a slovnik column")
    p.set_defaults(run=new_language)

    args = ap.parse_args()
    sys.exit(args.run(args))


if __name__ == '__main__':
    main()
