import json

STYLE = """
  @font-face { font-family: 'Oswald'; font-weight: 500; font-style: normal; font-display: swap; src: url('assets/fonts/oswald-500.woff2') format('woff2'); }
  @font-face { font-family: 'Oswald'; font-weight: 700; font-style: normal; font-display: swap; src: url('assets/fonts/oswald-700.woff2') format('woff2'); }
  @font-face { font-family: 'IBM Plex Sans'; font-weight: 400; font-style: normal; font-display: swap; src: url('assets/fonts/plexsans-400.woff2') format('woff2'); }
  @font-face { font-family: 'IBM Plex Sans'; font-weight: 600; font-style: normal; font-display: swap; src: url('assets/fonts/plexsans-600.woff2') format('woff2'); }
  @font-face { font-family: 'IBM Plex Mono'; font-weight: 400; font-style: normal; font-display: swap; src: url('assets/fonts/plexmono-400.woff2') format('woff2'); }
  @font-face { font-family: 'IBM Plex Mono'; font-weight: 600; font-style: normal; font-display: swap; src: url('assets/fonts/plexmono-600.woff2') format('woff2'); }

  :root {
    --bg: #d8d2c4; --surface: #f4f0e6; --surface-raised: #14204d;
    --ink: #17203b; --ink-muted: #5b5f72; --ink-on-raised: #f4f0e6; --ink-on-raised-muted: #aab0c8;
    --accent: #c8a24a; --border: #cfc7b2; --border-on-raised: rgba(244,240,230,0.16);
    --status-good: #2f7a4f; --status-warn: #c07d18; --status-crit: #b32036;
    --status-good-bg: rgba(47,122,79,0.12); --status-warn-bg: rgba(192,125,24,0.12); --status-crit-bg: rgba(179,32,54,0.12);
    --eyebrow-accent: var(--surface-raised);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0b0e18; --surface: #131a2c; --surface-raised: #1c2747;
      --ink: #ece7d8; --ink-muted: #9098b0; --ink-on-raised: #ece7d8; --ink-on-raised-muted: #9098b0;
      --accent: #d9b568; --border: #2a3350; --border-on-raised: rgba(236,231,216,0.14);
      --status-good: #3f9468; --status-warn: #c17f1d; --status-crit: #e0405f;
      --status-good-bg: rgba(63,148,104,0.16); --status-warn-bg: rgba(193,127,29,0.16); --status-crit-bg: rgba(224,64,94,0.16);
      --eyebrow-accent: var(--accent);
    }
  }
  :root[data-theme="dark"] {
    --bg: #0b0e18; --surface: #131a2c; --surface-raised: #1c2747;
    --ink: #ece7d8; --ink-muted: #9098b0; --ink-on-raised: #ece7d8; --ink-on-raised-muted: #9098b0;
    --accent: #d9b568; --border: #2a3350; --border-on-raised: rgba(236,231,216,0.14);
    --status-good: #3f9468; --status-warn: #c17f1d; --status-crit: #e0405f;
    --status-good-bg: rgba(63,148,104,0.16); --status-warn-bg: rgba(193,127,29,0.16); --status-crit-bg: rgba(224,64,94,0.16);
    --eyebrow-accent: var(--accent);
  }
  :root[data-theme="light"] {
    --bg: #d8d2c4; --surface: #f4f0e6; --surface-raised: #14204d;
    --ink: #17203b; --ink-muted: #5b5f72; --ink-on-raised: #f4f0e6; --ink-on-raised-muted: #aab0c8;
    --accent: #c8a24a; --border: #cfc7b2; --border-on-raised: rgba(244,240,230,0.16);
    --status-good: #2f7a4f; --status-warn: #c07d18; --status-crit: #b32036;
    --status-good-bg: rgba(47,122,79,0.12); --status-warn-bg: rgba(192,125,24,0.12); --status-crit-bg: rgba(179,32,54,0.12);
    --eyebrow-accent: var(--surface-raised);
  }

  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink); font-family: 'IBM Plex Sans', -apple-system, sans-serif; font-size: 15px; line-height: 1.6; }
  .page { max-width: 1180px; margin: 0 auto; padding: 0 20px 64px; }
  .eyebrow { font-family: 'Oswald', sans-serif; font-weight: 700; font-size: 11px; letter-spacing: 2px; text-transform: uppercase; }
  .num { font-family: 'IBM Plex Mono', monospace; font-variant-numeric: tabular-nums; }

  .theme-toggle { position: fixed; top: 14px; right: 14px; z-index: 10; background: var(--surface); border: 1px solid var(--border); color: var(--ink); font-family: 'IBM Plex Mono', monospace; font-size: 11px; padding: 6px 10px; cursor: pointer; }

  .masthead { background: var(--surface-raised); color: var(--ink-on-raised); margin: 0 0 28px; padding: 28px 20px 24px; border-bottom: 6px solid var(--accent); }
  .masthead-inner { max-width: 1180px; margin: 0 auto; }
  .masthead .eyebrow { color: var(--accent); margin-bottom: 6px; }
  .masthead h1 { font-family: 'Oswald', sans-serif; font-weight: 700; font-size: clamp(28px, 4.2vw, 40px); line-height: 1.1; margin: 0 0 6px; text-wrap: balance; }
  .masthead .sub { color: var(--ink-on-raised-muted); font-size: 13px; margin: 0 0 24px; }
  .masthead .sub .num { color: var(--ink-on-raised); }

  .hero-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; background: var(--border-on-raised); border: 1px solid var(--border-on-raised); }
  .hero-stat { background: var(--surface-raised); padding: 16px 18px 18px; }
  .hero-stat .label { font-family: 'Oswald', sans-serif; font-size: 11px; letter-spacing: 1.5px; text-transform: uppercase; color: var(--ink-on-raised-muted); margin-bottom: 8px; }
  .hero-stat .value { font-family: 'IBM Plex Mono', monospace; font-weight: 600; font-size: clamp(22px, 3vw, 30px); font-variant-numeric: tabular-nums; display: flex; align-items: baseline; gap: 8px; }
  .hero-stat .value .unit { font-size: 13px; font-weight: 400; color: var(--ink-on-raised-muted); font-family: 'IBM Plex Sans', sans-serif; }
  .hero-stat .note { font-size: 12px; color: var(--ink-on-raised-muted); margin-top: 6px; }
  @media (max-width: 640px) { .hero-stats { grid-template-columns: 1fr; } }

  .boards { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  .boards.full { grid-template-columns: 1fr; }
  @media (max-width: 860px) { .boards { grid-template-columns: 1fr; } }
  .board { background: var(--surface); border: 1px solid var(--border); padding: 20px 22px 22px; margin-bottom: 20px; }
  .board-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid var(--accent); }
  .board-head .eyebrow { color: var(--eyebrow-accent); }
  .board-head .meta { font-size: 11px; color: var(--ink-muted); font-family: 'IBM Plex Mono', monospace; }

  .roster-row { display: flex; align-items: center; justify-content: space-between; padding: 9px 0; border-top: 1px solid var(--border); }
  .roster-row:first-child { border-top: none; }
  .roster-row .team { font-size: 14px; }
  .roster-row .count { font-family: 'IBM Plex Mono', monospace; font-weight: 600; font-variant-numeric: tabular-nums; }
  .data-flag { margin-top: 14px; padding: 10px 12px; background: var(--status-warn-bg); border-left: 3px solid var(--status-warn); font-size: 12.5px; color: var(--ink); }
  .data-flag strong { color: var(--status-warn); }

  .wf-row { padding: 12px 0; border-top: 1px solid var(--border); }
  .wf-row:first-child { border-top: none; padding-top: 0; }
  .wf-row-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 8px; }
  .wf-name { font-size: 13.5px; font-weight: 600; }
  .wf-rate { font-family: 'IBM Plex Mono', monospace; font-size: 13px; }
  .wf-rate.good { color: var(--status-good); }
  .wf-rate.warn { color: var(--status-warn); }
  .wf-rate.crit { color: var(--status-crit); }
  .strip { display: flex; gap: 2px; margin-bottom: 6px; }
  .tick { flex: 1; height: 18px; background: var(--status-good); position: relative; cursor: default; }
  .tick.crit { background: var(--status-crit); }
  .tick.warn { background: var(--status-warn); }
  .tick[title]:hover::after {
    content: attr(title); position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%);
    background: var(--surface-raised); color: var(--ink-on-raised); font-family: 'IBM Plex Mono', monospace;
    font-size: 11px; padding: 4px 7px; white-space: nowrap; margin-bottom: 4px; z-index: 5;
    border: 1px solid var(--border-on-raised);
  }
  .wf-meta { font-size: 11.5px; color: var(--ink-muted); }

  .score-row { margin-bottom: 12px; }
  .score-row:last-child { margin-bottom: 0; }
  .score-row-head { display: flex; justify-content: space-between; font-size: 12.5px; margin-bottom: 4px; }
  .score-row-head .val { font-family: 'IBM Plex Mono', monospace; font-weight: 600; font-variant-numeric: tabular-nums; }
  .bar-track { height: 8px; background: var(--border); position: relative; }
  .bar-fill { height: 100%; }
  .bar-fill.good { background: var(--status-good); }
  .bar-fill.warn { background: var(--status-warn); }
  .bar-fill.crit { background: var(--status-crit); }

  .eval-overall { display: flex; align-items: baseline; gap: 10px; margin: 16px 0 18px; padding: 12px 14px; background: var(--bg); border: 1px solid var(--border); }
  .eval-overall .big { font-family: 'IBM Plex Mono', monospace; font-weight: 600; font-size: 26px; }
  .eval-overall .lbl { font-size: 12px; color: var(--ink-muted); }

  .trend-wrap { margin-top: 18px; }
  .trend-note { font-size: 11.5px; color: var(--ink-muted); margin-top: 8px; }
  svg.trend { width: 100%; height: auto; overflow: visible; }
  .trend-line { fill: none; stroke: var(--accent); stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; }
  .trend-area { fill: var(--accent); opacity: 0.08; }
  .trend-grid { stroke: var(--border); stroke-width: 1; }
  .trend-pt { fill: var(--surface); stroke: var(--accent); stroke-width: 2.5; }
  .trend-pt-hit { fill: transparent; cursor: pointer; }
  .trend-axis-label { font-family: 'IBM Plex Mono', monospace; font-size: 10px; fill: var(--ink-muted); }
  .trend-endlabel { font-family: 'IBM Plex Mono', monospace; font-size: 12px; font-weight: 600; fill: var(--ink); }
  .trend-tooltip {
    position: absolute; pointer-events: none; background: var(--surface-raised); color: var(--ink-on-raised);
    font-family: 'IBM Plex Mono', monospace; font-size: 11px; padding: 5px 8px; border: 1px solid var(--border-on-raised);
    transform: translate(-50%, -130%); white-space: nowrap; opacity: 0; transition: opacity .1s;
  }
  .trend-tooltip.show { opacity: 1; }
  .eval-caveat { margin-top: 16px; padding: 10px 12px; background: var(--status-warn-bg); border-left: 3px solid var(--status-warn); font-size: 12px; }
  .eval-caveat strong { color: var(--status-warn); }
  .eval-empty { padding: 24px; text-align: center; color: var(--ink-muted); font-size: 13px; }

  .editions-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 1px; background: var(--border); border: 1px solid var(--border); }
  .edition-card { background: var(--surface); padding: 14px 16px 16px; }
  .edition-team { font-family: 'Oswald', sans-serif; font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: var(--eyebrow-accent); border-bottom: 2px solid var(--accent); display: inline-block; padding-bottom: 4px; margin-bottom: 8px; }
  .edition-score { font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: var(--ink-muted); margin-bottom: 6px; }
  .edition-headline { font-size: 13.5px; line-height: 1.55; font-weight: 600; }

  footer { margin-top: 8px; padding-top: 16px; border-top: 1px solid var(--border); font-size: 11.5px; color: var(--ink-muted); }
  footer p { margin: 0 0 6px; }
"""

