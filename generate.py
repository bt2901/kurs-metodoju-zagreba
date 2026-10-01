#!/usr/bin/env python
# -*- coding: utf-8 -*-

import yaml
from yaml.resolver import Resolver
import glob
import re
import os
import argparse
import contextlib
import sys
import html_generiloj
import leo_markdown
import lesson_builder
import exercise_builder

TOTAL_N = 3
import pickle

# A lesson's units (see exercise_builder.py) are its tabs, in order. Lessons
# without a lessonNN_exercises.yml (see legacy_units) get this default set.
DEFAULT_UNITS = [{'id': BUILTIN['id'], 'type': unit_type}
                 for unit_type, BUILTIN in exercise_builder.BUILTIN_UNITS.items()]


def exercise_caption(unit, fasado, number):
    """Tab caption for an exercise unit: its own `title`, else the type's
    label (unnumbered types) or 'Ekzerco N' (numbered ones)."""
    if unit.get('title'):
        return unit['title']
    exercise_type = exercise_builder.EXERCISE_TYPES[unit['type']]
    if not exercise_type['numbered']:
        return fasado[exercise_type['label']]
    key = 'Ekzerco %d' % number
    if key in fasado:
        return fasado[key]
    return fasado['Ekzerco 1'].replace('1', str(number))


def build_tabs(units, fasado):
    """One tab per unit, in order. Each tab carries its page template, URL
    segment, caption, and (for exercises) the unit itself plus a per-lesson
    exercise number used to keep DOM ids unique."""
    tabs = []
    exercise_number = 0
    caption_number = 0
    for unit in units:
        if unit['type'] in exercise_builder.BUILTIN_UNITS:
            builtin = exercise_builder.BUILTIN_UNITS[unit['type']]
            tabs.append({
                'id': builtin['id'],
                'href': builtin['href'],
                'template': builtin['template'],
                'caption': fasado[builtin['fasado_key']],
                'unit': None,
                'ekzerco_index': None,
            })
            continue
        exercise_number += 1
        if exercise_builder.EXERCISE_TYPES[unit['type']]['numbered']:
            caption_number += 1
        tabs.append({
            'id': unit['id'],
            'href': unit['id'] + '/',
            'template': 'ex_' + unit['type'].replace('-', '_'),
            'caption': exercise_caption(unit, fasado, caption_number),
            'unit': unit,
            'ekzerco_index': exercise_number,
        })
    return tabs


def legacy_units(language, i_padded):
    """Units for a lesson that has no lessonNN_exercises.yml: the built-in
    tabs plus the old per-type, per-language exercise files (already in
    compiled form). Kept only until every lesson has an exercises file."""
    def load_yml(path):
        return yaml.load(open(path, encoding="utf8"), yaml.Loader)

    return DEFAULT_UNITS + [
        {'id': 'ekzerco1', 'type': 'translate', 'title': None,
         'items': load_yml('enhavo/tradukenda/' + language + '/ekzercoj/traduku/' + i_padded + '.yml')},
        {'id': 'ekzerco2', 'type': 'cloze', 'title': None,
         'items': load_yml('enhavo/netradukenda/ekzercoj/kompletigu-la-frazojn/' + i_padded + '.yml')},
        {'id': 'ekzerco3', 'type': 'translate-answer', 'title': None,
         'items': load_yml('enhavo/tradukenda/' + language + '/ekzercoj/traduku-kaj-respondu/' + i_padded + '.yml')},
    ]


def join_morphemes(yaml_str):
    return ''.join([list(m.keys())[0] for m in yaml_str])

def iskati(stroka, jezyk, sheet):
    result = sheet[sheet[jezyk] == stroka]
    return result.index.values.tolist()

# remove resolver entries for On/Off/Yes/No
# https://stackoverflow.com/a/36470466/52023
for ch in "OoYyNn":
    if len(Resolver.yaml_implicit_resolvers[ch]) == 1:
        del Resolver.yaml_implicit_resolvers[ch]
    else:
        Resolver.yaml_implicit_resolvers[ch] = [x for x in
                                                Resolver.yaml_implicit_resolvers[ch] if
                                                x[0] != 'tag:yaml.org,2002:bool']


def transpose_headlines(markdown, level):
    prefix = ''
    for i in range(level):
        prefix += '#'
    markdown = re.sub(r'^#', '#' + prefix, markdown)
    markdown = re.sub(r'\n#', '\n#' + prefix, markdown)
    return markdown


def get_markdown_headlines(s):
    headlines = []
    for match in re.finditer(r'(^|\n)# (.+)\n', s):
        headlines.append(match.group(2).strip())

    return headlines


