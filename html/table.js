/* Prediction-pool leaderboard renderer — vanilla JS, no dependencies.
   Reads results.json: { matches: [...], players: { id: {...} } }. */
(function () {
  "use strict";

  var DATA = null;
  var SORT = { key: "score", dir: -1 }; // default: score desc
  var QUEENS_ONLY = false;              // 👑 filter
  var VIEW = "all";                     // all | round | historical | today | next
  var ROUND = null;                     // selected round when VIEW === "round"
  var SCROLL_MODE = "end";              // end (first load) | start (view change) | keep

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
  function buildHead(matches) {
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
    rMatch.appendChild(corner("player", "name", "Player"));
    rMatch.appendChild(corner("pts", "score", "Pts"));
    rMatch.appendChild(corner("exact", "exact", "Exact"));

    matches.forEach(function (m) {
      var th = el("th", "match-col");
      var result = clean(m.result);
      var pending = !result || /^[\s-]*$/.test(result);
      th.innerHTML =
        '<div class="match-card">' +
          '<div class="teams">' + esc(m.team0) + " v " + esc(m.team1) + "</div>" +
          '<div class="score' + (pending ? " pending" : "") + '">' + (pending ? "vs" : esc(result)) + "</div>" +
          '<div class="meta">' + esc(m.time) + (m.round ? " · " + esc(m.round) : "") + "</div>" +
        "</div>";
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
        (p.is_queen ? ' <span class="queen">👑</span>' : "") + "</span>";
      tr.appendChild(el("th", "col-player", nameHtml));
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
    ["col-rank", "col-player", "col-pts", "col-exact"].forEach(function (cls, i) {
      var cells = table.querySelectorAll("." + cls);
      for (var j = 0; j < cells.length; j++) cells[j].style.left = lefts[i] + "px";
    });
  }

  function render() {
    var scroll = document.querySelector(".lb-scroll");
    var prevLeft = scroll ? scroll.scrollLeft : 0;

    var allMatches = DATA.matches || [];
    var matches = visibleMatches(allMatches);
    var all = playersArray(DATA);
    var ranks = computeRanks(QUEENS_ONLY ? all.filter(function (p) { return p.is_queen; }) : all);
    var players = sortPlayers(all.filter(function (p) { return !QUEENS_ONLY || p.is_queen; }));

    var table = el("table", "lb");
    table.appendChild(buildHead(matches));
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

    // first load: jump to latest match; view change: back to start; else keep position
    box.scrollLeft = SCROLL_MODE === "end" ? box.scrollWidth
                   : SCROLL_MODE === "start" ? 0
                   : prevLeft;
    SCROLL_MODE = "keep";
  }

  function noMatchesMsg() {
    if (VIEW === "today") return "No matches scheduled for today.";
    if (VIEW === "next") return "No upcoming matches — every match has been played.";
    if (VIEW === "round") return "No matches in this round.";
    return "No matches to show.";
  }

  var TABS = [
    { id: "all", label: "All" },
    { id: "round", label: "By round" },
    { id: "historical", label: "Historical" },
    { id: "today", label: "Today" },
    { id: "next", label: "Next" }
  ];

  function buildToolbar(allMatches, nVisible, nShown, all) {
    var nQueens = all.filter(function (p) { return p.is_queen; }).length;

    var header = el("div", "lb-header");

    // --- row 1: title, tabs, round picker, queens filter, meta ---
    var bar = el("div", "lb-toolbar");
    bar.appendChild(el("h1", null, "Leaderboard"));

    var tabs = el("div", "lb-tabs");
    var counts = tabCounts(allMatches);
    TABS.forEach(function (t) {
      var b = el("button", "lb-tab" + (VIEW === t.id ? " active" : ""), t.label +
        (t.id !== "all" && t.id !== "round" ? ' <span class="cnt">' + counts[t.id] + "</span>" : ""));
      b.addEventListener("click", function () {
        if (VIEW === t.id) return;
        VIEW = t.id;
        if (VIEW === "round" && !ROUND) ROUND = (roundsOf(allMatches)[0] || null);
        SCROLL_MODE = "start";
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
      sel.addEventListener("change", function () { ROUND = sel.value; SCROLL_MODE = "start"; render(); });
      bar.appendChild(sel);
    }

    if (nQueens) {
      var qbtn = el("button", "lb-filter" + (QUEENS_ONLY ? " active" : ""),
        "👑 Queens only (" + nQueens + ")");
      qbtn.setAttribute("aria-pressed", QUEENS_ONLY ? "true" : "false");
      qbtn.addEventListener("click", function () { QUEENS_ONLY = !QUEENS_ONLY; render(); });
      bar.appendChild(qbtn);
    }

    var who = QUEENS_ONLY ? (nShown + " queens") : (nShown + " players");
    bar.appendChild(el("div", "lb-meta", who + " · " + nVisible + " / " + allMatches.length + " matches"));
    header.appendChild(bar);

    // --- row 2: legend ---
    header.appendChild(el("div", "lb-legend",
      '<span class="chip"><span class="sample s-earned">+1.2</span>points earned</span>' +
      '<span class="chip"><span class="sample s-miss">1-0</span>no points</span>' +
      '<span class="chip"><span class="swatch s-exact"></span>exact scoreline (bonus)</span>'));

    return header;
  }

  function onSort(key) {
    if (SORT.key === key) {
      SORT.dir = -SORT.dir;
    } else {
      SORT.key = key;
      SORT.dir = (key === "name") ? 1 : -1; // names A→Z, numbers high→low
    }
    render();
  }

  function showStatus(msg, spin) {
    var c = document.getElementById("container");
    c.innerHTML = '<div class="lb-status">' + (spin ? '<span class="spinner"></span>' : "") + msg + "</div>";
  }

  function load() {
    showStatus("Loading results…", true);
    fetch("results.json", { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) { DATA = d; render(); })
      .catch(function (e) { showStatus("Couldn't load results.json (" + e.message + ")", false); });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();
