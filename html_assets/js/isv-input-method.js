/*
 * Interslavic (ISV) diacritic input method + diacritic-aware answer checking.
 *
 * Problem: learners typing exercise answers often have no ISV keyboard, so
 * they can't type diacritics (č š ž ě å ę ų ȯ ė ć đ ŕ ľ ...) at all. We don't
 * want to gatekeep them on input -- but we also must not accept a WRONG
 * diacritic as if it were the missing one. Concretely:
 *   - "sendvic" typed for expected "sendvič" -> ACCEPT (bare letter stands in
 *     for any diacritic form of it).
 *   - "šendvič" typed for expected "sendvič" -> REJECT (the learner put a
 *     diacritic on a letter that isn't supposed to have one -- a plain
 *     "strip all diacritics and compare" check would wrongly accept this,
 *     since stripping turns both into "sendvic").
 *   - "svęt" typed for expected "svět" -> REJECT (wrong diacritic FORM on the
 *     right letter -- ę and ě are different letters, not variants of the
 *     same accident).
 *
 * So instead of normalising both sides down to a lossy ASCII key, this module
 * gives the learner three independent, ASCII-friendly ways to type the exact
 * diacritic themselves as they go (so a genuine attempt has to be correct),
 * while a completely undecorated letter is still always accepted as "I don't
 * know this diacritic, but I got the base letter right":
 *
 *   - digraphX        : typing 'x' right after c/e/l/n/s/z toggles the
 *                        "hachek-style" ISV letter (č ě ĺ ń š ž), mirroring
 *                        https://isv.miraheze.org/wiki/MediaWiki:Gadget-im.js
 *   - rfc1345Suffixes : TeX / RFC 1345 style accent suffixes, unambiguous per
 *                       accent type: x<  caron, x;  ogonek, x.  dot above,
 *                       x'  acute, x/  stroke, x0  ring above. See
 *                       http://luki.sdf-eu.org/txt/cs-encodings-faq.html
 *   - altKeyLetters   : Alt+<letter> inserts that letter's hachek-style form
 *                       directly (e.g. Alt+z -> ž), same table as digraphX.
 *
 * The base letter 'e' is ambiguous: ISV has three diacritic forms (ě ę ė).
 * digraphX and altKeyLetters use a generic trigger that doesn't say which one
 * is meant, so when contextSensitiveE is on, the resolver "peeks" at the
 * field's own expected answer and picks whichever of ě/ę/ė actually occurs at
 * that position (falling back to ě). This peeking only ever narrows down
 * WHICH accepted diacritic to type for the learner -- it never lets a wrong
 * base letter or a wrong accent through, so it doesn't weaken the checks
 * above. rfc1345Suffixes sidesteps the ambiguity entirely (e< / e; / e. pick
 * ě / ę / ė explicitly), so it ignores contextSensitiveE.
 *
 * All four behaviours are independently togglable via IsvInputMethod.flags,
 * so any of them can be turned off without touching the others.
 */
