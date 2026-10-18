# Global Tech

A public, read-only research calendar for semiconductor, software and AI infrastructure catalysts. Calendar and list views share the same dataset and filters. Visitors can browse, filter and open source briefs; there are no write endpoints, event editors or credentials in the client.

## Run locally

Use the existing checkout. Cloud tasks are already isolated; do not create a worktree for setup.

```sh
cd /workspace/train-me-to-be-a-better-financial-analyst
python3 -m http.server 8000 --bind 127.0.0.1
```

Python 3.10+ is sufficient to serve, validate, build and refresh sources. There is no npm install or application build dependency. Node.js is used for JavaScript syntax and timezone/ICS checks in CI. Serve over HTTP; opening `index.html` directly does not support dataset fetching.

```sh
python3 -m unittest discover -s tests -v
node --check js/calendar-utils.js
node --check js/events.js
node --test tests/calendar-utils.test.cjs
python3 scripts/build_site.py
```

The build writes ignored `_site/` assets. Only the earnings and events application is published. The former research library, semiconductor article and Chinese-learning application have been removed. The build recreates `_site` to prevent removed pages from remaining in the public artifact.

Optional browser checks use Python Playwright and `/usr/bin/chromium`, already available in the current cloud machine. With the server running:

```sh
python3 tests/browser_smoke.py
python3 tests/timezone_export_smoke.py
```

These checks exercise both views, priority filtering, source details, keyboard dismissal, empty states, safe text rendering, cross-month events and the mobile layout. They freeze the browser clock to the dataset's seed month. They do not validate external websites or licensed feeds.

## Coverage

The original 12 coverage companies are TSMC (TSM), NVIDIA, AMD, Broadcom, Marvell Technology, Apple, Microsoft, Oracle, Salesforce, ServiceNow, Adobe and Workday. Stars identify their events in both views and event briefs. Multi-company events are priority events if at least one covered company participates.

The wider universe includes ASML, Lam Research, Samsung, SK hynix, Micron, MediaTek, Amazon, Alphabet, Anthropic, CoreWeave, Nebius, Cloudflare, OpenAI, Meta, Intel, Arm, Qualcomm, Snowflake, CrowdStrike and Palo Alto Networks. Hyperscaler earnings are included for capex context. GTC, OCP, re:Invent, Ignite, investor days and a potential Anthropic IPO are monitoring targets. An undated watch item does not assert that an event or IPO is scheduled. Dividends and routine corporate actions are not seeded.

## Browsing and presentation

The calendar/list switch is at the top, without a hero banner or statistics cards. Only Calendar view is month-based. List view is one chronological, scrollable timeline containing every event across all months and years. It initially scrolls to a today marker; scroll upward for history and downward for future events. “Jump to today” restores that position. Search and filters apply to the full timeline, not a selected month. The sidebar lists every tracked company in two sections: 12 starred coverage companies and 20 other companies in research scope. On mobile, the company-universe menu exposes the same lists without pushing the calendar down.

Color is determined only by event type: blue for earnings, blue-green for operating updates, teal for conferences, purple for keynotes, amber for investor days and slate for IPO watches. Coverage adds a star, not a different background. Unconfirmed dates and timing windows (estimated, media-reported or unannounced) have dotted borders. Officially confirmed events have solid borders, including events in the future. This is independent of whether an event is past or upcoming. The legend spells out these meanings.

The compact calendar shows event titles, coverage stars and short clock times when verified; earnings use ticker labels. It omits source links and repeated status/lifecycle labels from the grid. Hover for the full title or open an event brief for full timing and evidence. Timing-window cards are compact too. Every list row and undated watch item exposes all its evidence links, deduplicated by URL, without opening a dialog. Provider estimates link to the provider calendar; company announcements and event schedules link to their evidence. Opening a brief still shows status, check timestamps, source discrepancies and all sources. Outbound URLs must use HTTPS and are rendered safely.

Multi-day conferences appear as connected bands across consecutive calendar days, with a continuation when they cross a week boundary. The band opens one event brief and represents one selectable/exportable event. Oracle AI World 2026 combines its keynote sessions, including Clay Magouyrk’s keynote, into the conference entry. Their source links and published session times remain in the brief, without separate session cards. The 2025 conference remains a separate historical edition.

CoreWeave's November 9 and Nebius's November 10, 2026 earnings dates are public provider estimates. They are not presented as officially confirmed dates.

## Timezones and Outlook export

Hong Kong (`Asia/Hong_Kong`) is the initial default, even if the browser runs elsewhere. The user can choose Browser timezone or a named city; the preference is saved locally in that browser. Verified UTC `startAt`/optional `endAt` values drive the displayed date, time, calendar cell and list ordering. For example, Apple's November 2, 2026 14:00 Pacific call is November 3 at 06:00 in Hong Kong. The original source date/time remains in its event brief. Conflicting AMD time wording remains unnormalized; estimated dates with no verified clock time remain date-only.

