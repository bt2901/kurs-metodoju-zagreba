#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

import jinja2
import mistune

import exercise_builder


def kreu_md(enhavo, printendaj):
    """Print the course as Markdown.

    `printendaj` selects what to print: 'partoj' (any of teksto, vortoj,
    gramatiko, ekzercoj, solvoj), 'lecionoj' (lesson numbers; None = all) and
    'unuoj' (exercise unit ids; None = all). A lesson's unit list decides
    which of its parts exist; the book layout (text, new words, grammar, then
    exercises, then collected solutions) is fixed.
    """
    md = mistune.Markdown()

    env = jinja2.Environment()
    env.filters['markdown'] = lambda text: jinja2.Markup(md(text))
    env.trim_blocks = True
    env.lstrip_blocks = True
    env.loader = jinja2.FileSystemLoader('leo_markdown/templates/')

    lesson_numbers = printendaj.get('lecionoj') or range(1, len(enhavo['lecionoj']) + 1)
    unknown = [n for n in lesson_numbers if not 1 <= n <= len(enhavo['lecionoj'])]
    if unknown:
        raise ValueError("no such lesson(s): %s (have 1-%d)" % (unknown, len(enhavo['lecionoj'])))
    wanted_units = printendaj.get('unuoj')

    all_unit_ids = set()
    for leciono in enhavo['lecionoj']:
        units = leciono['units']
        all_unit_ids.update(u['id'] for u in units)
        leciono['md_builtin'] = [u['type'] for u in units if u['type'] in exercise_builder.BUILTIN_UNITS]
        leciono['md_unuoj'] = [u for u in units
                               if u['type'] in exercise_builder.EXERCISE_TYPES
                               and (not wanted_units or u['id'] in wanted_units)]
    if wanted_units and set(wanted_units) - all_unit_ids:
        raise ValueError("no such exercise unit(s): %s" % sorted(set(wanted_units) - all_unit_ids))

    # Ŝanĝu __ al **, ĉar nur tio Pandoc ŝajne komprenas.
    for leciono in enhavo['lecionoj']:
        if leciono['gramatiko']:
            leciono['gramatiko']['teksto'] = re.sub('__', '**', leciono['gramatiko']['teksto'])

    printendaj = dict(printendaj, lecionoj=list(lesson_numbers))
    rendered = env.get_template('arangxo.md').render(enhavo=enhavo, printendaj=printendaj)
    print(rendered)