def load(language, gramatiko_transpose_headlines=2):
    enhavo = {'lingvo': language, 'vortaro': {}}

    from isv_nlp_utils.slovnik import get_slovnik, download_slovnik, prepare_slovnik
    # get_slovnik() chats on stdout, which is the document in md mode.
    with contextlib.redirect_stdout(sys.stderr):
        slovnik = get_slovnik()['words']
    prepare_slovnik(slovnik)

    paths = glob.glob('enhavo/tradukenda/' + language + '/vortaro/*.yml')
    # Provo solvi
    # https://github.com/Esperanto/kurso-zagreba-metodo/issues/36
    # sed kauzas aliajn problemojn.
    # paths.append('enhavo/tradukenda/en/vortaro/vorto.yml')
    # print(paths)

    # for path in paths:
    if False:
        dirs, filename = os.path.split(path)
        root, extension = os.path.splitext(filename)
        vortspeco = root.replace('_', ' ')
        vortlisto = yaml.load(open(path, encoding="utf8").read(), yaml.Loader)
        for esperante in vortlisto:
            fontlingve = vortlisto[esperante]
            vortlisto[esperante] = {
                'tradukajxo': fontlingve,
                'vortspeco': vortspeco
            }
        enhavo['vortaro'].update(vortlisto)

    enhavo['finajxoj'] = yaml.load(open('enhavo/netradukenda/radikaj_finajxoj.yml', encoding="utf8").read(), yaml.Loader)

    enhavo['ordoj'] = {}
    enhavo['ordoj']['cifero'] = yaml.load(open('enhavo/netradukenda/ordoj/cifero.yml', encoding="utf8"), yaml.Loader)
    enhavo['ordoj']['monato'] = yaml.load(open('enhavo/netradukenda/ordoj/monato.yml', encoding="utf8"), yaml.Loader)
    enhavo['ordoj']['sezono'] = yaml.load(open('enhavo/netradukenda/ordoj/sezono.yml', encoding="utf8"), yaml.Loader)
    enhavo['ordoj']['tago_en_la_semajno'] = yaml.load(open('enhavo/netradukenda/ordoj/tago_en_la_semajno.yml', encoding="utf8"),
                                                      yaml.Loader)

    enhavo['fasado'] = {}
    paths = glob.glob('enhavo/tradukenda/' + language + '/fasado/*.yml')
    for path in paths:
        tradukajxoj = yaml.load(open(path, encoding="utf8").read(), yaml.Loader)
        enhavo['fasado'].update(tradukajxoj)

    path = 'enhavo/tradukenda/' + language + '/enkonduko.md'
    enkonduko = open(path, encoding="utf8").read()
    # enkonduko = transpose_headlines(enkonduko, 1)
    enhavo['enkonduko'] = enkonduko

    path = 'enhavo/tradukenda/' + language + '/post.md'
    enhavo['post'] = open(path, encoding="utf8").read()
    enhavo['post'] = transpose_headlines(enhavo['post'], 2)

    lecionoj = []
    vortoj = {}
    etm_morph = None

    for i in range(1, TOTAL_N):
        leciono = {
            'teksto': None,
            'gramatiko': None,
        }
        i_padded = str(i).zfill(2)

        leciono['indekso'] = {
            'cifre': i,
            'cxene': i_padded
        }

        path = 'enhavo/netradukenda/tekstoj/' + i_padded + '.yml'

        # If a plaintext-ish Markdown source exists for this lesson, it's the
        # source of truth: regenerate the tagged YAML from it (see
        # lesson_builder.py, which replaces the manual tokenize/analyze/paste
        # workflow that used to live in maintenance/uczebnik.ipynb). The YAML
        # file stays as the intermediate build artifact that the rest of the
        # pipeline (and any human inspecting a lesson) reads.
        source_md_path = 'enhavo/netradukenda/tekstoj/lesson' + i_padded + '_source.md'
        if os.path.exists(source_md_path):
            if etm_morph is None:
                etm_morph = lesson_builder.get_etm_analyzer()
            teksto = lesson_builder.build_teksto(source_md_path, morph=etm_morph)
            with open(path, 'w', encoding='utf8') as f:
                yaml.dump(teksto, f, allow_unicode=True, default_flow_style=False)

        leciono['teksto'] = yaml.load(open(path, encoding="utf8").read(), yaml.Loader)
        with open(r"C:\dev\kurso-zagreba-metodo\leciono.pkl", "wb") as f:
            pickle.dump(leciono, f)

        # Create a string of the lesson titles.
        titolo_string = ''
        for radikoj in leciono['teksto']['titolo']:
            if type(radikoj) is dict:
                radikoj = radikoj['token']
                if 'morfemes' in radikoj:
                    titolo_string += join_morphemes(radikoj['morfemes'])
                else:
                    titolo_string += radikoj
            else:
                titolo_string += " "

        leciono['teksto']['titolo_string'] = titolo_string

        leciono['vortoj'] = {}
        leciono['vortoj']['teksto'] = []
        leciono['vortoj']['pliaj'] = []

        path = 'enhavo/netradukenda/vortoj/' + i_padded + '.yml'
        leciono['vortoj']['pliaj'] = yaml.load(open(path, encoding="utf8").read(), yaml.Loader)

        for paragrafo in leciono['teksto']['paragrafoj']:
            for vorto in paragrafo:
                if not vorto:
                    continue
                vorto = vorto['token']
                if type(vorto) is dict:
                    radiko = vorto['lemma'].replace("dʒ", "đ")
                    if not radiko.lower() in vortoj:
                        leciono['vortoj']['teksto'].append(radiko)
                        vortoj[radiko.lower()] = True

        path = 'enhavo/tradukenda/' + language + '/gramatiko/' + i_padded + '.md'

        gramatiko_teksto = open(path, encoding="utf8").read()
        gramatiko_titoloj = get_markdown_headlines(gramatiko_teksto)
        gramatiko_teksto = transpose_headlines(gramatiko_teksto, gramatiko_transpose_headlines)

        gramatiko = {
            'teksto': gramatiko_teksto,
            'titoloj': gramatiko_titoloj,
        }
        leciono['gramatiko'] = gramatiko

        # If a lessonNN_exercises.yml exists, its unit list is the lesson's
        # tab list and the single source of all its exercises (see
        # exercise_builder.py); other lessons fall back to the old layout.
        exercises_path = 'enhavo/netradukenda/tekstoj/lesson' + i_padded + '_exercises.yml'
        if os.path.exists(exercises_path):
            if etm_morph is None:
                etm_morph = lesson_builder.get_etm_analyzer()
            glosser = exercise_builder.Glosser(slovnik, lambda: etm_morph)
            units = exercise_builder.build_units(exercises_path, language, glosser)
        else:
            units = legacy_units(language, i_padded)

        leciono['units'] = units
        leciono['tabs'] = build_tabs(units, enhavo['fasado'])


        lecionoj.append(leciono)

    enhavo['lecionoj'] = lecionoj
    all_words = set()
    for leciono in enhavo['lecionoj']:
        all_words |= set(leciono['vortoj']['teksto'])

    for isv_lemma in all_words:
        found_indices = iskati(isv_lemma, "isv", slovnik)
        if len(found_indices):
            idx = found_indices[0]
            translated_word = slovnik.loc[idx][language]
            pos = slovnik.loc[idx]['partOfSpeech']
            enhavo['vortaro'][isv_lemma] = {'tradukajxo': translated_word, 'vortspeco': pos}
        else:
            print(isv_lemma, file=sys.stderr)
    with open("enhavo.pkl", "wb") as f:
        pickle.dump(enhavo, f)

    return enhavo


