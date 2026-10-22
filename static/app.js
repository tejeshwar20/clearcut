const $ = (id) => document.getElementById(id);
let report = null;
let busy = false;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function showError(message) {
  $('error').textContent = message;
  $('error').hidden = !message;
}

function invalidate() {
  report = null;
  $('written-review').hidden = true;
  $('review-text').textContent = '';
  $('report-state').textContent = '';
}

function render(data) {
  $('review-text').replaceChildren();
  const text = data.reader_review;
  text.split(/\n\s*\n/).filter(Boolean).forEach((block, index) => {
    const paragraph = element('p');
    const opening = index === 0 && block.match(/^(.+?[.!?])(?:\s+|$)/);
    if (opening) {
      paragraph.append(element('strong', '', opening[1]), document.createTextNode(' ' + block.slice(opening[0].length)));
    } else {
      paragraph.textContent = block;
    }
    $('review-text').append(paragraph);
  });
  $('written-review').hidden = !text;
  const rated = typeof data.overall_score === 'number' && Number.isFinite(data.overall_score);
  $('overall-score').textContent = rated ? data.overall_score.toFixed(1) : 'Not rated';
  $('score-scale').hidden = !rated;
  $('overall-rating').title = data.score_basis || 'Sentiment-based estimate from the supplied opinions.';
}

function presentReport(data, collection) {
  if (data.reader_output?.version !== 1 || data.reader_output?.checked !== true || typeof data.reader_review !== 'string') {
    throw new Error('This server returned an unchecked review. Reload the updated app and refresh the report.');
  }
  report = data;
  $('report-heading').textContent = data.reader_title || collection;
  $('report-state').textContent = '';
  render(data);
}

async function getJSON(url, options) {
  const response = await fetch(url, {signal: AbortSignal.timeout(90000), ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed.');
  return data;
}

$('reviews').addEventListener('input', invalidate);

$('review-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (busy) return;
  showError('');
  const reviews = $('reviews').value.split(/\n\s*\n/).map((text) => text.trim()).filter(Boolean);
  if (!reviews.length) { showError('Paste a review first.'); return; }
  invalidate();
  busy = true;
  const controls = [...document.querySelectorAll('input,textarea,button')];
  const wasDisabled = controls.map((control) => control.disabled);
  controls.forEach((control) => { control.disabled = true; });
  $('analyze').textContent = 'Preparing review...';
  $('report-state').textContent = 'Reading your review...';
  document.querySelector('.report-panel').setAttribute('aria-busy', 'true');
  try {
    const data = await getJSON('/api/analyze', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({reviews})});
    presentReport(data, 'Your review');
  } catch (error) { $('report-state').textContent = ''; showError(error.message); }
  finally {
    controls.forEach((control, index) => { control.disabled = wasDisabled[index]; });
    $('analyze').replaceChildren(document.createTextNode('Generate spoiler-free review '), element('span', '', '\u2192'));
    document.querySelector('.report-panel').setAttribute('aria-busy', 'false');
    busy = false;
  }
});