TOGGLE_SCRIPT = """
(function() {
  var stored = localStorage.getItem('fn-dashboard-theme');
  if (stored) document.documentElement.setAttribute('data-theme', stored);
  window.__toggleTheme = function() {
    var current = document.documentElement.getAttribute('data-theme') ||
      (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    var next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('fn-dashboard-theme', next);
  };
})();
"""


def _band(v):
    if v >= 75:
        return "good"
    if v >= 50:
        return "warn"
    return "crit"


def _roster_html(roster):
    rows = []
    for team, count in roster:
        rows.append(
            f'<div class="roster-row"><span class="team">{team}</span>'
            f'<span class="count num">{count}</span></div>'
        )
    return "\n".join(rows)


def _workflows_html(workflows):
    blocks = []
    for w in workflows:
        ticks = "".join(
            f'<div class="tick {("" if s == "good" else s)}" title="{d} — {s}"></div>'
            for d, s in w["history"]
        )
        pct = round(w["ok"] / w["total"] * 100) if w["total"] else 0
        rate_band = "good" if pct == 100 else ("warn" if pct >= 90 else "crit")
        blocks.append(f"""
        <div class="wf-row">
          <div class="wf-row-head"><span class="wf-name">{w['name']}</span>
          <span class="wf-rate num {rate_band}">{w['ok']}/{w['total']} ({pct}%)</span></div>
          <div class="strip">{ticks}</div>
          <div class="wf-meta">last run {w['last_run']} &middot; schedule: {w['schedule']}</div>
        </div>""")
    return "\n".join(blocks)


