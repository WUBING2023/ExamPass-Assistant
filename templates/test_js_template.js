var Q = __QUESTIONS_PLACEHOLDER__;
var LABELS = __LABELS_PLACEHOLDER__;
var __epaImages = {}; // { qid: [dataUrl, ...] } — pasted images per answer field

// ─── Answer normalization (robust to how the JSON was authored) ──────
// tf / choice answers may arrive as int index, boolean, letter ("A"),
// or label string ("正确"/"错误"/"对"/"错"). All are coerced to an
// option index so grading never silently fails on a type mismatch.

function tfAnswerIndex(ans) {
  // option 0 = true_label (正确), option 1 = false_label (错误)
  // boolean: true → 正确(0), false → 错误(1)
  if (typeof ans === 'boolean') return ans ? 0 : 1;
  // number: treat as boolean (0=false→错误(1), non-zero=true→正确(0))
  if (typeof ans === 'number') return ans ? 0 : 1;
  var s = ('' + ans).trim().toLowerCase();
  var truthy = ['t', 'true', '正确', '对', '是', 'yes', 'y', '√', '✓'];
  var falsy  = ['f', 'false', '错误', '错', '否', 'no', 'n', '×', 'x'];
  if (truthy.indexOf(s) !== -1) return 0;
  if (falsy.indexOf(s) !== -1) return 1;
  return ans ? 0 : 1;
}

function choiceAnswerIndex(ans, options) {
  if (typeof ans === 'number') return ans;
  var s = ('' + ans).trim();
  if (/^[A-Za-z]$/.test(s)) return s.toUpperCase().charCodeAt(0) - 65;
  if (/^\d+$/.test(s)) return parseInt(s, 10);
  if (options) {
    for (var i = 0; i < options.length; i++) {
      if (('' + options[i]).trim() === s) return i;
    }
  }
  return parseInt(s, 10);
}

function multiAnswerSet(ans, options) {
  var arr = Array.isArray(ans) ? ans : [ans];
  var set = {};
  for (var i = 0; i < arr.length; i++) {
    set[choiceAnswerIndex(arr[i], options)] = true;
  }
  return set;
}

