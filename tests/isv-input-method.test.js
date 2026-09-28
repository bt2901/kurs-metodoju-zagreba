// Plain-Node unit tests for the ISV diacritic-aware answer checker (no test
// framework configured in this repo -- see CLAUDE.md). Run with:
//   node tests/isv-input-method.test.js
'use strict';

var assert = require('assert');
var path = require('path');
var IsvInputMethod = require(path.join('..', 'html_assets', 'js', 'isv-input-method.js'));

var passed = 0;

function check(description, actual, expected) {
  assert.strictEqual(actual, expected, description + ' (got ' + JSON.stringify(actual) + ', expected ' + JSON.stringify(expected) + ')');
  passed++;
}

// --- TASK-01 acceptance criteria: bare letters accepted, diacritics optional.
check('bare "zena" accepted for expected "žena"', IsvInputMethod.answersMatch('zena', 'žena'), true);
check('exact "žena" still accepted for expected "žena"', IsvInputMethod.answersMatch('žena', 'žena'), true);
check('unrelated "pivo" rejected for expected "žena"', IsvInputMethod.answersMatch('pivo', 'žena'), false);

// --- The important regression from the plan: a WRONG diacritic must be
// rejected, not smoothed over the way "strip all diacritics" would.
check('bare "sendvic" accepted for expected "sendvič"', IsvInputMethod.answersMatch('sendvic', 'sendvič'), true);
check('wrongly-decorated "šendvič" rejected for expected "sendvič"', IsvInputMethod.answersMatch('šendvič', 'sendvič'), false);
check('bare "svet" accepted for expected "svět"', IsvInputMethod.answersMatch('svet', 'svět'), true);
check('wrong e-variant "svęt" rejected for expected "svět"', IsvInputMethod.answersMatch('svęt', 'svět'), false);
check('wrong e-variant "svět" rejected for expected "svęt"', IsvInputMethod.answersMatch('svět', 'svęt'), false);

// --- Multiple accepted alternatives, and the exact-spelling hint lookup.
check('"vyše | vecej" accepts bare "vyse"', IsvInputMethod.anyAnswerMatches('vyse', 'vyše | vecej'), true);
check('firstMatchingAlternative returns full correct orthography', IsvInputMethod.firstMatchingAlternative('vyse', 'vyše | vecej'), 'vyše');
check('firstMatchingAlternative returns null when nothing matches', IsvInputMethod.firstMatchingAlternative('pivo', 'vyše | vecej'), null);

// --- Cyrillic: same bare-letter-accepts-any-diacritic rule, no cross-script
// transliteration attempted (out of scope per TASK-01-input-method.md).
check('Cyrillic exact match still works', IsvInputMethod.answersMatch('жена', 'жена'), true);
check('Cyrillic й (with breve) accepted by bare и', IsvInputMethod.answersMatch('маи', 'май'), true);

// --- stripDiacritic / isBareLetter helpers, including non-decomposing
// "stroke" letters that Unicode NFD can't handle generically.
check('stripDiacritic("š") == "s"', IsvInputMethod.stripDiacritic('š'), 's');
check('stripDiacritic("đ") == "d" (stroke letter, no NFD decomposition)', IsvInputMethod.stripDiacritic('đ'), 'd');
check('stripDiacritic("ę") == "e"', IsvInputMethod.stripDiacritic('ę'), 'e');
check('isBareLetter("s") is true', IsvInputMethod.isBareLetter('s'), true);
check('isBareLetter("š") is false', IsvInputMethod.isBareLetter('š'), false);

// --- Trigger resolvers (pure functions behind the live keydown handler).
var flags = { digraphX: true, rfc1345Suffixes: true, altKeyLetters: true, contextSensitiveE: true };

// digraphX / altKeyLetters share one table: c e l n s z -> č ě ĺ ń š ž.
check('resolveHachekTrigger("s", ...) -> "š"', IsvInputMethod.resolveHachekTrigger('s', 'vyše', 1, flags), 'š');
check('resolveHachekTrigger("S", ...) -> "Š" (case preserved)', IsvInputMethod.resolveHachekTrigger('S', 'Vyše', 1, flags), 'Š');
check('resolveHachekTrigger("q", ...) -> null (not in table)', IsvInputMethod.resolveHachekTrigger('q', 'vyše', 1, flags), null);
check('resolveHachekToggleBack("š") -> "s"', IsvInputMethod.resolveHachekToggleBack('š'), 's');
check('resolveHachekToggleBack("s") -> null (not decorated)', IsvInputMethod.resolveHachekToggleBack('s'), null);

// Context-sensitive 'e': peeks at the expected answer to pick ě / ę / ė.
check('resolveHachekTrigger("e", "svět", ...) -> "ě"', IsvInputMethod.resolveHachekTrigger('e', 'svět', 2, flags), 'ě');
check('resolveHachekTrigger("e", "svęt", ...) -> "ę"', IsvInputMethod.resolveHachekTrigger('e', 'svęt', 2, flags), 'ę');
check('resolveHachekTrigger("e", "svöt", ...) falls back to "ě" (no e-variant there)', IsvInputMethod.resolveHachekTrigger('e', 'svöt', 2, flags), 'ě');
var noPeek = { digraphX: true, rfc1345Suffixes: true, altKeyLetters: true, contextSensitiveE: false };
check('contextSensitiveE: false always yields "ě"', IsvInputMethod.resolveHachekTrigger('e', 'svęt', 2, noPeek), 'ě');

// RFC1345 suffixes: unambiguous per accent, e< is always ě regardless of peek.
check('resolveRfc1345Trigger("u", ";", ...) -> "ų" (ogonek)', IsvInputMethod.resolveRfc1345Trigger('u', ';', '', 0, flags), 'ų');
check('resolveRfc1345Trigger("e", ";", ...) -> "ę" (ogonek)', IsvInputMethod.resolveRfc1345Trigger('e', ';', '', 0, flags), 'ę');
check('resolveRfc1345Trigger("e", ".", ...) -> "ė" (dot above)', IsvInputMethod.resolveRfc1345Trigger('e', '.', '', 0, flags), 'ė');
check('resolveRfc1345Trigger("e", "<", "svęt", 2, flags) -> "ě" (unambiguous, ignores peek)', IsvInputMethod.resolveRfc1345Trigger('e', '<', 'svęt', 2, flags), 'ě');
check('resolveRfc1345Trigger("d", "/", ...) -> "đ" (stroke)', IsvInputMethod.resolveRfc1345Trigger('d', '/', '', 0, flags), 'đ');
check('resolveRfc1345Trigger("a", "0", ...) -> "å" (ring above)', IsvInputMethod.resolveRfc1345Trigger('a', '0', '', 0, flags), 'å');
check('resolveRfc1345Trigger("x", "<", ...) -> null (not in table)', IsvInputMethod.resolveRfc1345Trigger('x', '<', '', 0, flags), null);

console.log(passed + ' assertions passed.');