def _scorecard_html(metrics):
    rows = []
    for label, value in metrics:
        b = _band(value)
        rows.append(f"""
        <div class="score-row">
          <div class="score-row-head"><span>{label}</span><span class="val">{value:.1f}%</span></div>
          <div class="bar-track"><div class="bar-fill {b}" style="width:{value}%"></div></div>
        </div>""")
    return "\n".join(rows)


def _editions_html(editions):
    if not editions:
        return '<div class="eval-empty">No newsletter editions found yet.</div>'
    cards = []
    for team, score_line, headline in editions:
        cards.append(f"""
        <div class="edition-card">
          <div class="edition-team">{team}</div>
          <div class="edition-score num">{score_line}</div>
          <div class="edition-headline">{headline}</div>
        </div>""")
    return "\n".join(cards)


def render(data: dict) -> str:
    roster_flag_html = ""
    if data.get("roster_flag"):
        roster_flag_html = f'<div class="data-flag"><strong>Data quality:</strong> {data["roster_flag"]}</div>'

    eval_current = data.get("eval_current")
    eval_history = data.get("eval_history") or []
    eval_caveat = data.get("eval_caveat")

    if eval_current:
        eval_overall_html = f"""
          <div class="eval-overall"><span class="big num">{eval_current['overall']:.1f}%</span>
          <span class="lbl">overall weighted score for week of {eval_current['date']} (n={eval_current['n']})<br>
          ({eval_current['weights']})</span></div>
          {_scorecard_html(eval_current['metrics'])}
        """
        hero_eval_value = f"{eval_current['overall']:.1f}"
        hero_eval_note = f"week of {eval_current['date']} &middot; n={eval_current['n']} newsletters"
    else:
        eval_overall_html = '<div class="eval-empty">No evaluation data yet — runs after the first generate_newsletter completes with the evaluation harness live.</div>'
        hero_eval_value = "—"
        hero_eval_note = "no evaluation data yet"

    trend_html = ""
    if len(eval_history) >= 2:
        trend_html = f"""
        <div class="trend-wrap">
          <div class="board-head" style="margin-top:24px;"><span class="eyebrow" style="font-size:10px;">Overall Score — Trend</span>
          <span class="meta">{len(eval_history)} evaluable weeks</span></div>
          <div id="trend-container" style="position:relative;"></div>
        </div>"""

    caveat_html = f'<div class="eval-caveat"><strong>Note:</strong> {eval_caveat}</div>' if eval_caveat else ""

    total_subs = sum(c for _, c in data["roster"])
    total_runs = sum(w["total"] for w in data["workflows"])
    total_ok = sum(w["ok"] for w in data["workflows"])
    pipeline_pct = round(total_ok / total_runs * 100) if total_runs else 0

    editions_week = data.get("editions_week", "no data yet")

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Football News — Control Room</title>
<style>{STYLE}</style>
</head>
<body>
<script>{TOGGLE_SCRIPT}</script>
<button class="theme-toggle" onclick="window.__toggleTheme()">theme</button>

