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
import sys
from collections import Counter

from razdel import tokenize
from isv_nlp_utils import constants

import glosses
import wordsense

DEFAULT_DICT_PATH = os.environ.get('ISV_DICT_PATH', 'C:\\dev\\ISV_pymorphy2_dicts\\pymorphy2-dicts\\')

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
        # Move the shared first letter(s) of the endings into the stem -- but only
        # if this form's ending really starts with them: for a fleeting-e form
        # like `otėc` (ending `ėc`, while most endings are `ca ci cu ...`) cutting
        # a character off the ending anyway turns `ot|ėc` into `otc|c`.
        if its_freq / len(paradigm) >= postprocess_freq_thres and suff.startswith(most_common_pref):
            fixed_stem = stem + most_common_pref
            fixed_suf = suff[pref_len:]

    if word.isupper():
        # The paradigm table (most_common_pref/suff above) is always
        # lowercase, so an all-caps word (lesson titles) would otherwise
        # come out with a correctly-cased stem but a lowercase tail.
        fixed_stem = fixed_stem.upper()
        fixed_suf = fixed_suf.upper()

    # The parts are joined back into the displayed word, so they must spell it
    # as the author wrote it. They can differ when the dictionary's ending is
    # spelled another way (`sědžų` vs its ending `ʒų`) or when a guessed parse
    # for a form the dictionary lacks is wrong. Keep the analyzer's stem if the
    # word really starts with it and take the ending from the word itself;
    # otherwise show the word unsplit rather than a different spelling.
    if (pref + fixed_stem + fixed_suf).lower() != word.lower():
        if not pref and word.lower().startswith(fixed_stem.lower()):
            return pref, word[:len(fixed_stem)], word[len(fixed_stem):]
        print("[split] %r: the analyzer's split %s|%s doesn't spell the word; showing it unsplit"
              % (word, fixed_stem, fixed_suf), file=sys.stderr)
        return '', word, ''

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

not_found = {'člověka', 'ljubogo', 'tvojego', 'sebę', 'nekulturnogo', 'den', 'necivilizovanogo', 'sendvič', 'vědati', 'kulturų', 'črnogo', 'ogo', 'jedno', 'imati', 'kolikogo', 'myzljiti', 'togo', 'čašų', 'zemjų', 'vladimir', 'boų', 'pauzų', 'tutogo', 'dobrogo', 'imamų', 'sidti', 'veś', 'jedinogo', 'kostovati', 'čego', 'kakogo', 'ziťje', 'lavkų', 'hlopca', 'tovariša', 'bělogo', 'siděti', 'direktora', 'nikogo', 'samogo', 'začego', 'pokų', 'potrěbnogo', 'kapučinogo', 'nikolų', 'žestokogo', 'borodinų', 'slabogo', 'kulturnogo', 'otca'}

not_found = {'kostovati', 'ziťje', 'kapučiny', 'nekulturny', 'nikola', 'sendvič', 'imama', 'borodina', 'vědati', 'y', 'den', 'necivilizovany', 'veś', 'toj', 'imati', 'vladimir', 'hlopec', 'otec', 'kako'}

def _apply_override(result, word, key, entry, where):
    """Fold a glosses.py entry into a parsed token: replace the lemma and/or
    the morpheme split, and remember the entry's key (`gloss_key`) so the
    build can attach the per-language gloss and respect `scope`."""
    if entry.get('lemma'):
        result['lemma'] = entry['lemma']
    if 'morphemes' in entry:
        result['morfemes'] = glosses.apply_morphemes(word, entry['morphemes'], where)
    result['gloss_key'] = key
    return result