def get_cmdline_arguments():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "-l",
        "--lingvo",
        help="Kreu eligon por tiu lingvo.",
        type=str,
        required=True
    )
    ap.add_argument(
        "-ef",
        "--eligformo",
        help="La eligoformo",
        type=str,
        choices=['html', 'md'],
        default='html'
    )
    ap.add_argument(
        "-pp",
        "--printendaj-partoj",
        help="Printendaj partoj (nur por md)",
        type=str,
        choices=['teksto', 'vortoj', 'gramatiko', 'ekzercoj', 'solvoj'],
        default=['teksto', 'vortoj', 'gramatiko', 'ekzercoj', 'solvoj'],
        nargs='*'
    )
    ap.add_argument(
        "-pl",
        "--printendaj-lecionoj",
        help="Printendaj lecionoj (numeroj; norme ĉiuj) (nur por md)",
        type=int,
        nargs='*'
    )
    ap.add_argument(
        "-pu",
        "--printendaj-unuoj",
        help="Printendaj ekzercaj unuoj laŭ identigilo (norme ĉiuj) (nur por md)",
        type=str,
        nargs='*'
    )
    ap.add_argument(
        "-vp",
        "--vojprefikso",
        help="La vojprefikso por ĉiuj ligiloj en la eligo. Norme: /[lingvokodo]/",
        type=str
    )
    args = ap.parse_args()

    return args


def main():
    args = get_cmdline_arguments()
    lingvoj = yaml.load(open('agordoj/lingvoj.yml', encoding="utf8").read(), yaml.Loader)
    if args.eligformo == 'html':
        # if args.lingvo not in lingvoj.keys():
        #    sys.exit("'" + args.lingvo + "' ne estas havebla lingvokodo.")
        enhavo = load(args.lingvo)
        enhavo['lingvoj'] = lingvoj
        enhavo['tekstodirekto'] = lingvoj[args.lingvo].get('tekstodirekto', 'ltr')
        html_generiloj.generi.generate_html(args.lingvo, enhavo, args)
    if args.eligformo == 'md':
        enhavo = load(args.lingvo, 3)
        enhavo['lingvoj'] = lingvoj
        enhavo['tekstodirekto'] = lingvoj[args.lingvo].get('tekstodirekto', 'ltr')
        leo_markdown.package.kreu_md(enhavo, printendaj={'partoj': args.printendaj_partoj,
                                                         'lecionoj': args.printendaj_lecionoj,
                                                         'unuoj': args.printendaj_unuoj})


main()
