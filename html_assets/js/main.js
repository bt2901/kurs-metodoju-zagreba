$(document).ready(function(){
  $('[data-toggle="tooltip"]').tooltip(); 
  $('[data-toggle="popover"]').popover({
    placement: 'bottom',
    trigger: 'hover',
    html: true 
  }); 
  $('.container table').addClass('table'); 
});

// Legacy from the Esperanto-target version of this course: 'cx'/'gx'/...
// digraphs -> ĉĝĵĥŝŭ, then a blunt lowercase-and-compare check. Superseded
// below by IsvInputMethod for the current ISV-target exercises (see
// TASK-01-input-method.md) -- kept only for reference, no longer wired into
// the input[data-solvo] handler.
function esperantigu(s) {

    s = s.replace('cx', 'ĉ')
    s = s.replace('gx', 'ĝ')
    s = s.replace('jx', 'ĵ')
    s = s.replace('hx', 'ĥ')
    s = s.replace('sx', 'ŝ')
    s = s.replace('Cx', 'Ĉ')
    s = s.replace('Gx', 'Ĝ')
    s = s.replace('Jx', 'Ĵ')
    s = s.replace('Hx', 'Ĥ')
    s = s.replace('Sx', 'Ŝ')
    s = s.replace('ux', 'ŭ')
    s = s.replace('Ux', 'Ŭ')

    return s;
}

function normalize(s) {

  s = s.trim();
  s = esperantigu(s);
  s = s.toLowerCase(s);
  return s;
}

function selectNextTabbableOrFocusable(selector){
	var selectables = $(selector);
	var current = $(':focus');
	var nextIndex = 0;
	if(current.length === 1){
		var currentIndex = selectables.index(current);
		if(currentIndex + 1 < selectables.length){
			nextIndex = currentIndex + 1;
		}
	}

	selectables.eq(nextIndex).focus();
}


// ISV exercise fields: let the learner type without an ISV keyboard (see
// TASK-01-input-method.md) via IsvInputMethod's digraph / RFC1345-suffix /
// Alt-key input methods, and check answers with its diacritic-aware
// comparison (a bare letter accepts any diacritic form of it, but a wrong
// diacritic is rejected, unlike a blunt "strip all diacritics" compare).
$('input[data-solvo]').each(function() {
  var input = this;
  IsvInputMethod.attachInputMethod(input, function() {
    return $(input).attr('data-solvo');
  });
  // Small "you typed X, correct spelling is Y" hint, shown only once the
  // field is marked correct and the learner's own spelling wasn't exact.
  $('<span class="isv-solvo-hint text-muted"></span>').insertAfter($('#glyphicon-' + $(input).attr('id')));
});

$('input[data-solvo]').on('input', function() {
  var id = $(this).attr('id');
  var form_group = $('#form-group-' + id);
  var glyphicon = $('#glyphicon-' + id);
  var hint = $(this).parent().find('.isv-solvo-hint');

  var input = $(this).val();
  var solvoField = $(this).attr('data-solvo');
  var matched = IsvInputMethod.firstMatchingAlternative(input, solvoField);

  if (matched !== null) {
    form_group.removeClass('has-error').addClass('has-success');
    glyphicon.removeClass('glyphicon-remove').addClass('glyphicon-ok');
    hint.text(matched === input.trim() ? '' : ' → ' + matched);
		// Set focus on the current
		// to not confuse it during the following step.
		$(this).focus();
		// Jump to the next input.
		selectNextTabbableOrFocusable(':tabbable');
  } else {
    hint.text('');
    form_group.removeClass('has-success').addClass('has-error');
    glyphicon.removeClass('glyphicon-ok').addClass('glyphicon-remove');
  }
});

$('.solvu').click(function() {
  var form_id = $(this).attr('data-form-id');
  var inputs  = $('#form-' + form_id + ' input[data-solvo] ');
  inputs.each(function() {
    var solvo = $(this).attr('data-solvo');
    $(this).val(solvo);
    $(this).trigger('input');
  });
});

$('.forigu').click(function() {
  var form_id = $(this).attr('data-form-id');
  var inputs  = $('#form-' + form_id + ' input[data-solvo] ');
  inputs.each(function() {
    $(this).val('');
    $(this).trigger('input');
  });
});


// Single-correct multiple-choice exercises ("elektu"): unlike the
// data-solvo text inputs above, a radio option has no typed value to
// normalize -- correctness is just "is the checked option the one
// flagged data-korekta=true".
$('input[type=radio][data-korekta]').on('change', function() {
  var group = $(this).closest('.form-group');
  var correct = $(this).attr('data-korekta') === 'true';
  if (correct) {
    group.removeClass('has-error').addClass('has-success');
  } else {
    group.removeClass('has-success').addClass('has-error');
  }
});

$('.solvu-elektu').click(function() {
  var form_id = $(this).attr('data-form-id');
  $('#form-' + form_id + ' .form-group').each(function() {
    $(this).find('input[data-korekta="true"]').prop('checked', true).trigger('change');
  });
});

$('.forigu-elektu').click(function() {
  var form_id = $(this).attr('data-form-id');
  $('#form-' + form_id + ' input[type=radio]').prop('checked', false);
  $('#form-' + form_id + ' .form-group').removeClass('has-success has-error');
});


var currentLangCode = $('#lingvoelektilo').val();

$('#lingvoelektilo').change(function(e) {

	// currentLangCode comes from global.
	var newLanguangeCode = $(this).val()

	var url = window.location.href;
  url = url.replace(
		'/' + currentLangCode + '/',  	
	  '/' + newLanguangeCode + '/'
	);
	window.location.href = url;

	// var previousLangCode = $('#lingvoelektilo').val());
	// var before_change = $(this).data('pre');
	// console.log(before_change);
	//var langCode = console.log($(this).val())
});