<div class="masthead">
  <div class="masthead-inner">
    <p class="eyebrow">Weekly Operations &middot; Matchday Programme</p>
    <h1>Football News — Control Room</h1>
    <p class="sub">Live view of subscriber reach, pipeline health, and output quality. Generated <span class="num">{data['generated_at']}</span>.</p>
    <div class="hero-stats">
      <div class="hero-stat">
        <div class="label">Subscribers</div>
        <div class="value">{total_subs} <span class="unit">across {len(data['roster'])} clubs</span></div>
        <div class="note">1 per club typical — see roster board</div>
      </div>
      <div class="hero-stat">
        <div class="label">Pipeline Health</div>
        <div class="value">{pipeline_pct}<span class="unit">%</span></div>
        <div class="note">{total_ok} / {total_runs} recent runs succeeded</div>
      </div>
      <div class="hero-stat">
        <div class="label">Latest Eval Score</div>
        <div class="value">{hero_eval_value}<span class="unit">%</span></div>
        <div class="note">{hero_eval_note}</div>
      </div>
    </div>
  </div>
</div>

<div class="page">
  <div class="boards">
    <div class="board">
      <div class="board-head"><span class="eyebrow">Subscriber Roster</span><span class="meta">source: Google Sheet</span></div>
      {_roster_html(data['roster'])}
      {roster_flag_html}
    </div>
    <div class="board">
      <div class="board-head"><span class="eyebrow">Pipeline Run Log</span><span class="meta">last {data['workflows'][0]['total'] if data['workflows'] else 0} GitHub Actions runs</span></div>
      {_workflows_html(data['workflows'])}
    </div>
  </div>

  <div class="boards full">
    <div class="board">
      <div class="board-head"><span class="eyebrow">Evaluation Scorecard</span><span class="meta">{eval_current['date'] if eval_current else ''}</span></div>
      {eval_overall_html}
      {trend_html}
      {caveat_html}
    </div>
  </div>

  <div class="boards full">
    <div class="board">
      <div class="board-head"><span class="eyebrow">Recent Editions</span><span class="meta">{editions_week}</span></div>
      <div class="editions-grid">{_editions_html(data.get('editions', []))}</div>
    </div>
  </div>

  <footer>
    <p>Subscriber counts read live from the "&#49888;&#52397;&#51088; &#47785;&#47197;" worksheet via <code>google_sheet_parser.py</code>. Pipeline runs from the GitHub Actions API. Evaluation scores from <code>evaluate/evaluate_main.py</code>.</p>
    <p>Rebuilds automatically after collect_news and generate_newsletter runs.</p>
  </footer>