def _parse_token(word, morph, isv_dict, grammemes=None, where='', ambiguities=None, overrides=None):
    """Return a {'lemma': ..., 'morfemes': [{piece: tags}, ...]} dict (plus
    'gloss_key' if a glosses.py override applies) for a recognised word, or
    None if the analyzer doesn't know it and there is no override for it.

    `grammemes` (from a `{...}` annotation in the source) picks which of the
    word's parses to use; without it the first parse is used and
    lemma/part-of-speech ambiguity is recorded in `ambiguities`."""
    if not word.isalpha():
        return None
    overrides = overrides or {}
    early_key, early = glosses.lookup(overrides, word)
    parses = morph.parse(word)
    if not parses:
        if early is None:
            return None
        return _apply_override({'lemma': word.lower(), 'morfemes': [{word: 'stem'}]},
                               word, early_key, early, where)

    # an override that fixes the lemma or the split settles any ambiguity
    settled = early is not None and ('lemma' in early or 'morphemes' in early)
    word_parse = wordsense.choose_parse(word, parses, grammemes, where,
                                        None if settled else ambiguities)
    _, stem, suffix = extract_stem_suffix(word, word_parse, isv_dict)
    morfemes = {stem: 'stem', suffix: str(word_parse.tag).replace(',', ' ')}
    morfemes.pop('', None)
    lemma = wordsense.lemma_of(word, word_parse, morph)
    if lemma in not_found:
        print(word_parse, file=sys.stderr)

    result = {
        'lemma': lemma,
        'morfemes': [{k: v} for k, v in morfemes.items()],
    }
    key, entry = glosses.lookup(overrides, word, lemma)
    if entry is not None:
        _apply_override(result, word, key, entry, where)
    return result


def tokenize_to_paragraphs(text, morph, isv_dict, where='', ambiguities=None, overrides=None):
    """Tokenize `text`, analyze every recognisable ISV word, and group the
    result into paragraphs (one per line break in the source), matching the
    shape of enhavo/netradukenda/tekstoj/NN.yml's `titolo`/`paragrafoj`.

    `{grammemes}` annotations after words (see wordsense.py) are stripped
    first and steer which parse each annotated word gets."""
    text, notes = wordsense.strip_annotations(text, where)
    tokens = list(tokenize(text))
    whitespace = _whitespace_after_tokens(text, tokens)

    paragraphs = [[]]
    for token, token_whitespace in zip(tokens, whitespace):
        grammemes = notes.pop(token.stop, None)
        parsed = _parse_token(token.text, morph, isv_dict, grammemes, where, ambiguities, overrides)
        if grammemes is not None and parsed is None:
            raise ValueError("%s: {%s} follows %r, which isn't a word the analyzer knows"
                             % (where, ' '.join(sorted(grammemes)), token.text))
        if parsed is not None:
            paragraphs[-1].append({'token': parsed})
        else:
            paragraphs[-1].append({'token': token.text})

        if '\n' in token_whitespace:
            paragraphs.append([])
        elif token_whitespace:
            # None (-> YAML null), not the whitespace text: html_generiloj's
            # vorto.html and generate.py's word-extraction loop both treat a
            # falsy paragraph entry as "render a single space here".
            paragraphs[-1].append(None)

    wordsense.check_all_attached(notes, where)
    return [p for p in paragraphs if p]


def build_teksto(source_md_path, dict_path=None, morph=None, overrides=None):
    """Read a `# Title` + body Markdown source file and return a dict with
    `titolo` and `paragrafoj`, ready to be dumped as a lesson's teksto YAML.
    `overrides` are the lesson's word overrides (see glosses.py)."""
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

    ambiguities = wordsense.Ambiguities()
    titolo_paragraphs = tokenize_to_paragraphs(title_text, morph, isv_dict, source_md_path, ambiguities, overrides)
    paragrafoj = tokenize_to_paragraphs(body_text, morph, isv_dict, source_md_path, ambiguities, overrides)
    ambiguities.print(source_md_path)

    titolo = titolo_paragraphs[0] if titolo_paragraphs else []

    return {'titolo': titolo, 'paragrafoj': paragrafoj}