To export, click **Select events**, check several events, then click **Download .ics**. **Select shown** selects the current filtered list or calendar month; **Clear selection** resets it. Selected events remain selected across views, months, filters and timezone changes. A multi-day conference spanning several calendar dates is selected and exported once. The website remains read-only: selection/export does not edit the public dataset.

The generated RFC 5545 `.ics` uses stable event UIDs, UTC timestamps for timed calls, exclusive end dates for all-day ranges, CRLF line endings, escaped text and UTF-8-aware 75-octet folding. Outlook displays timed events in Outlook's own timezone. No unannounced duration is invented. Date-only events export as all-day markers. Forecasts and reports are marked tentative; month/year timing windows explicitly say TIMING WINDOW and export as transparent all-day ranges so they do not mark the user busy. Truly unsourced timing cannot be selected. Import or open the downloaded file in Outlook; this is a downloadable snapshot, not a subscription or an ongoing sync.

Pure Node tests cover DST, cross-day/month/year conversion, source-time conflicts, all-day boundaries, stable IDs, deduplication, escaping, folding and uncertain-window semantics. Browser checks download actual files, test default Hong Kong on a simulated New York browser, and exercise mobile and desktop selection. Downloaded test files were also parsed with an independent iCalendar parser; access to a running Outlook client was not available.

## Data integrity and maintenance through Codex

`data/events.json` is the reviewed event store. Public visitors cannot modify it. Ask Codex to add, update or delete events, then validate and deploy the change.

- **confirmed**: a date checked against an official company announcement, event organizer page or participant schedule. The record includes source links, a check timestamp and evidence in `basis`. Release times and conference-call times are distinguished.
- **estimated**: an actual day-level estimate published by a named public provider, not our own reporting-month assumption. Sources include MarketBeat, Stock Analysis and FT Markets (whose page credits LSEG). A checked estimate is still unconfirmed; `sourceCheckedAt` is populated, but `verifiedAt` is null. Do not infer a precise release time from an estimated calendar date.
- **reported**: an attributable media-reported date when primary confirmation was not verified. This includes Anthropic’s October 14 investor day, reported by Bloomberg and read through Yahoo Finance/Stocktwits. `verifiedAt` is null. A scheduled past date does not independently prove attendance.
- **unannounced**: an undated monitoring target. A potential IPO listing remains undated until a sourced listing date is available. Do not confuse an investor day or proposed marketing week with a listing date.

Every dated entry includes `sourceCheckedAt`, `sourceUrl`, `sourceLabel`, a `sources` array and a rationale. `dateConflict`, when present, exposes discrepancies in the event brief. Official company announcements override older provider estimates. Examples found in this review include official ServiceNow after-close timing versus a vendor's before-open label; an AMD timezone label requiring verification; MediaTek calendars disagreeing; and ASML provider confirmation flags disagreeing.

All 12 coverage companies have a sourced day-level next earnings date as of October 15, 2026. Unsourced January–March reporting-month placeholders were removed. Do not fill future quarters by extrapolating cadence. Check a public provider or company announcement first.

Dates and optional `endDate` use `YYYY-MM-DD` in the published event calendar. Conference sessions can be combined into their parent event, preserving their evidence and timing details in its brief; Oracle AI World uses this presentation. Other separately tracked keynotes remain distinct events. Published clock times are normalized to UTC instants with an IANA source timezone. The client converts those instants and their dates to the selected timezone, accounting for daylight saving. Hong Kong is the default, with an explicit Browser timezone option and common cities. Date-only entries retain their published source date; a clock time or day rollover is never invented for them. The today indicator follows the selected timezone. Past scheduled dates stay in their historical month and display “Past date”; they cannot appear in the undated radar. The October 14 ASML results, October 14 Anthropic investor day, October 12–15 OCP edition and October 6 Marvell investor day are dated entries. Future GTC editions, CEO keynotes, Ignite and re:Invent use published schedules.

Dates checked more than 14 days ago display a recheck label. Check timestamps prove a source review, not a guarantee that the schedule cannot change. Status labels distinguish estimates and media-reported dates without changing event-type colors.

### Approximate timing is distinct from an exact date

An event with `timingWindow` has `date: null` and `endDate: null`. Its window records `start`, `end`, `precision` and a human-readable `label`. Range boundaries define an uncertainty period, not scheduled event days. The list displays the label and sorts by the window start; the month calendar shows overlapping windows in a separate panel rather than filling calendar cells with a fabricated IPO date.

Anthropic's possible IPO is a reported November 2026 month window; its proposed marketing week is a separate week window. OpenAI's possible IPO is a broad 2027 scenario window. Sources disagree about late 2026 versus early 2027, and no specific quarter is confirmed, so the app does not invent one. These are unconfirmed targets, never guaranteed listings.

An industry event may have no tracked company: it then requires an `organizer` and primary event evidence. MIT AI Conference is such an event. Do not imply that tracked companies are participants merely to populate a company field. Newly verified conference dates include MIT AI Conference (October 17, 2026), Cloudflare Connect (October 19–21, 2026) and Oracle AI World (October 25–28, 2026). Oracle's October 13–16, 2025 edition is retained as a separate historical event. “Agenti Conference” remains to be identified rather than guessing its organizer or date.