</div>

<script>
(function() {{
  var trend = {json.dumps(eval_history)};
  if (trend.length < 2) return;
  var container = document.getElementById('trend-container');
  if (!container) return;
  var W = 900, H = 200, padL = 8, padR = 70, padT = 20, padB = 28;
  var values = trend.map(function(p) {{ return p.overall_score; }});
  var minV = Math.max(0, Math.floor(Math.min.apply(null, values) / 10) * 10 - 10);
  var maxV = Math.min(100, Math.ceil(Math.max.apply(null, values) / 10) * 10 + 5);
  function x(i) {{ return padL + (i / (trend.length - 1)) * (W - padL - padR); }}
  function y(v) {{ return padT + (1 - (v - minV) / (maxV - minV)) * (H - padT - padB); }}
  var pathD = trend.map(function(p, i) {{ return (i === 0 ? 'M' : 'L') + x(i).toFixed(1) + ',' + y(p.overall_score).toFixed(1); }}).join(' ');
  var areaD = pathD + ' L' + x(trend.length - 1).toFixed(1) + ',' + (H - padB) + ' L' + x(0).toFixed(1) + ',' + (H - padB) + ' Z';
  var gridLines = '';
  var step = (maxV - minV) > 40 ? 20 : 10;
  for (var gv = Math.ceil(minV / step) * step; gv <= maxV; gv += step) {{
    gridLines += '<line class="trend-grid" x1="' + padL + '" x2="' + (W - padR) + '" y1="' + y(gv).toFixed(1) + '" y2="' + y(gv).toFixed(1) + '"></line>';
    gridLines += '<text class="trend-axis-label" x="' + (W - padR + 8) + '" y="' + (y(gv) + 3).toFixed(1) + '">' + gv + '%</text>';
  }}
  var points = '', hits = '', labels = '';
  trend.forEach(function(p, i) {{
    points += '<circle class="trend-pt" cx="' + x(i).toFixed(1) + '" cy="' + y(p.overall_score).toFixed(1) + '" r="4"></circle>';
    hits += '<circle class="trend-pt-hit" data-i="' + i + '" cx="' + x(i).toFixed(1) + '" cy="' + y(p.overall_score).toFixed(1) + '" r="14"></circle>';
    labels += '<text class="trend-axis-label" x="' + x(i).toFixed(1) + '" y="' + (H - 8) + '" text-anchor="middle">' + p.date.slice(5) + '</text>';
  }});
  var last = trend[trend.length - 1];
  var endY = y(last.overall_score);
  var endLabel = '<rect x="' + (x(trend.length - 1) + 7) + '" y="' + (endY - 9) + '" width="42" height="16" fill="var(--surface)"></rect>' +
    '<text class="trend-endlabel" x="' + (x(trend.length - 1) + 10) + '" y="' + (endY + 4) + '">' + last.overall_score.toFixed(1) + '%</text>';
  container.innerHTML = '<svg class="trend" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none">' +
    gridLines + '<path class="trend-area" d="' + areaD + '"></path>' + '<path class="trend-line" d="' + pathD + '"></path>' +
    points + endLabel + labels + hits + '</svg><div class="trend-tooltip" id="trend-tooltip"></div>';
  var tooltip = document.getElementById('trend-tooltip');
  container.querySelectorAll('.trend-pt-hit').forEach(function(hit) {{
    hit.addEventListener('mouseenter', function() {{
      var p = trend[+hit.getAttribute('data-i')];
      tooltip.textContent = p.date + '  \\u00b7  ' + p.overall_score.toFixed(1) + '%  (n=' + p.n + ')';
      var rect = container.getBoundingClientRect();
      var scale = rect.width / W;
      tooltip.style.left = (parseFloat(hit.getAttribute('cx')) * scale) + 'px';
      tooltip.style.top = (parseFloat(hit.getAttribute('cy')) * scale) + 'px';
      tooltip.classList.add('show');
    }});
    hit.addEventListener('mouseleave', function() {{ tooltip.classList.remove('show'); }});
  }});
}})();
</script>
</body>
</html>
"""
    return html