// Normalize free text for fill-in-the-blank comparison: trim, lowercase,
// drop surrounding whitespace and common punctuation, unify full/half width.
function normText(s) {
  s = ('' + s).trim().toLowerCase();
  s = s.replace(/[\s　]+/g, '');
  s = s.replace(/[.,;:!?。，、；：！？“”"'（）()【】\[\]<>《》]/g, '');
  // full-width ASCII -> half-width
  s = s.replace(/[！-～]/g, function (c) {
    return String.fromCharCode(c.charCodeAt(0) - 0xfee0);
  });
  return s;
}

// How many blanks does a fill question have? Count underscore / ＿ runs.
function fillBlankCount(question) {
  var m = ('' + question).match(/(_{2,}|＿+)/g);
  return m ? m.length : 0;
}

// Coerce a fill `answer` into an array (one entry per blank) of accepted
// answer lists. Handles: string, [synonyms], [[blank1 syns],[blank2 syns]].
function fillBlankAnswers(ans, nBlanks) {
  if (nBlanks < 1) nBlanks = 1;
  if (!Array.isArray(ans)) return padBlanks([[ans]], nBlanks);
  if (ans.length && Array.isArray(ans[0])) return padBlanks(ans, nBlanks);
  // flat array of strings
  if (nBlanks === 1) return [ans];                 // synonyms for one blank
  if (ans.length === nBlanks) {                    // one answer per blank
    return ans.map(function (a) { return [a]; });
  }
  return padBlanks([ans], nBlanks);                // ambiguous -> all on blank 1
}

function padBlanks(arr, n) {
  var out = arr.slice(0, n);
  while (out.length < n) out.push(['']);
  return out;
}

// ─── Build ───────────────────────────────────────────────────────────

function build() {
  var container = document.getElementById('questions-container');
  if (!container) { console.error('ExamPass: questions-container not found'); return; }

  // Stable-sort questions by section order so headings group correctly
  // regardless of input order.
  var order = LABELS.section_order || [];
  Q.forEach(function (q, i) { q._i = i; });
  Q.sort(function (a, b) {
    var oa = order.indexOf(a.type); if (oa === -1) oa = 99;
    var ob = order.indexOf(b.type); if (ob === -1) ob = 99;
    return oa - ob || a._i - b._i;
  });

  var h = '';
  var sec = '';
  var titles = LABELS.section;

  for (var i = 0; i < Q.length; i++) {
    var q = Q[i];
    if (q.type !== sec) {
      sec = q.type;
      if (titles[q.type]) h += '<h3>' + titles[q.type] + '</h3>';
    }

    var qid = 'q' + i;
    h += '<div class="q-card" id="card-' + qid + '">';
    h += '<div class="q-num">' + (i + 1) + '. (' + q.points + ' ' + LABELS.points_suffix + ')</div>';

    if (q.type === 'fill') {
      h += '<div class="q-text">' + renderFill(q, qid) + '</div>';
    } else {
      h += '<div class="q-text">' + q.question + '</div>';
    }

    if (q.type === 'choice') {
      var opts = q.options || [];
      for (var j = 0; j < opts.length; j++) {
        h += '<label class="option" id="opt-' + qid + '-' + j + '" onclick="sel(\'' + qid + '\',' + j + ')">';
        h += '<input type="radio" name="' + qid + '" value="' + j + '">' + String.fromCharCode(65 + j) + '. ' + opts[j] + '</label>';
      }
    } else if (q.type === 'multi') {
      var mopts = q.options || [];
      for (var k = 0; k < mopts.length; k++) {
        h += '<label class="option" id="opt-' + qid + '-' + k + '" onclick="toggle(\'' + qid + '\',' + k + ')">';
        h += '<input type="checkbox" name="' + qid + '" value="' + k + '">' + String.fromCharCode(65 + k) + '. ' + mopts[k] + '</label>';
      }
    } else if (q.type === 'tf') {
      h += '<label class="option" id="opt-' + qid + '-0" onclick="sel(\'' + qid + '\',0)">';
      h += '<input type="radio" name="' + qid + '" value="0">' + LABELS.true_label + '</label>';
      h += '<label class="option" id="opt-' + qid + '-1" onclick="sel(\'' + qid + '\',1)">';
      h += '<input type="radio" name="' + qid + '" value="1">' + LABELS.false_label + '</label>';
    } else if (q.type === 'fill') {
      // inputs already rendered inline inside q-text
    } else if (q.type === 'code') {
      h += '<textarea class="q-textarea q-code" id="text-' + qid + '" placeholder="' + (LABELS.code_placeholder || LABELS.placeholder) + '" rows="8" spellcheck="false"></textarea>';
    } else {
      h += '<textarea class="q-textarea" id="text-' + qid + '" placeholder="' + LABELS.placeholder + '" rows="3"></textarea>';
    }

    h += '<div class="result" id="result-' + qid + '">';
    h += '<span class="badge" id="badge-' + qid + '"></span><span id="correct-' + qid + '"></span>';
    h += '<div class="explanation">' + (q.explanation || '') + '</div>';
    if (q.pitfall) {
      h += '<div class="pitfall">' + LABELS.pitfall_prefix + q.pitfall + '</div>';
    }
    h += '</div></div>';
  }

  container.innerHTML = h;
  __epaPasteListeners(container);

  if (window.MathJax && MathJax.typesetPromise) {
    MathJax.typesetPromise([container]).catch(function (err) {
      console.error('MathJax typeset error:', err);
    });
  }
}

// Render fill question text with inline <input> boxes replacing blanks.
function renderFill(q, qid) {
  var nBlanks = fillBlankCount(q.question);
  var k = 0;
  var html = ('' + q.question).replace(/(_{2,}|＿+)/g, function () {
    var inp = '<input type="text" class="fill-input" id="fill-' + qid + '-' + k + '" autocomplete="off" spellcheck="false">';
    k++;
    return inp;
  });
  if (k === 0) {
    // No markers in text -> append boxes based on answer shape, one per line
    var n = fillBlankAnswers(q.answer, 1).length;
    var ans = q.answer;
    if (Array.isArray(ans)) n = Array.isArray(ans[0]) ? ans.length : (ans.length || 1);
    if (n < 1) n = 1;
    html += '<div>';
    for (var b = 0; b < n; b++) {
      html += '<div class="fill-blank-row">';
      if (n > 1) html += '<span class="fill-tag">' + (b + 1) + '.</span>';
      html += '<input type="text" class="fill-input" id="fill-' + qid + '-' + b + '" autocomplete="off" spellcheck="false">';
      html += '</div>';
    }
    html += '</div>';
  }
  return html;
}

document.addEventListener('DOMContentLoaded', build);
if (document.readyState === 'interactive' || document.readyState === 'complete') {
  build();
}

// ─── Selection handlers ──────────────────────────────────────────────

function sel(qid, idx) {
  var prefix = 'opt-' + qid + '-';
  var all = document.querySelectorAll('[id^="' + prefix + '"]');
  for (var i = 0; i < all.length; i++) all[i].classList.remove('selected');
  var target = document.getElementById('opt-' + qid + '-' + idx);
  if (target) target.classList.add('selected');
  var radio = document.querySelector('input[name="' + qid + '"][value="' + idx + '"]');
  if (radio) radio.checked = true;
}

function toggle(qid, idx) {
  var box = document.querySelector('input[name="' + qid + '"][value="' + idx + '"]');
  var label = document.getElementById('opt-' + qid + '-' + idx);
  if (!box) return;
  box.checked = !box.checked;
  if (label) label.classList.toggle('selected', box.checked);
}

// ─── Grading ─────────────────────────────────────────────────────────

function gradeAll() {
  var score = 0;
  for (var i = 0; i < Q.length; i++) {
    var q = Q[i];
    var qid = 'q' + i;
    var card = document.getElementById('card-' + qid);
    var result = document.getElementById('result-' + qid);
    var badge = document.getElementById('badge-' + qid);
    var correctEl = document.getElementById('correct-' + qid);
    if (!card || !result) continue;

    result.style.display = 'block';

    if (q.type === 'choice' || q.type === 'tf') {
      score += gradeSingle(q, qid, card, badge, correctEl);
    } else if (q.type === 'multi') {
      score += gradeMulti(q, qid, card, badge, correctEl);
    } else if (q.type === 'fill') {
      score += gradeFill(q, qid, card, badge, correctEl);
    } else {
      card.classList.add('correct');
      badge.className = 'badge badge-ref';
      badge.textContent = LABELS.reference_label;
    }
  }

  var sb = document.getElementById('score-box');
  if (sb) {
    sb.style.display = 'block';
    document.getElementById('score-num').textContent = roundScore(score);
    sb.scrollIntoView({ behavior: 'smooth' });
  }

  var opts = document.querySelectorAll('.option');
  for (var a = 0; a < opts.length; a++) opts[a].style.pointerEvents = 'none';
  var tas = document.querySelectorAll('.q-textarea');
  for (var b = 0; b < tas.length; b++) tas[b].disabled = true;
  var fis = document.querySelectorAll('.fill-input');
  for (var c = 0; c < fis.length; c++) fis[c].disabled = true;

  var btn = document.getElementById('grade-btn');
  if (btn) { btn.disabled = true; btn.textContent = LABELS.graded_label; }

  if (window.MathJax && MathJax.typesetPromise) {
    MathJax.typesetPromise().catch(function (err) {
      console.error('MathJax typeset error:', err);
    });
  }
}

function roundScore(s) {
  return Math.round(s * 10) / 10;
}

function gradeSingle(q, qid, card, badge, correctEl) {
  var ansIdx = q.type === 'tf' ? tfAnswerIndex(q.answer) : choiceAnswerIndex(q.answer, q.options);
  var radio = document.querySelector('input[name="' + qid + '"]:checked');
  if (radio && parseInt(radio.value, 10) === ansIdx) {
    card.classList.add('correct');
    badge.className = 'badge badge-ok';
    badge.textContent = LABELS.correct_label;
    correctEl.innerHTML = '';
    var ok = document.getElementById('opt-' + qid + '-' + ansIdx);
    if (ok) ok.classList.add('correct-answer');
    return q.points;
  }
  card.classList.add('wrong');
  badge.className = 'badge badge-no';
  badge.textContent = LABELS.wrong_label;
  var ansText = q.type === 'choice'
    ? String.fromCharCode(65 + ansIdx) + '. ' + (q.options ? q.options[ansIdx] : '')
    : (ansIdx === 0 ? LABELS.true_label : LABELS.false_label);
  correctEl.innerHTML = LABELS.answer_prefix + ansText;
  if (radio) {
    var wrongOpt = document.getElementById('opt-' + qid + '-' + radio.value);
    if (wrongOpt) wrongOpt.classList.add('wrong-answer');
  }
  var corr = document.getElementById('opt-' + qid + '-' + ansIdx);
  if (corr) corr.classList.add('correct-answer');
  return 0;
}

function gradeMulti(q, qid, card, badge, correctEl) {
  var want = multiAnswerSet(q.answer, q.options);
  var wantKeys = Object.keys(want).map(Number);
  var checked = document.querySelectorAll('input[name="' + qid + '"]:checked');
  var picked = [];
  for (var i = 0; i < checked.length; i++) picked.push(parseInt(checked[i].value, 10));

  var anyWrong = false, hitCorrect = 0;
  for (var p = 0; p < picked.length; p++) {
    if (want[picked[p]]) hitCorrect++;
    else anyWrong = true;
  }

  // reveal correct / wrong option markers
  var mopts = q.options || [];
  for (var j = 0; j < mopts.length; j++) {
    var el = document.getElementById('opt-' + qid + '-' + j);
    if (!el) continue;
    if (want[j]) el.classList.add('correct-answer');
    else if (picked.indexOf(j) !== -1) el.classList.add('wrong-answer');
  }

  var earned;
  if (!anyWrong && hitCorrect === wantKeys.length && picked.length === wantKeys.length) {
    earned = q.points;
    card.classList.add('correct');
    badge.className = 'badge badge-ok';
    badge.textContent = LABELS.correct_label;
    correctEl.innerHTML = '';
  } else if (!anyWrong && hitCorrect > 0) {
    // 少选不错选 -> partial credit
    earned = roundScore(q.points * hitCorrect / wantKeys.length);
    card.classList.add('partial');
    badge.className = 'badge badge-partial';
    badge.textContent = LABELS.partial_label;
    correctEl.innerHTML = LABELS.answer_prefix + multiAnswerText(wantKeys, mopts);
  } else {
    earned = 0;
    card.classList.add('wrong');
    badge.className = 'badge badge-no';
    badge.textContent = LABELS.wrong_label;
    correctEl.innerHTML = LABELS.answer_prefix + multiAnswerText(wantKeys, mopts);
  }
  return earned;
}

function multiAnswerText(keys, options) {
  return keys.sort(function (a, b) { return a - b; }).map(function (k) {
    return String.fromCharCode(65 + k) + '. ' + (options ? options[k] : '');
  }).join('  ');
}

// ─── Image paste support ─────────────────────────────────────────────

function __epaPasteListeners(container) {
  var tas = container.querySelectorAll('.q-textarea');
  for (var i = 0; i < tas.length; i++) {
    (function(ta) {
      var qid = ta.id.replace('text-', '');
      ta.addEventListener('paste', function(e) {
        var items = e.clipboardData && e.clipboardData.items;
        if (!items) return;
        for (var j = 0; j < items.length; j++) {
          if (items[j].type.indexOf('image') !== -1) {
            e.preventDefault();
            var file = items[j].getAsFile();
            var reader = new FileReader();
            reader.onload = (function(id, anchor) {
              return function(ev) {
                var dataUrl = ev.target.result;
                if (!__epaImages[id]) __epaImages[id] = [];
                __epaImages[id].push(dataUrl);

                var wrap = document.createElement('div');
                wrap.className = 'paste-img-wrap';
                var img = document.createElement('img');
                img.src = dataUrl;
                var rm = document.createElement('button');
                rm.className = 'paste-img-remove';
                rm.title = '移除图片';
                rm.textContent = '×';
                rm.onclick = (function(url, w) {
                  return function() {
                    var idx = __epaImages[id].indexOf(url);
                    if (idx !== -1) __epaImages[id].splice(idx, 1);
                    w.parentNode.removeChild(w);
                  };
                })(dataUrl, wrap);
                wrap.appendChild(img);
                wrap.appendChild(rm);
                anchor.parentNode.insertBefore(wrap, anchor.nextSibling);
              };
            })(qid, ta);
            reader.readAsDataURL(file);
          }
        }
      });
    })(tas[i]);
  }
}

// ─── Collect all user answers for export ─────────────────────────────

function collectAnswers() {
  var out = [];
  for (var i = 0; i < Q.length; i++) {
    var q = Q[i];
    var qid = 'q' + i;
    var userAnswer = null;

    if (q.type === 'choice' || q.type === 'tf') {
      var radio = document.querySelector('input[name="' + qid + '"]:checked');
      userAnswer = radio ? parseInt(radio.value, 10) : null;
    } else if (q.type === 'multi') {
      var checked = document.querySelectorAll('input[name="' + qid + '"]:checked');
      userAnswer = [];
      for (var c = 0; c < checked.length; c++) {
        userAnswer.push(parseInt(checked[c].value, 10));
      }
    } else if (q.type === 'fill') {
      var nBlanks = fillBlankCount(q.question);
      var blanks = fillBlankAnswers(q.answer, nBlanks);
      userAnswer = [];
      for (var b = 0; b < blanks.length; b++) {
        var inp = document.getElementById('fill-' + qid + '-' + b);
        userAnswer.push(inp ? inp.value : '');
      }
    } else {
      var ta = document.getElementById('text-' + qid);
      userAnswer = ta ? ta.value : '';
    }

    out.push({
      index: i,
      type: q.type,
      question: q.question,
      options: q.options || null,
      correct_answer: q.answer,
      user_answer: userAnswer,
      points: q.points,
      explanation: q.explanation || '',
      kc_id: q.kc_id || '',
      images: (__epaImages[qid] || []).slice()
    });
  }
  return out;
}

// ─── Save answers for AI grading ─────────────────────────────────────

function saveForGrading() {
  var answers = collectAnswers();
  var chapterTitle = (document.title || '章节').replace(/\s+/g, '_');
  var nowStr = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  var filename = chapterTitle + '_answers_' + nowStr + '.json';

  var data = JSON.stringify({
    chapter: document.title || '',
    saved_at: new Date().toISOString(),
    questions: answers
  }, null, 2);

  var blob = new Blob([data], { type: 'application/json' });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  var cmdEl = document.getElementById('epa-grade-cmd-text');
  if (cmdEl) cmdEl.textContent = '/exampass grade "<下载目录>/' + filename + '"';
  var modal = document.getElementById('epa-grade-modal');
  if (modal) modal.classList.add('open');
}

function __epaCloseGradeModal() {
  var modal = document.getElementById('epa-grade-modal');
  if (modal) modal.classList.remove('open');
}

function __epaCopyGradeCmd() {
  var cmdEl = document.getElementById('epa-grade-cmd-text');
  if (!cmdEl) return;
  if (navigator.clipboard) {
    navigator.clipboard.writeText(cmdEl.textContent);
  } else {
    var range = document.createRange();
    range.selectNodeContents(cmdEl);
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    document.execCommand('copy');
    sel.removeAllRanges();
  }
  var btn = document.getElementById('epa-grade-copy-btn');
  if (btn) { btn.textContent = '已复制'; setTimeout(function(){ btn.textContent = '复制命令'; }, 2000); }
}

function gradeFill(q, qid, card, badge, correctEl) {
  var nBlanks = fillBlankCount(q.question);
  var blanks = fillBlankAnswers(q.answer, nBlanks);
  var n = blanks.length;
  var hit = 0;
  var displays = [];

  for (var b = 0; b < n; b++) {
    var inp = document.getElementById('fill-' + qid + '-' + b);
    var accepted = blanks[b] || [''];
    var user = inp ? normText(inp.value) : '';
    var ok = false;
    for (var a = 0; a < accepted.length; a++) {
      if (accepted[a] !== '' && normText(accepted[a]) === user && user !== '') { ok = true; break; }
    }
    if (inp) inp.classList.add(ok ? 'fill-ok' : 'fill-no');
    if (ok) hit++;
    displays.push((n > 1 ? (b + 1) + '. ' : '') + accepted.filter(function (x) { return x !== ''; }).join(' / '));
  }

  var earned = roundScore(q.points * hit / n);
  correctEl.innerHTML = LABELS.answer_prefix + displays.join('   ');

  if (hit === n) {
    card.classList.add('correct');
    badge.className = 'badge badge-ok';
    badge.textContent = LABELS.correct_label;
  } else if (hit > 0) {
    card.classList.add('partial');
    badge.className = 'badge badge-partial';
    badge.textContent = LABELS.partial_label;
  } else {
    card.classList.add('wrong');
    badge.className = 'badge badge-no';
    badge.textContent = LABELS.wrong_label;
  }
  return earned;
}
