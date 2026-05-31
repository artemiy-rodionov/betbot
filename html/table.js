/* Prediction-pool leaderboard renderer — vanilla JS, no dependencies.
   Reads results.json: { matches: [...], players: { id: {...} } }. */
(function () {
  "use strict";

  var DATA = null;
  var SORT = { key: "score", dir: -1 }; // default: score desc
  var QUEENS_ONLY = false;              // 👑 filter
  var VIEW = "all";                     // all | round | historical | today | next
  var ROUND = null;                     // selected round when VIEW === "round"
  var SCROLL_MODE = "lastPlayed";       // lastPlayed (open/view change) | keep (sort/filter)
  var LAST_MODIFIED = null;             // results.json Last-Modified header
  var REFRESH_TIMER = null;
  var REFRESH_MS = 60000;               // auto-refresh interval

  // ---- helpers ----
  function clean(s) {
    // strip BOM / zero-width chars that appear in the source data
    return (s == null ? "" : String(s)).replace(/[﻿​‎‏]/g, "").trim();
  }
  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function esc(s) {
    return clean(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function fmtPts(v) {
    if (v == null) return "";
    var n = Number(v);
    if (!isFinite(n)) return "";
    return Number.isInteger(n) ? String(n) : n.toFixed(2).replace(/\.?0+$/, "");
  }
  // "Mon, 31 May 2026 14:23:00 GMT" -> "31.05 14:23"
  function fmtDateTime(s) {
    if (!s) return "";
    var d = new Date(s);
    if (isNaN(d.getTime())) return "";
    var p = function (n) { return ("0" + n).slice(-2); };
    return p(d.getDate()) + "." + p(d.getMonth() + 1) + " " + p(d.getHours()) + ":" + p(d.getMinutes());
  }

  // ---- match (column) filtering ----
  // a match is "played" once it has a real scoreline like "2 - 1"
  function isPlayed(m) {
    return /\d+\s*[-–:]\s*\d+/.test(clean(m.result));
  }
  // time strings look like "14.06 22:00" (DD.MM) — compare day+month to today
  function todayDDMM() {
    var d = new Date();
    return ("0" + d.getDate()).slice(-2) + "." + ("0" + (d.getMonth() + 1)).slice(-2);
  }
  function isToday(m) {
    return clean(m.time).slice(0, 5) === todayDDMM();
  }
  function roundsOf(matches) {
    var seen = {}, order = [];
    matches.forEach(function (m) {
      var r = clean(m.round);
      if (r && !seen[r]) { seen[r] = true; order.push(r); }
    });
    return order;
  }
  function tabCounts(matches) {
    var played = matches.filter(isPlayed).length;
    return {
      historical: played,
      next: matches.length - played,
      today: matches.filter(isToday).length
    };
  }
  function visibleMatches(matches) {
    switch (VIEW) {
      case "historical": return matches.filter(isPlayed);
      case "next":       return matches.filter(function (m) { return !isPlayed(m); });
      case "today":      return matches.filter(isToday);
      case "round":      return matches.filter(function (m) { return clean(m.round) === ROUND; });
      default:           return matches.slice();
    }
  }

  function playersArray(data) {
    var out = [];
    var pl = data.players || {};
    for (var id in pl) if (Object.prototype.hasOwnProperty.call(pl, id)) {
      var p = pl[id];
      out.push({
        id: id, // dict key — always unique (p.id may be missing)
        name: clean(p.name),
        score: Number(p.score) || 0,
        exact: Number(p.exact_score) || 0,
        is_queen: !!p.is_queen,
        predByMatch: indexPreds(p.predictions || [])
      });
    }
    return out;
  }
  function indexPreds(preds) {
    var m = {};
    for (var i = 0; i < preds.length; i++) m[preds[i].match_id] = preds[i];
    return m;
  }

  function sortPlayers(arr) {
    var k = SORT.key, d = SORT.dir;
    arr.sort(function (a, b) {
      var av, bv;
      if (k === "name") { av = a.name.toLowerCase(); bv = b.name.toLowerCase();
        if (av < bv) return -1 * d; if (av > bv) return 1 * d; return 0; }
      // rank tracks score desc → ascending rank = higher score first
      if (k === "rank") {
        if (a.score !== b.score) return (b.score - a.score) * d;
        if (a.exact !== b.exact) return (b.exact - a.exact) * d;
        return a.name.toLowerCase() < b.name.toLowerCase() ? -1 : 1;
      }
      av = a[k]; bv = b[k];
      if (av !== bv) return (av < bv ? -1 : 1) * d;
      // tie-breakers: score, then exact, then name
      if (a.score !== b.score) return b.score - a.score;
      if (a.exact !== b.exact) return b.exact - a.exact;
      return a.name.toLowerCase() < b.name.toLowerCase() ? -1 : 1;
    });
    return arr;
  }

  // rank is always by score desc (independent of current sort)
  function computeRanks(players) {
    var byScore = players.slice().sort(function (a, b) {
      return b.score - a.score || b.exact - a.exact;
    });
    var ranks = {}, lastScore = null, lastRank = 0;
    byScore.forEach(function (p, i) {
      var r = (p.score === lastScore) ? lastRank : i + 1;
      ranks[p.id] = r; lastScore = p.score; lastRank = r;
    });
    return ranks;
  }

  // ---- header ----
  function buildHead(matches, players) {
    var thead = el("thead");
    var rMatch = el("tr", "row-match");
    var rSub = el("tr", "row-sub");

    function corner(cls, key, label) {
      var th1 = el("th", "sortable col-" + cls + (SORT.key === key ? " sorted" : ""));
      th1.setAttribute("rowspan", "2");
      var arrow = SORT.key === key ? (SORT.dir < 0 ? "▼" : "▲") : "↕";
      th1.innerHTML = label + ' <span class="arrow">' + arrow + "</span>";
      th1.addEventListener("click", function () { onSort(key); });
      return th1;
    }
    rMatch.appendChild(corner("rank", "rank", "#"));
    rMatch.appendChild(corner("player", "name", "Игрок"));
    rMatch.appendChild(corner("pts", "score", "Очки"));
    rMatch.appendChild(corner("exact", "exact", "Точные"));

    matches.forEach(function (m) {
      var th = el("th", "match-col match-head");
      var result = clean(m.result);
      var pending = !result || /^[\s-]*$/.test(result);
      th.innerHTML =
        '<div class="match-card">' +
          '<div class="teams">' + esc(m.team0) + " – " + esc(m.team1) + "</div>" +
          '<div class="score' + (pending ? " pending" : "") + '">' + (pending ? "—" : esc(result)) + "</div>" +
          '<div class="meta">' + esc(m.time) + (m.round ? " · " + esc(m.round) : "") + "</div>" +
        "</div>";
      th.title = "Прогнозы на матч";
      (function (match) {
        th.addEventListener("click", function () { openMatchPanel(match, players); });
      })(m);
      rMatch.appendChild(th);

      var sub = el("th", "match-col");
      sub.textContent = clean(m.short_label) || (clean(m.team0) + " – " + clean(m.team1));
      rSub.appendChild(sub);
    });

    thead.appendChild(rMatch);
    thead.appendChild(rSub);
    return thead;
  }

  // ---- body ----
  function buildBody(players, matches, ranks) {
    var tbody = el("tbody");
    players.forEach(function (p) {
      var tr = el("tr");
      var r = ranks[p.id];
      var badge = (r <= 3)
        ? '<span class="rank-badge rank-' + r + '">' + r + "</span>"
        : '<span class="rank-badge">' + r + "</span>";
      tr.appendChild(el("th", "col-rank", badge));

      var nameHtml = '<span class="player-name">' + esc(p.name) +
        (p.is_queen ? ' <span class="queen">🎲</span>' : "") + "</span>";
      var nameTh = el("th", "col-player", nameHtml);
      nameTh.title = p.name;
      tr.appendChild(nameTh);
      tr.appendChild(el("td", "col-pts", fmtPts(p.score)));
      tr.appendChild(el("td", "col-exact", p.exact ? String(p.exact) : "·"));

      matches.forEach(function (m) {
        var pr = p.predByMatch[m.id];
        var td;
        if (!pr || pr.result == null) {
          td = el("td", "pred match-col empty");
          td.innerHTML = '<span class="res">–</span>';
        } else {
          var pts = Number(pr.score) || 0;
          var exact = !!pr.is_exact_score;
          var state = exact ? "exact" : (pts > 0 ? "scored" : "miss");
          td = el("td", "pred match-col " + state);
          td.innerHTML =
            '<span class="res">' + esc(pr.result) + "</span>" +
            '<span class="pts">' + (pts > 0 ? "+" + fmtPts(pts) : "") + "</span>";
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    return tbody;
  }

  // assign sticky left offsets to the frozen columns from real widths,
  // so wide values (e.g. "134.24") are never covered by the next column.
  function applyStickyOffsets(table) {
    var headRow = table.querySelector("thead tr.row-match");
    if (!headRow) return;
    var ths = headRow.children; // first 4 are rank/player/pts/exact
    var w = [ths[0].offsetWidth, ths[1].offsetWidth, ths[2].offsetWidth, ths[3].offsetWidth];
    if (!w[0] && !w[1]) return; // layout not measurable (e.g. headless)
    var lefts = [0, w[0], w[0] + w[1], w[0] + w[1] + w[2]];
    var classes = ["col-rank", "col-player", "col-pts", "col-exact"];
    classes.forEach(function (cls, i) {
      var cells = table.querySelectorAll("." + cls);
      for (var j = 0; j < cells.length; j++) cells[j].style.left = lefts[i] + "px";
    });

    // Width of the frozen (horizontally-pinned) block, so scroll-snap can
    // align each match column right after it instead of under it.
    var frozenRight = 0;
    classes.forEach(function (cls, i) {
      var th = headRow.children[i];
      var cs = window.getComputedStyle ? window.getComputedStyle(th) : null;
      if (cs && cs.position === "sticky" && cs.left !== "auto") {
        frozenRight = Math.max(frozenRight, lefts[i] + th.offsetWidth);
      }
    });
    var box = table.parentNode;
    if (box && box.classList && box.classList.contains("lb-scroll")) {
      box.style.scrollPaddingLeft = frozenRight + "px";
    }
  }

  function render() {
    var scroll = document.querySelector(".lb-scroll");
    var prevLeft = scroll ? scroll.scrollLeft : 0;
    var prevTop = scroll ? scroll.scrollTop : 0;

    var allMatches = DATA.matches || [];
    var matches = visibleMatches(allMatches);
    var all = playersArray(DATA);
    var ranks = computeRanks(QUEENS_ONLY ? all.filter(function (p) { return p.is_queen; }) : all);
    var players = sortPlayers(all.filter(function (p) { return !QUEENS_ONLY || p.is_queen; }));

    var table = el("table", "lb");
    table.appendChild(buildHead(matches, all));
    table.appendChild(buildBody(players, matches, ranks));

    var container = document.getElementById("container");
    container.innerHTML = "";
    container.appendChild(buildToolbar(allMatches, matches.length, players.length, all));
    var box = el("div", "lb-scroll");
    box.appendChild(table);
    if (matches.length === 0) {
      box.appendChild(el("div", "lb-empty", noMatchesMsg()));
    }
    container.appendChild(box);

    applyStickyOffsets(table);

    // On open / view change, land on the last played match; otherwise (sort,
    // filter toggle, auto-refresh) keep the current scroll position.
    if (SCROLL_MODE === "keep") { box.scrollLeft = prevLeft; box.scrollTop = prevTop; }
    else scrollToLastPlayed(box, table, matches);
    SCROLL_MODE = "keep";
  }

  // scroll so the most recent played match sits at the right edge of the view
  function scrollToLastPlayed(box, table, matches) {
    var lpi = -1;
    for (var i = 0; i < matches.length; i++) if (isPlayed(matches[i])) lpi = i;
    if (lpi < 0) { box.scrollLeft = 0; return; }      // nothing played yet → start
    var headRow = table.querySelector("thead tr.row-match");
    var cell = headRow ? headRow.children[4 + lpi] : null;   // 4 frozen cols precede matches
    if (!cell) { box.scrollLeft = box.scrollWidth; return; }
    box.scrollLeft = Math.max(0, cell.offsetLeft + cell.offsetWidth - box.clientWidth);
  }

  function noMatchesMsg() {
    if (VIEW === "today") return "Сегодня матчей нет.";
    if (VIEW === "next") return "Будущих матчей нет — все матчи сыграны.";
    if (VIEW === "round") return "В этом туре нет матчей.";
    return "Нет матчей для отображения.";
  }

  // Russian plural: plural(n, "игрок", "игрока", "игроков")
  function plural(n, one, few, many) {
    var d = n % 10, h = n % 100;
    if (d === 1 && h !== 11) return one;
    if (d >= 2 && d <= 4 && (h < 10 || h >= 20)) return few;
    return many;
  }

  var TABS = [
    { id: "all", label: "Все" },
    { id: "round", label: "По турам" },
    { id: "historical", label: "Сыгранные" },
    { id: "today", label: "Сегодня" },
    { id: "next", label: "Будущие" }
  ];

  function buildToolbar(allMatches, nVisible, nShown, all) {
    var nQueens = all.filter(function (p) { return p.is_queen; }).length;

    var header = el("div", "lb-header");

    // --- row 1: title, tabs, round picker, queens filter, meta ---
    var bar = el("div", "lb-toolbar");
    bar.appendChild(el("h1", null, "Турнирная таблица"));

    var tabs = el("div", "lb-tabs");
    var counts = tabCounts(allMatches);
    TABS.forEach(function (t) {
      var b = el("button", "lb-tab" + (VIEW === t.id ? " active" : ""), t.label +
        (t.id !== "all" && t.id !== "round" ? ' <span class="cnt">' + counts[t.id] + "</span>" : ""));
      b.addEventListener("click", function () {
        if (VIEW === t.id) return;
        VIEW = t.id;
        if (VIEW === "round" && !ROUND) ROUND = (roundsOf(allMatches)[0] || null);
        SCROLL_MODE = "lastPlayed";
        render();
      });
      tabs.appendChild(b);
    });
    bar.appendChild(tabs);

    if (VIEW === "round") {
      var sel = el("select", "lb-round");
      roundsOf(allMatches).forEach(function (r) {
        var o = el("option", null, r);
        o.value = r;
        if (r === ROUND) o.selected = true;
        sel.appendChild(o);
      });
      sel.addEventListener("change", function () { ROUND = sel.value; SCROLL_MODE = "lastPlayed"; render(); });
      bar.appendChild(sel);
    }

    if (nQueens) {
      var qbtn = el("button", "lb-filter" + (QUEENS_ONLY ? " active" : ""),
        "🎲 Только лудоманы (" + nQueens + ")");
      qbtn.setAttribute("aria-pressed", QUEENS_ONLY ? "true" : "false");
      qbtn.addEventListener("click", function () { QUEENS_ONLY = !QUEENS_ONLY; render(); });
      bar.appendChild(qbtn);
    }

    // --- info button (ⓘ): stats + legend tucked into a popover to keep the bar light ---
    var who = QUEENS_ONLY
      ? (nShown + " " + plural(nShown, "лудоман", "лудомана", "лудоманов"))
      : (nShown + " " + plural(nShown, "игрок", "игрока", "игроков"));
    var statsText = who + " · " + nVisible + " из " + allMatches.length + " матчей";

    var infoBtn = el("button", "lb-info", "i");
    infoBtn.setAttribute("aria-label", "Информация");
    infoBtn.title = "Информация";
    var updated = fmtDateTime(LAST_MODIFIED);
    var panel = el("div", "lb-infopanel",
      '<div class="info-stats">' + statsText + "</div>" +
      (updated ? '<div class="info-updated">Обновлено: ' + updated + "</div>" : "") +
      '<div class="info-title">Легенда таблицы</div>' +
      '<div class="lb-legend">' +
        '<span class="chip"><span class="sample s-earned">+1.2</span>очки начислены</span>' +
        '<span class="chip"><span class="sample s-miss">1-0</span>без очков</span>' +
        '<span class="chip"><span class="swatch s-exact"></span>точный счёт (бонус)</span>' +
      "</div>");
    infoBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      var open = panel.classList.toggle("open");
      infoBtn.classList.toggle("active", open);
    });
    panel.addEventListener("click", function (e) { e.stopPropagation(); });
    bar.appendChild(infoBtn);

    header.appendChild(bar);
    header.appendChild(panel);
    return header;
  }

  // close the info popover on any outside click (attached once)
  if (!window.__lbInfoBound) {
    window.__lbInfoBound = true;
    document.addEventListener("click", function () {
      var p = document.querySelector(".lb-infopanel.open");
      if (p) p.classList.remove("open");
      var b = document.querySelector(".lb-info.active");
      if (b) b.classList.remove("active");
    });
  }

  function onSort(key) {
    if (SORT.key === key) {
      SORT.dir = -SORT.dir;
    } else {
      SORT.key = key;
      // names A→Z and rank 1→N ascending; points/exact high→low
      SORT.dir = (key === "name" || key === "rank") ? 1 : -1;
    }
    render();
  }

  // tap a match header -> modal with the score + every player's prediction, ranked by points
  function openMatchPanel(match, players) {
    closeMatchPanel();
    var result = clean(match.result);
    var pending = !result || /^[\s-]*$/.test(result);

    var rows = players.map(function (p) {
      var pr = p.predByMatch[match.id];
      var has = pr && pr.result != null;
      return { name: p.name, queen: p.is_queen, has: has,
               pred: has ? pr.result : null,
               pts: has ? (Number(pr.score) || 0) : -1,
               exact: has && !!pr.is_exact_score };
    });
    rows.sort(function (a, b) {
      if (a.has !== b.has) return a.has ? -1 : 1;
      if (b.pts !== a.pts) return b.pts - a.pts;
      return a.name.toLowerCase() < b.name.toLowerCase() ? -1 : 1;
    });

    var list = rows.map(function (r) {
      var cls = r.exact ? "mm-row exact" : (r.has && r.pts > 0 ? "mm-row scored" : "mm-row");
      var pts = r.has ? (r.pts > 0 ? "+" + fmtPts(r.pts) : "0") : "";
      return '<div class="' + cls + '">' +
        '<span class="mm-name">' + esc(r.name) + (r.queen ? " 🎲" : "") + "</span>" +
        '<span class="mm-pred">' + (r.has ? esc(r.pred) : "–") + "</span>" +
        '<span class="mm-pts">' + pts + "</span>" +
      "</div>";
    }).join("");

    var head =
      '<div class="mm-head">' +
        '<div class="mm-teams">' + esc(match.team0) + " – " + esc(match.team1) + "</div>" +
        '<div class="mm-score' + (pending ? " pending" : "") + '">' + (pending ? "—" : esc(result)) + "</div>" +
        '<div class="mm-meta">' + esc(match.time) + (match.round ? " · " + esc(match.round) : "") + "</div>" +
      "</div>";
    var header =
      '<div class="mm-row mm-colhead"><span class="mm-name">Игрок</span>' +
      '<span class="mm-pred">Прогноз</span><span class="mm-pts">Очки</span></div>';

    var overlay = el("div", "lb-modal-overlay");
    var modal = el("div", "lb-modal", head + header + '<div class="mm-list">' + list + "</div>");
    var closeBtn = el("button", "mm-close", "×");
    closeBtn.setAttribute("aria-label", "Закрыть");
    closeBtn.addEventListener("click", closeMatchPanel);
    modal.appendChild(closeBtn);
    overlay.appendChild(modal);
    overlay.addEventListener("click", function (e) { if (e.target === overlay) closeMatchPanel(); });
    document.body.appendChild(overlay);
    document.addEventListener("keydown", escCloseMatch);
  }
  function escCloseMatch(e) { if (e.key === "Escape") closeMatchPanel(); }
  function closeMatchPanel() {
    var o = document.querySelector(".lb-modal-overlay");
    if (o) o.parentNode.removeChild(o);
    document.removeEventListener("keydown", escCloseMatch);
  }

  function showStatus(msg, spin) {
    var c = document.getElementById("container");
    c.innerHTML = '<div class="lb-status">' + (spin ? '<span class="spinner"></span>' : "") + msg + "</div>";
  }

  function load() {
    showStatus("Загрузка результатов…", true);
    fetch("results.json", { cache: "no-store" })
      .then(function (r) {
        if (!r.ok) throw new Error(r.status);
        LAST_MODIFIED = r.headers.get("Last-Modified");
        return r.json();
      })
      .then(function (d) { DATA = d; render(); startAutoRefresh(); })
      .catch(function (e) { showStatus("Не удалось загрузить results.json (" + e.message + ")", false); });
  }

  // re-fetch periodically; re-render (keeping scroll/sort) only when data changed
  function startAutoRefresh() {
    if (REFRESH_TIMER) return;
    REFRESH_TIMER = setInterval(function () {
      fetch("results.json", { cache: "no-store" })
        .then(function (r) {
          if (!r.ok) return null;
          var lm = r.headers.get("Last-Modified");
          return r.json().then(function (d) {
            if (JSON.stringify(d) !== JSON.stringify(DATA)) {
              DATA = d; LAST_MODIFIED = lm || LAST_MODIFIED;
              SCROLL_MODE = "keep"; render();
            }
          });
        })
        .catch(function () {});
    }, REFRESH_MS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();
