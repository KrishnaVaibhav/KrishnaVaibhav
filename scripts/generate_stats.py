"""Generate the animated GitHub stats cards in assets/generated/.

Runs daily from .github/workflows/profile-stats.yml. Needs GITHUB_TOKEN (any token that can
read public GraphQL data) and optionally GITHUB_USER (defaults to KrishnaVaibhav).
"""
import datetime as dt
import json
import os
import urllib.request
from collections import Counter
from html import escape

USER = os.environ.get("GITHUB_USER", "KrishnaVaibhav")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "generated")

# Card theme — matches assets/header.svg
BG, BORDER, GRID = "#0b1022", "#24304f", "#1b2542"
INK, DIM, MUTED = "#e6edf3", "#8fa3c7", "#5b6a8c"
PURPLE, TEAL = "#8b7cf6", "#5eead4"
# Categorical slots, validated (dataviz validate_palette.js, dark, surface #0b1022): all checks pass
SERIES = ["#8b7cf6", "#199e70", "#d95926", "#3987e5", "#c98500"]
OTHER = "#5b6478"
FONT = "'JetBrains Mono','Fira Code','Cascadia Code',Consolas,'Courier New',monospace"


# ---------------------------------------------------------------- data
def gql(query, **variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.load(r)
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]


def fetch():
    profile = gql("""
      query($login: String!) {
        user(login: $login) {
          createdAt
          followers { totalCount }
          pullRequests { totalCount }
          merged: pullRequests(states: MERGED) { totalCount }
          issues { totalCount }
          repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, PULL_REQUEST_REVIEW]) { totalCount }
        }
      }""", login=USER)["user"]

    repos, cursor = [], None
    while True:
        page = gql("""
          query($login: String!, $cursor: String) {
            user(login: $login) {
              repositories(ownerAffiliations: OWNER, isFork: false, first: 100, after: $cursor, privacy: PUBLIC) {
                totalCount
                pageInfo { hasNextPage endCursor }
                nodes {
                  name stargazerCount forkCount pushedAt
                  primaryLanguage { name }
                  languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } }
                }
              }
            }
          }""", login=USER, cursor=cursor)["user"]["repositories"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    now = dt.datetime.now(dt.timezone.utc)
    start_year = int(profile["createdAt"][:4])
    years, days = [], {}
    for year in range(start_year, now.year + 1):
        frm = dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc)
        to = min(dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc), now)
        c = gql("""
          query($login: String!, $from: DateTime!, $to: DateTime!) {
            user(login: $login) {
              contributionsCollection(from: $from, to: $to) {
                totalCommitContributions totalPullRequestReviewContributions restrictedContributionsCount
                contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
              }
            }
          }""", login=USER, **{"from": frm.isoformat(), "to": to.isoformat()})["user"]["contributionsCollection"]
        years.append(c)
        for w in c["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]

    last_year = gql("""
      query($login: String!) {
        user(login: $login) {
          contributionsCollection {
            totalCommitContributions totalPullRequestContributions totalIssueContributions
            totalPullRequestReviewContributions totalRepositoryContributions restrictedContributionsCount
            contributionCalendar { totalContributions weeks { contributionDays { date contributionCount weekday } } }
          }
        }
      }""", login=USER)["user"]["contributionsCollection"]

    return profile, repos, years, days, last_year, now


# ---------------------------------------------------------------- helpers
def fmt(n):
    if n >= 100_000:
        return f"{n / 1000:.0f}k"
    if n >= 10_000:
        return f"{n / 1000:.1f}k"
    return f"{n:,}"


def date_range(a, b):
    a, b = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    left = f"{a:%b} {a.day}" + ("" if a.year == b.year else f", {a.year}")
    return f"{left} – {b:%b} {b.day}, {b.year}"


def card(w, h, title, body, label):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{escape(label)}">
<title>{escape(label)}</title>
<defs>
  <linearGradient id="edge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{PURPLE}" stop-opacity=".55"/><stop offset=".5" stop-color="{BORDER}"/><stop offset="1" stop-color="{TEAL}" stop-opacity=".55"/></linearGradient>
  <linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{PURPLE}" stop-opacity=".45"/><stop offset="1" stop-color="{PURPLE}" stop-opacity="0"/></linearGradient>
</defs>
<style>
  text {{ font-family: {FONT}; }}
  @keyframes rise {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: none; }} }}
  @keyframes grow {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
  @keyframes growY {{ from {{ transform: scaleY(0); }} to {{ transform: scaleY(1); }} }}
  @keyframes draw {{ from {{ stroke-dashoffset: 1; }} to {{ stroke-dashoffset: 0; }} }}
  @keyframes fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
  @keyframes pulse {{ 0%, 100% {{ opacity: .35; }} 50% {{ opacity: 1; }} }}
  .rise {{ animation: rise .7s ease-out both; }}
  .grow {{ transform-box: fill-box; transform-origin: left; animation: grow 1s cubic-bezier(.2,.8,.2,1) both; }}
  .growY {{ transform-box: fill-box; transform-origin: bottom; animation: growY .9s cubic-bezier(.2,.8,.2,1) both; }}
  .draw {{ stroke-dasharray: 1; animation: draw 2.2s ease-in-out both; }}
  .fade {{ animation: fade 1.2s ease-out both; }}
  .pulse {{ animation: pulse 2.4s ease-in-out infinite; }}
  @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
</style>
<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="14" fill="{BG}" stroke="url(#edge)" stroke-width="1.5"/>
<circle class="pulse" cx="26" cy="31" r="4" fill="{TEAL}"/>
<text x="38" y="36" font-size="14" font-weight="700" fill="{INK}">{escape(title)}</text>
{body}
</svg>
'''


def delay(i, step=0.08, base=0.1):
    return f'style="animation-delay:{base + i * step:.2f}s"'


# ---------------------------------------------------------------- cards
def overview_card(p, repos, years):
    stars = sum(r["stargazerCount"] for r in repos)
    commits = sum(y["totalCommitContributions"] for y in years)
    reviews = sum(y["totalPullRequestReviewContributions"] for y in years)
    rows = [
        ("Stars earned", stars), ("Commits", commits),
        ("Pull requests", p["pullRequests"]["totalCount"]), ("PRs merged", p["merged"]["totalCount"]),
        ("Issues opened", p["issues"]["totalCount"]), ("Code reviews", reviews),
        ("Contributed to (1y)", p["repositoriesContributedTo"]["totalCount"]), ("Followers", p["followers"]["totalCount"]),
    ]
    body = []
    for i, (label, val) in enumerate(rows):
        col, row = i % 2, i // 2
        x0, x1, y = 24 + col * 236, 222 + col * 236, 78 + row * 32
        body.append(f'<g class="rise" {delay(i)}>'
                    f'<rect x="{x0}" y="{y - 10}" width="3" height="12" rx="1.5" fill="{PURPLE if col == 0 else TEAL}"/>'
                    f'<text x="{x0 + 12}" y="{y}" font-size="12.5" fill="{DIM}">{label}</text>'
                    f'<text x="{x1}" y="{y}" font-size="14" font-weight="700" fill="{INK}" text-anchor="end">{fmt(val)}</text></g>')
    return card(495, 200, "git stats --all-time", "".join(body), "All-time GitHub stats")


def streaks(days, today):
    dates = sorted(days)
    longest = (0, None, None)
    run, run_start = 0, None
    prev = None
    for d in dates:
        if days[d] > 0:
            if prev is not None and run and (dt.date.fromisoformat(d) - dt.date.fromisoformat(prev)).days == 1:
                run += 1
            else:
                run, run_start = 1, d
            if run > longest[0]:
                longest = (run, run_start, d)
            prev = d
        else:
            run = 0
            prev = d
    # current streak: walk back from today (today may still be empty)
    cur, end = 0, None
    d = today
    if days.get(d.isoformat(), 0) == 0:
        d -= dt.timedelta(days=1)
    while days.get(d.isoformat(), 0) > 0:
        cur += 1
        end = end or d.isoformat()
        d -= dt.timedelta(days=1)
    start = (d + dt.timedelta(days=1)).isoformat() if cur else None
    return (cur, start, end), longest


def streak_card(days, years, today, created):
    total = sum(y["contributionCalendar"]["totalContributions"] for y in years)
    (cur, cs, ce), (lng, ls, le) = streaks(days, today)
    circ = 2 * 3.14159 * 42
    frac = min(cur / lng, 1) if lng else 0
    cur_range = date_range(cs, ce) if cur else "start one today"
    lng_range = date_range(ls, le) if lng else "—"
    body = f'''
<g class="rise" {delay(0)}>
  <text x="85" y="110" font-size="30" font-weight="800" fill="{INK}" text-anchor="middle">{fmt(total)}</text>
  <text x="85" y="134" font-size="12" fill="{DIM}" text-anchor="middle">Total contributions</text>
  <text x="85" y="154" font-size="10.5" fill="{MUTED}" text-anchor="middle">since {dt.date.fromisoformat(created[:10]).strftime("%b %Y")}</text>
</g>
<line x1="170" y1="70" x2="170" y2="170" stroke="{GRID}"/>
<line x1="325" y1="70" x2="325" y2="170" stroke="{GRID}"/>
<g class="rise" {delay(1)}>
  <circle cx="247.5" cy="106" r="42" fill="none" stroke="{GRID}" stroke-width="6"/>
  <circle cx="247.5" cy="106" r="42" fill="none" stroke="{TEAL}" stroke-width="6" stroke-linecap="round"
          transform="rotate(-90 247.5 106)" stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ * (1 - frac):.1f}"
          style="animation: ring 1.4s .3s cubic-bezier(.2,.8,.2,1) both"/>
  <style>@keyframes ring {{ from {{ stroke-dashoffset: {circ:.1f}; }} }}</style>
  <text x="247.5" y="115" font-size="28" font-weight="800" fill="{INK}" text-anchor="middle">{cur}</text>
  <text x="247.5" y="168" font-size="12" font-weight="700" fill="{TEAL}" text-anchor="middle">Current streak</text>
  <text x="247.5" y="186" font-size="10.5" fill="{MUTED}" text-anchor="middle">{cur_range}</text>