### Check public sources

```sh
python3 scripts/refresh_events.py
```

This dependency-free command checks company pages, official event metadata and cited provider calendars with TLS verification, at most four concurrent requests and 20-second timeouts. It writes `data/source-checks.json` with retrieval results, candidate evidence and explicitly published estimates in `publishedEstimate`.

The provider parser only accepts explicitly labeled next earnings estimates from supported providers. It rejects unlabeled historic earnings dates and dates already in the past. Company dates must still be checked against primary announcements: a provider can retain an estimate label after a company has announced its date. JSON event metadata is staged for review; its date may refer to an earnings call rather than a release time.

The command never automatically modifies reviewed events or promotes a publication date to an event date. Review the staged evidence in Codex, resolve conflicting sources and update the relevant record. Do not add duplicates when replacing a provider estimate with a company-confirmed date. Update review timestamps only for evidence actually checked. A partial source-check run is explicitly partial; HTTP 200 alone does not prove a JavaScript calendar was rendered.

The source-check report is linked from the website footer. Current reviewed earnings sources and their timestamps are also included in each event brief, including multiple sources where useful. Static publisher pages can lag; vendor estimates are not promises.

There is no live licensed Bloomberg or Refinitiv API connection. Bloomberg reporting is attributed through public reporting; FT Markets' public forecasts page credits LSEG for data. Neither is represented as authenticated terminal access. Visitors cannot edit events. Manual changes remain available through Codex; the native scheduled task below is the intended recurring maintenance path.

## Weekly native Codex task

The weekly work should run as a native scheduled Codex task using the platform's model and repository access. Codex researches, reviews and edits the event data, then commits and pushes it. `.github/workflows/deploy-pages.yml` publishes that push to GitHub Pages and verifies the live dataset. This flow needs no separate OpenAI API key, Resend account, or GitHub research cron.

The complete task settings and copyable research/publication prompt are in [docs/weekly-codex-task.md](docs/weekly-codex-task.md). Schedule **Sunday at 02:00 Asia/Hong_Kong**, select the strongest available native Codex model and its highest reasoning setting, and use native task notifications. Email to `hangyul.son@clsa.com` depends on the platform's notification controls and configured destination; do not treat it as enabled merely because it appears in a prompt.

**Registration is pending:** saving the task instructions in the repository does not create a platform schedule. The task must be created and confirmed active in the native Scheduled/Automations interface. The current chat exposes no native task-creation tool. Test one native run with repository read/write access, web research and command execution before relying on it. A local desktop task needs the computer and app running; use a cloud-capable task if offered for unattended overnight work.

The API-based GitHub weekly workflow has been removed. Legacy `scripts/weekly_refresh.py`, `scripts/send_weekly_email.py` and their policy/tests are inactive; the native task must not invoke them. The public-source staging command, application checks and push-to-Pages deployment remain available. An uncertainty or incomplete source review must be reported honestly; no model can guarantee error-free or exhaustive coverage.

## Public hosting

The site can be served worldwide without an application server, database or visitor login. It is prepared for either hosting option:

- **GitHub Pages:** the existing `deploy-pages.yml` validates and builds the static artifact, then deploys on pushes to `main` or `claude/build-tech-finance-site-HRNbI`, or manual workflow dispatch. Configure the repository's Pages source to **GitHub Actions**. The redundant Jekyll deployment was removed because the site has no Jekyll dependency.
- **Netlify:** connect this repository; `netlify.toml` runs the static copy build and publishes `_site`.

The public calendar is deployed through GitHub Pages at https://hangyul-son.github.io/global-tech-team-features/. Source updates require a repository change and successful deployment; the native scheduled Codex task is intended to perform both automatically once registered. Deployments also ensure the Pages source is GitHub Actions where the token permits it, so an unrelated branch does not replace the calendar. If GitHub refuses that setting change, a repository administrator must select **Settings > Pages > Source > GitHub Actions** once. The cloud development environment's Publish action snapshots the development machine; it does not publish this website to GitHub Pages or Netlify.

## Targeted source additions · October 18, 2026

Sixteen official-source events were added without changing the 12/20 company universe: TSMC monthly revenue publication dates (October, November and December revenue), Adobe MAX and its opening keynote, Adobe Summit 2027, Workday Rising US and EMEA, ServiceNow Knowledge 2027, three Oracle AI World keynotes, Salesforce TDX and Dreamforce 2027, CES 2027, and Workday's October 13 financial analyst day. The NVIDIA GTC 2027 entry now displays the official FAQ's broader March 14–18 range as a discrepancy alongside the March 15–18 core conference dates. The dataset retains October 15 as the last complete universe review; October 18 is marked as a targeted update, not an exhaustive recheck. Monthly revenue is shown as a separate **Operating update** type and never misrepresented as an earnings call.

The previous Workday investor-relations events URL returned HTTP 404 in the October 15 source check. The company-universe link now points to the working official investor-relations homepage; the historical source-check report retains the original failed retrieval.
