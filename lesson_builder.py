#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build the tagged `teksto` YAML structure for a lesson from a plaintext-ish
Markdown source file.

This replaces the manual workflow that used to live in
maintenance/uczebnik.ipynb: write ISV prose, tokenize it, run it through the
ISV morphological analyzer, split each recognised word into stem + suffix,
and hand-paste the result into enhavo/netradukenda/tekstoj/NN.yml. Here it's
wired up so `generate.py` can regenerate that YAML automatically from the
Markdown source on every build.

Needs the ISV pymorphy2 dictionaries (out_isv_lat/out_isv_etm/out_isv_cyr),
which are NOT part of this repo or the isv_nlp_utils package -- point
ISV_DICT_PATH at the local directory that contains them (e.g. an
ISV_data_gathering checkout).
"""

import os
import re
from collections import Counter

from razdel import tokenize
from isv_nlp_utils import constants

DEFAULT_DICT_PATH = os.environ.get('ISV_DICT_PATH', 'C:\\dev\\pymorphy2-dicts\\')

_TITLE_RE = re.compile(r'^#\s*(.+?)\s*\n+', re.UNICODE)


def get_etm_analyzer(dict_path=None):
    """Load the etymological-alphabet ISV morphological analyzer.

    `dict_path` must contain the compiled pymorphy2 dictionaries
    (out_isv_lat/out_isv_etm/out_isv_cyr). Defaults to ISV_DICT_PATH.
    """
    dict_path = dict_path or DEFAULT_DICT_PATH
    if not os.path.isdir(os.path.join(dict_path, 'out_isv_etm')):
        raise FileNotFoundError(
            "No ISV pymorphy2 dictionaries found under %r (expected an "
            "out_isv_etm/ subdirectory there). These aren't part of this "
            "repo or the isv_nlp_utils package -- point the ISV_DICT_PATH "
            "environment variable at the local directory that has them "
            "(e.g. an ISV_data_gathering checkout)."
            % dict_path
        )
    analyzers = constants.create_analyzers_for_every_alphabet(dict_path)
    return analyzers['etm']


def extract_stem_suffix(word, word_parse, isv_dict, postprocess_freq_thres=0.9):
    """Split a parsed word into (prefix, stem, suffix) using the analyzer's
    paradigm tables. Ported as-is from maintenance/uczebnik.ipynb."""
    paradigm_num = word_parse[4][0][2]
    form_num = word_parse[4][0][3]
    paradigm = isv_dict.build_paradigm_info(paradigm_num)
    stem = isv_dict.build_stem(isv_dict.paradigms[paradigm_num], form_num, word)

    pref = paradigm[form_num][0]
    suff = paradigm[form_num][2]

    fixed_stem = stem
    fixed_suf = suff

    for pref_len in range(1, 5):
        freq = Counter([suf[:pref_len] for (_, _, suf) in paradigm])
        most_common_pref, its_freq = freq.most_common(1)[0]
        if its_freq / len(paradigm) >= postprocess_freq_thres:
            fixed_stem = stem + most_common_pref
            fixed_suf = suff[pref_len:]

    if word.isupper():
        # The paradigm table (most_common_pref/suff above) is always
        # lowercase, so an all-caps word (lesson titles) would otherwise
        # come out with a correctly-cased stem but a lowercase tail.
        fixed_stem = fixed_stem.upper()
        fixed_suf = fixed_suf.upper()

    return pref, fixed_stem, fixed_suf


def _whitespace_after_tokens(text, token_list):
    result = []
    for idx, token in enumerate(token_list):
        if idx < len(token_list) - 1:
            next_start = token_list[idx + 1].start
            result.append(text[token.stop:next_start])
        else:
            result.append('')
    return result


def _parse_token(word, morph, isv_dict):
    """Return a {'lemma': ..., 'morfemes': {stem: 'stem', suffix: tags}}
    dict for a recognised word, or None if the analyzer doesn't know it."""
    if not word.isalpha():
        return None
    parses = morph.parse(word)
    if not parses:
        return None

    word_parse = parses[0]
    _, stem, suffix = extract_stem_suffix(word, word_parse, isv_dict)
    morfemes = {stem: 'stem', suffix: str(word_parse.tag).replace(',', ' ')}
    morfemes.pop('', None)

    return {
        'lemma': word_parse.normal_form.replace('d\u0292', '\u0111'),  # dʒ -> đ
        'morfemes': morfemes,
    }


def tokenize_to_paragraphs(text, morph, isv_dict):
    """Tokenize `text`, analyze every recognisable ISV word, and group the
    result into paragraphs (one per line break in the source), matching the
    shape of enhavo/netradukenda/tekstoj/NN.yml's `titolo`/`paragrafoj`."""
    tokens = list(tokenize(text))
    whitespace = _whitespace_after_tokens(text, tokens)

    paragraphs = [[]]
    for token, token_whitespace in zip(tokens, whitespace):
        parsed = _parse_token(token.text, morph, isv_dict)
        if parsed is not None:
            morfemes = [{k: v} for k, v in parsed['morfemes'].items()]
            paragraphs[-1].append({'token': {'lemma': parsed['lemma'], 'morfemes': morfemes}})
        else:
            paragraphs[-1].append({'token': token.text})

        if '\n' in token_whitespace:
            paragraphs.append([])
        elif token_whitespace:
            # None (-> YAML null), not the whitespace text: html_generiloj's
            # vorto.html and generate.py's word-extraction loop both treat a
            # falsy paragraph entry as "render a single space here".
            paragraphs[-1].append(None)

    return [p for p in paragraphs if p]


def build_teksto(source_md_path, dict_path=None, morph=None):
    """Read a `# Title` + body Markdown source file and return a dict with
    `titolo` and `paragrafoj`, ready to be dumped as a lesson's teksto YAML."""
    with open(source_md_path, encoding='utf-8') as f:
        content = f.read()

    title_match = _TITLE_RE.match(content)
    if not title_match:
        raise ValueError("%s: expected a leading '# Title' line" % source_md_path)

    title_text = title_match.group(1)
    body_text = content[title_match.end():].strip('\n')

    if morph is None:
        morph = get_etm_analyzer(dict_path)
    isv_dict = morph._units[0][0].dict

    titolo_paragraphs = tokenize_to_paragraphs(title_text, morph, isv_dict)
    paragrafoj = tokenize_to_paragraphs(body_text, morph, isv_dict)

    titolo = titolo_paragraphs[0] if titolo_paragraphs else []

    return {'titolo': titolo, 'paragrafoj': paragrafoj}