</g>
<g class="rise" {delay(2)}>
  <text x="410" y="110" font-size="30" font-weight="800" fill="{INK}" text-anchor="middle">{lng}</text>
  <text x="410" y="134" font-size="12" fill="{DIM}" text-anchor="middle">Longest streak</text>
  <text x="410" y="154" font-size="10.5" fill="{MUTED}" text-anchor="middle">{lng_range}</text>
</g>'''
    return card(495, 200, "git streak --days", body, f"Contribution streaks: current {cur} days, longest {lng} days")


def language_sizes(repos):
    sizes = Counter()
    for r in repos:
        for e in r["languages"]["edges"]:
            sizes[e["node"]["name"]] += e["size"]
    return sizes


def language_colors(repos):
    """Colour follows the language everywhere: top-5 by bytes get the series slots, the rest are 'Other'."""
    return {n: SERIES[i] for i, (n, _) in enumerate(language_sizes(repos).most_common(5))}


def languages_card(repos):
    sizes = language_sizes(repos)
    total = sum(sizes.values()) or 1
    top = sizes.most_common(5)
    other = total - sum(s for _, s in top)
    parts = [(n, s, SERIES[i]) for i, (n, s) in enumerate(top)]
    if other > 0:
        parts.append(("Other", other, OTHER))
    x, W, gap, body = 24, 447, 2, []
    usable = W - gap * (len(parts) - 1)
    body.append(f'<clipPath id="bar"><rect x="24" y="62" width="{W}" height="12" rx="6"/></clipPath><g clip-path="url(#bar)">')
    for i, (n, s, c) in enumerate(parts):
        w = max(usable * s / total, 2)
        body.append(f'<rect class="grow" {delay(i, .12)} x="{x:.1f}" y="62" width="{w:.1f}" height="12" fill="{c}"/>')
        x += w + gap
    body.append("</g>")
    for i, (n, s, c) in enumerate(parts):
        col, row = i % 2, i // 2
        lx, ly = 24 + col * 236, 112 + row * 28
        body.append(f'<g class="rise" {delay(i, .08, .5)}><circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{c}"/>'
                    f'<text x="{lx + 18}" y="{ly}" font-size="12.5" fill="{INK}">{escape(n)}</text>'
                    f'<text x="{lx + 198}" y="{ly}" font-size="12.5" fill="{DIM}" text-anchor="end">{s / total * 100:.1f}%</text></g>')
    return card(495, 200, "languages --by-bytes", "".join(body),
                "Top languages: " + ", ".join(f"{n} {s / total * 100:.1f}%" for n, s, _ in parts))


def weekday_card(last_year):
    by_day = [0] * 7
    for w in last_year["contributionCalendar"]["weeks"]:
        for d in w["contributionDays"]:
            by_day[d["weekday"]] += d["contributionCount"]
    order = [1, 2, 3, 4, 5, 6, 0]  # Mon..Sun
    names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    vals = [by_day[i] for i in order]
    peak = max(vals) or 1
    pi = vals.index(max(vals))
    base, maxh, bw, step, x0 = 168, 92, 38, 63, 37
    body = [f'<line x1="24" y1="{base}" x2="471" y2="{base}" stroke="{GRID}"/>']
    for i, v in enumerate(vals):
        h = max(v / peak * maxh, 2)
        x = x0 + i * step
        c = TEAL if i == pi else PURPLE
        body.append(f'<path class="growY" {delay(i, .07)} d="M{x} {base} V{base - h + 4} Q{x} {base - h} {x + 4} {base - h} '
                    f'H{x + bw - 4} Q{x + bw} {base - h} {x + bw} {base - h + 4} V{base} Z" fill="{c}" fill-opacity="{1 if i == pi else .75}"/>')
        body.append(f'<text x="{x + bw / 2}" y="{base + 18}" font-size="11.5" fill="{INK if i == pi else DIM}" text-anchor="middle">{names[order[i]]}</text>')
    body.append(f'<text class="fade" style="animation-delay:1s" x="{x0 + pi * step + bw / 2}" y="{base - peak / peak * maxh - 8}" '
                f'font-size="12" font-weight="700" fill="{INK}" text-anchor="middle">{fmt(vals[pi])}</text>')
    return card(495, 200, "contributions --by-weekday --1y", "".join(body),
                "Contributions by weekday, last 12 months: " + ", ".join(f"{names[order[i]]} {v}" for i, v in enumerate(vals)))


def mix_card(last_year):
    rows = [("Commits", last_year["totalCommitContributions"]),
            ("Pull requests", last_year["totalPullRequestContributions"]),
            ("Code reviews", last_year["totalPullRequestReviewContributions"]),
            ("Issues", last_year["totalIssueContributions"]),
            ("Repos created", last_year["totalRepositoryContributions"])]
    if last_year["restrictedContributionsCount"]:
        rows.append(("Private", last_year["restrictedContributionsCount"]))
    peak = max(v for _, v in rows) or 1
    gap = 128 / len(rows)
    body = []
    for i, (label, v) in enumerate(rows):
        y = 66 + i * gap
        w = max(v / peak * 250, 3)
        body.append(f'<text class="rise" {delay(i)} x="24" y="{y + 9}" font-size="12.5" fill="{DIM}">{label}</text>'
                    f'<rect class="grow" {delay(i, .08, .2)} x="140" y="{y}" width="{w:.1f}" height="11" rx="4" fill="{PURPLE}"/>'
                    f'<text class="fade" {delay(i, .08, .8)} x="{140 + w + 8:.1f}" y="{y + 9.5}" font-size="12.5" font-weight="700" fill="{INK}">{fmt(v)}</text>')
    return card(495, 200, "activity --mix --1y", "".join(body), "Contribution mix, last 12 months: " +
                ", ".join(f"{l} {v}" for l, v in rows))


def repos_card(repos):
    top = sorted(repos, key=lambda r: (r["stargazerCount"], r["forkCount"], r["pushedAt"]), reverse=True)[:4]
    colors = language_colors(repos)
    body = [f'<text x="471" y="36" font-size="11.5" fill="{MUTED}" text-anchor="end">{len(repos)} public repos</text>']
    for i, r in enumerate(top):
        y = 76 + i * 32
        lang = (r["primaryLanguage"] or {}).get("name", "—")
        name = r["name"] if len(r["name"]) <= 24 else r["name"][:23] + "…"
        body.append(f'<g class="rise" {delay(i)}>'
                    f'<text x="24" y="{y}" font-size="13" font-weight="700" fill="{INK}">{escape(name)}</text>'
                    f'<circle cx="276" cy="{y - 4}" r="4.5" fill="{colors.get(lang, OTHER)}"/>'
                    f'<text x="286" y="{y}" font-size="11.5" fill="{DIM}">{escape(lang[:12])}</text>'
                    f'<text x="420" y="{y}" font-size="12" fill="{INK}" text-anchor="end">★ {fmt(r["stargazerCount"])}</text>'
                    f'<text x="471" y="{y}" font-size="12" fill="{DIM}" text-anchor="end">⑂ {fmt(r["forkCount"])}</text></g>')
    return card(495, 200, "repos --top", "".join(body), "Top repositories: " + ", ".join(r["name"] for r in top))


def activity_card(last_year):
    weeks = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in last_year["contributionCalendar"]["weeks"]]
    first_days = [w["contributionDays"][0]["date"] for w in last_year["contributionCalendar"]["weeks"]]
    W, H, L, R, T, B = 1000, 260, 56, 24, 64, 220
    n = len(weeks)
    peak = max(weeks) or 1
    nice = max(4, -(-peak // 4) * 4)
    sx = lambda i: L + i * (W - L - R) / (n - 1)
    sy = lambda v: B - v / nice * (B - T)
    body = []
    for k in range(5):
        v = nice * k // 4
        body.append(f'<line x1="{L}" y1="{sy(v):.1f}" x2="{W - R}" y2="{sy(v):.1f}" stroke="{GRID}" stroke-dasharray="{"0" if k == 0 else "3 5"}"/>'
                    f'<text x="{L - 10}" y="{sy(v) + 4:.1f}" font-size="11" fill="{MUTED}" text-anchor="end">{v}</text>')
    seen = set()
    for i, d in enumerate(first_days):
        m = d[:7]
        if m not in seen and i > 0 and first_days[i - 1][:7] != m:
            seen.add(m)
            body.append(f'<text x="{sx(i):.1f}" y="{B + 22}" font-size="11" fill="{MUTED}" text-anchor="middle">{dt.date.fromisoformat(d).strftime("%b")}</text>')
    pts = [(sx(i), sy(v)) for i, v in enumerate(weeks)]
    # smooth line (Catmull-Rom → cubic Bézier), clamped so it never dips below the baseline
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
    for i in range(n - 1):
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, n - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, min(p1[1] + (p2[1] - p0[1]) / 6, B))
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, min(p2[1] - (p3[1] - p1[1]) / 6, B))
        d += f" C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
    body.append(f'<path class="fade" style="animation-delay:.9s" d="{d} L{pts[-1][0]:.1f} {B} L{pts[0][0]:.1f} {B} Z" fill="url(#area)"/>')
    body.append(f'<path class="draw" pathLength="1" d="{d}" fill="none" stroke="{PURPLE}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
    pi = weeks.index(max(weeks))
    px, py = pts[pi]
    anchor = "end" if pi > n * 0.8 else "middle"
    body.append(f'<g class="fade" style="animation-delay:1.8s"><circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="{TEAL}" stroke="{BG}" stroke-width="2"/>'
                f'<text x="{px:.1f}" y="{py - 12:.1f}" font-size="12" font-weight="700" fill="{INK}" text-anchor="{anchor}">peak · {weeks[pi]}</text></g>')
    total = last_year["contributionCalendar"]["totalContributions"]
    body.append(f'<text x="{W - R}" y="36" font-size="12" fill="{DIM}" text-anchor="end">{fmt(total)} contributions in the last year</text>')
    return card(W, H, "contributions --weekly --1y", "".join(body),
                f"Weekly contributions over the last 12 months, {total} total, peak {weeks[pi]} in one week")


def main():
    profile, repos, years, days, last_year, now = fetch()
    os.makedirs(OUT, exist_ok=True)
    cards = {
        "activity.svg": activity_card(last_year),
        "overview.svg": overview_card(profile, repos, years),
        "streak.svg": streak_card(days, years, now.date(), profile["createdAt"]),
        "languages.svg": languages_card(repos),
        "weekday.svg": weekday_card(last_year),
        "mix.svg": mix_card(last_year),
        "repos.svg": repos_card(repos),
    }
    for name, svg in cards.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(svg)
    print("wrote", ", ".join(cards))


if __name__ == "__main__":
    main()