(function (root) {
  'use strict';

  // Base letter -> its ISV "hachek-style" diacritic form. Shared by the
  // digraphX and altKeyLetters input methods. Matches the ISV wiki gadget's
  // 'x' table (which groups the caron letters č š ž with the acute letters
  // ĺ ń under one trigger, for learnability, not diacritic purity).
  var HACHEK = { c: 'č', e: 'ě', l: 'ĺ', n: 'ń', s: 'š', z: 'ž' };

  // RFC 1345 / TeX style accent suffixes: trigger character -> per-base-letter
  // replacement. Each suffix is unambiguous, so 'e' does not need peeking
  // here: e< is always ě, e; is always ę, e. is always ė.
  var RFC1345 = {
    '<': { c: 'č', s: 'š', z: 'ž', e: 'ě' }, // caron / hachek
    ';': { e: 'ę', u: 'ų' }, // ogonek
    '.': { e: 'ė', o: 'ȯ' }, // dot above
    "'": { c: 'ć', n: 'ń', r: 'ŕ', l: 'ľ' }, // acute
    '/': { d: 'đ' }, // stroke
    '0': { a: 'å' } // ring above
  };

  var E_VARIANTS = ['ě', 'ę', 'ė'];

  var DEFAULT_FLAGS = {
    digraphX: true,
    rfc1345Suffixes: true,
    altKeyLetters: true,
    contextSensitiveE: true
  };

  // --- Diacritic stripping (used only to test "is this letter undecorated",
  // and to find a decorated letter's base for the accept-a-bare-letter rule
  // above -- never to normalise both sides of a comparison down together).

  // Letters with a stroke (đ, ł) don't have a Unicode canonical decomposition
  // into base + combining mark, unlike caron/acute/ogonek/etc., so they need
  // an explicit map.
  var STROKE_LETTERS = { đ: 'd', Đ: 'D', ł: 'l', Ł: 'L' };

  function stripDiacritic(ch) {
    if (!ch) return ch;
    if (STROKE_LETTERS[ch]) return STROKE_LETTERS[ch];
    return ch.normalize('NFD').replace(/[̀-ͯ]/g, '');
  }

  function isBareLetter(ch) {
    return !!ch && ch === stripDiacritic(ch);
  }

  function matchCase(sampleChar, resultLower) {
    return sampleChar && sampleChar === sampleChar.toUpperCase() && sampleChar !== sampleChar.toLowerCase()
      ? resultLower.toUpperCase()
      : resultLower;
  }

  // --- The actual accept/reject rule for a single character pair.
  //
  // Equal (case-insensitively) -> match. Otherwise, a completely undecorated
  // user letter stands in for any diacritic form of the same base letter --
  // but a DECORATED user letter must match the expected letter exactly, so a
  // wrong diacritic (on the wrong letter, or the wrong accent on the right
  // letter) is rejected rather than silently accepted.
  function charsMatch(userChar, expectedChar) {
    if (!userChar || !expectedChar) return false;
    if (userChar.toLowerCase() === expectedChar.toLowerCase()) return true;
    return (
      isBareLetter(userChar) &&
      stripDiacritic(expectedChar).toLowerCase() === userChar.toLowerCase()
    );
  }

  function answersMatch(userInput, expectedAnswer) {
    var u = (userInput || '').trim();
    var e = (expectedAnswer || '').trim();
    if (u.length !== e.length) return false;
    for (var i = 0; i < u.length; i++) {
      if (!charsMatch(u.charAt(i), e.charAt(i))) return false;
    }
    return true;
  }

  // `expectedField` (a template's data-solvo attribute) may list several
  // acceptable spellings separated by " | ". Returns the first alternative
  // that userInput matches, in its exact correct orthography -- or null.
  function firstMatchingAlternative(userInput, expectedField) {
    var alternatives = (expectedField || '').split(/\s*\|\s*/);
    for (var i = 0; i < alternatives.length; i++) {
      if (answersMatch(userInput, alternatives[i])) return alternatives[i].trim();
    }
    return null;
  }

  function anyAnswerMatches(userInput, expectedField) {
    return firstMatchingAlternative(userInput, expectedField) !== null;
  }

  // --- Disambiguating the generic 'e' trigger against the field's own
  // expected answer(s). `index` is the position the resolved letter will
  // land at in the (post-replacement) input value.
  function pickEVariantAt(expectedField, index, flags) {
    if (flags.contextSensitiveE && index >= 0) {
      var alternatives = (expectedField || '').split(/\s*\|\s*/);
      for (var i = 0; i < alternatives.length; i++) {
        var ch = alternatives[i].trim().charAt(index).toLowerCase();
        if (E_VARIANTS.indexOf(ch) !== -1) return ch;
      }
    }
    return 'ě';
  }

  // --- Pure trigger resolvers: given what's already in the field, the key
  // just pressed, and the flags, decide what (if anything) should replace
  // the previous character. Kept separate from the DOM-attachment code below
  // so they can be unit-tested without a browser/DOM.

  // 'x' pressed right after a base letter (digraphX) or the base letter
  // itself pressed with Alt held (altKeyLetters) -- same underlying table.
  function resolveHachekTrigger(prevChar, expectedField, indexOfPrevChar, flags) {
    if (!prevChar) return null;
    var lower = prevChar.toLowerCase();
    if (!HACHEK[lower]) return null;
    var replacementLower = lower === 'e' ? pickEVariantAt(expectedField, indexOfPrevChar, flags) : HACHEK[lower];
    return matchCase(prevChar, replacementLower);
  }

  // Typing 'x' again after an already-decorated hachek-style letter toggles
  // it back to the base letter (so a mis-toggle, or a genuine literal 'x'
  // after such a letter, can be corrected without deleting).
  function resolveHachekToggleBack(prevChar) {
    if (!prevChar) return null;
    for (var base in HACHEK) {
      if (HACHEK[base] === prevChar.toLowerCase()) {
        return matchCase(prevChar, base);
      }
    }
    return null;
  }

  function resolveRfc1345Trigger(prevChar, triggerChar, expectedField, indexOfPrevChar, flags) {
    if (!prevChar) return null;
    var table = RFC1345[triggerChar];
    if (!table) return null;
    var lower = prevChar.toLowerCase();
    if (triggerChar === '<' && lower === 'e') {
      // e< is unambiguous by construction (always ě); contextSensitiveE does
      // not apply to explicit RFC1345 suffixes.
      return matchCase(prevChar, 'ě');
    }
    if (!table[lower]) return null;
    return matchCase(prevChar, table[lower]);
  }

  // --- DOM attachment: wires the resolvers above to keydown on a real input.

  function attachInputMethod(inputEl, getExpectedField, flags) {
    flags = flags || DEFAULT_FLAGS;

    inputEl.addEventListener('keydown', function (e) {
      if (e.ctrlKey || e.metaKey || e.key.length !== 1) return;

      var pos = inputEl.selectionStart;
      var value = inputEl.value;
      var expectedField = getExpectedField();

      function apply(replacement, consumedChars) {
        e.preventDefault();
        var start = pos - consumedChars;
        inputEl.value = value.slice(0, start) + replacement + value.slice(pos);
        var newPos = start + replacement.length;
        inputEl.setSelectionRange(newPos, newPos);
        // Re-run whatever listens for 'input' (the correctness check).
        inputEl.dispatchEvent(new Event('input', { bubbles: true }));
      }

      if (flags.altKeyLetters && e.altKey && !e.shiftKey) {
        var replacement = resolveHachekTrigger(e.key, expectedField, pos, flags);
        if (replacement) apply(replacement, 0);
        return;
      }

      if (e.altKey || e.metaKey) return;

      var prevChar = value.slice(0, pos).slice(-1);
      if (!prevChar) return;
      var indexOfPrevChar = pos - 1;

      if (flags.digraphX && e.key.toLowerCase() === 'x') {
        var hachek = resolveHachekTrigger(prevChar, expectedField, indexOfPrevChar, flags);
        if (hachek) {
          apply(hachek, 1);
          return;
        }
        var toggledBack = resolveHachekToggleBack(prevChar);
        if (toggledBack) {
          apply(toggledBack, 1);
          return;
        }
      }

      if (flags.rfc1345Suffixes) {
        var accented = resolveRfc1345Trigger(prevChar, e.key, expectedField, indexOfPrevChar, flags);
        if (accented) {
          apply(accented, 1);
          return;
        }
      }
    });
  }

  var IsvInputMethod = {
    flags: DEFAULT_FLAGS,
    stripDiacritic: stripDiacritic,
    isBareLetter: isBareLetter,
    charsMatch: charsMatch,
    answersMatch: answersMatch,
    firstMatchingAlternative: firstMatchingAlternative,
    anyAnswerMatches: anyAnswerMatches,
    pickEVariantAt: pickEVariantAt,
    resolveHachekTrigger: resolveHachekTrigger,
    resolveHachekToggleBack: resolveHachekToggleBack,
    resolveRfc1345Trigger: resolveRfc1345Trigger,
    attachInputMethod: attachInputMethod
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = IsvInputMethod;
  } else {
    root.IsvInputMethod = IsvInputMethod;
  }
})(typeof window !== 'undefined' ? window : this);
