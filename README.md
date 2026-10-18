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

Color is determined only by event type: blue for earnings, teal for conferences, purple for keynotes, amber for investor days and slate for IPO watches. Coverage adds a star, not a different background. Unconfirmed dates and timing windows (estimated, media-reported or unannounced) have dotted borders. Officially confirmed events have solid borders, including events in the future. This is independent of whether an event is past or upcoming. The legend spells out these meanings.

The compact calendar shows event titles, coverage stars and short clock times when verified; earnings use ticker labels. It omits source links and repeated status/lifecycle labels from the grid. Hover for the full title or open an event brief for full timing and evidence. Timing-window cards are compact too. Every list row and undated watch item exposes all its evidence links, deduplicated by URL, without opening a dialog. Provider estimates link to the provider calendar; company announcements and event schedules link to their evidence. Opening a brief still shows status, check timestamps, source discrepancies and all sources. Outbound URLs must use HTTPS and are rendered safely.

CoreWeave's November 9 and Nebius's November 10, 2026 earnings dates are public provider estimates. They are not presented as officially confirmed dates.

## Timezones and Outlook export

Hong Kong (`Asia/Hong_Kong`) is the initial default, even if the browser runs elsewhere. The user can choose Browser timezone or a named city; the preference is saved locally in that browser. Verified UTC `startAt`/optional `endAt` values drive the displayed date, time, calendar cell and list ordering. For example, Apple's November 2, 2026 14:00 Pacific call is November 3 at 06:00 in Hong Kong. The original source date/time remains in its event brief. Conflicting AMD time wording remains unnormalized; estimated dates with no verified clock time remain date-only.

To export, click **Select events**, check several events, then click **Download .ics**. **Select shown** selects the current filtered list or calendar month; **Clear selection** resets it. Selected events remain selected across views, months, filters and timezone changes. A multi-day conference shown on several calendar dates is selected and exported once. The website remains read-only: selection/export does not edit the public dataset.

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

Dates and optional `endDate` use `YYYY-MM-DD` in the published event calendar. Full conference ranges and separately scheduled keynotes are distinct events. Published clock times are normalized to UTC instants with an IANA source timezone. The client converts those instants and their dates to the selected timezone, accounting for daylight saving. Hong Kong is the default, with an explicit Browser timezone option and common cities. Date-only entries retain their published source date; a clock time or day rollover is never invented for them. The today indicator follows the selected timezone. Past scheduled dates stay in their historical month and display “Past date”; they cannot appear in the undated radar. The October 14 ASML results, October 14 Anthropic investor day, October 12–15 OCP edition and October 6 Marvell investor day are dated entries. Future GTC editions, CEO keynotes, Ignite and re:Invent use published schedules.

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

There is no live licensed Bloomberg or Refinitiv API connection. Bloomberg reporting is attributed through public reporting; FT Markets' public forecasts page credits LSEG for data. Neither is represented as authenticated terminal access. Visitors cannot edit events. Manual changes remain available through Codex; the weekly workflow below is the separately authorized automated maintenance path.

## Weekly overnight research and email

`.github/workflows/weekly-refresh.yml` schedules research every **Sunday at 02:00 Hong Kong time**, the night from Saturday to Sunday (`0 18 * * 6` in UTC). GitHub may delay scheduled jobs; this is a scheduled start, not a guaranteed completion time. Scheduled workflows run only from the repository's default branch. GitHub may disable schedules in inactive public repositories after 60 days; check the Actions page if updates stop. Successful weekly data commits normally keep this repository active.

The researcher and independent reviewer both use **GPT-6 Astra (`gpt-6-astra`) with `reasoning.effort: max`**, OpenAI's current highest-capability general model and its highest documented reasoning setting. The policy is in `config/weekly-refresh.json`; no cheaper or lower-reasoning fallback is used. Model access, token usage and live web-search calls are billed to the supplied OpenAI API account, separately from ChatGPT/Codex subscriptions. Future model upgrades should be explicit policy changes after checking availability and capabilities.

The workflow automatically researches, commits, pushes and publishes each approved weekly update; there is no manual weekly publishing step. **Automated research and publication require `OPENAI_API_KEY` to be configured once and a successful live run.** Email delivery is independent: missing or invalid email settings cannot block website publication. This workflow does not reuse this chat's authentication. Add the following in [repository Actions secrets](https://github.com/Hangyul-Son/global-tech-team-features/settings/secrets/actions):

| Name | Value |
| --- | --- |
| `OPENAI_API_KEY` | An [OpenAI API key](https://platform.openai.com/api-keys) with billing and access to `gpt-6-astra`, background Responses and web search. |
| `RESEND_API_KEY` | For email only: a [Resend sending API key](https://resend.com/api-keys). |
| `GLOBAL_TECH_EMAIL_FROM` | For email only: a sender authorized by Resend, such as `Global Tech <calendar@your-verified-domain.com>`. This may instead be an Actions variable with the same name. Receiving email at CLSA does not authorize sending as `@clsa.com`. |

Never paste keys into chat, commit them, or put them in public `data/` files. Resend requires an authorized sender; its development sender has recipient restrictions. Verify sender/domain setup in Resend. The destination is fixed in code to **hangyul.son@clsa.com** and cannot be changed by model output or a web page.

After adding configuration, open [Weekly Global Tech refresh in Actions](https://github.com/Hangyul-Son/global-tech-team-features/actions/workflows/weekly-refresh.yml), choose **Run workflow** on the default branch, and verify research and publish succeed. If email is configured, verify the email job succeeds and the note arrives. Provider acceptance does not prove inbox delivery; spam and corporate mail filtering can affect receipt. Once tested, the same workflow researches and publishes every week without any manual commit/push/deploy, open browser or running cloud development machine. Missing email settings fail only the notification job.

Each run:

1. Checks all 32 tracked companies in four research groups, plus a separate industry-conference search. It searches durable IR/news/organizer indexes and public estimate providers, rather than only revisiting old press releases. Research covers the recent 14 days and next 210 days, with separately labeled longer IPO windows.
2. Requires every proposed source to have a contextual quotation from actual web research. Code independently retrieves and matches that quotation; first-party domains are required for official confirmations. Blocked, unreadable, redirected or conflicting evidence is held for review. Web pages and the model have no git, deployment or email tools.
3. Runs a separate maximum-reasoning review of every proposal and every tracked company. Unsupported proposals are excluded. Published estimates stay tentative; times require UTC, an IANA source timezone and explicit clock evidence. Past records, stable event identities, the company universe and the original 12 coverage flags are preserved. No date is fabricated to fill a research gap.
4. Validates the final dataset and application, protects intervening manual changes, commits only the two public data files, and deploys directly to Pages. A `GITHUB_TOKEN` commit does not trigger another push workflow, so direct deployment is intentional. Older queued snapshots cannot replace newer repository changes.
5. Uses the actual Pages deployment URL (including after a repository rename), fetches the public dataset and compares its SHA-256 to the approved artifact before reporting publication. Then it emails the actual result, new/changed events with source links, and exceptions. Failed or blocked runs send a failure/blocked note when email credentials work; they never claim a successful update. Email errors fail the notification job visibly without preventing website publication.

Research reports, reviewed proposals, usage and exceptions are retained as GitHub run artifacts for 30 days. They are not published as website files. Only evidence actually approved gets a new verification timestamp; partial reviews retain the previous full-review timestamp. No model can guarantee error-free or exhaustive coverage, so unresolved items remain visible in the report.

Offline checks for this automation are part of the normal Python test command. They mock API/email/network calls and do not incur API charges. To inspect an example note without sending:

```sh
python3 scripts/send_weekly_email.py --result blocked --dry-run
```

## Public hosting

The site can be served worldwide without an application server, database or visitor login. It is prepared for either hosting option:

- **GitHub Pages:** the existing `deploy-pages.yml` validates and builds the static artifact, then deploys on pushes to `main` or `claude/build-tech-finance-site-HRNbI`, or manual workflow dispatch. Configure the repository's Pages source to **GitHub Actions**. The redundant Jekyll deployment was removed because the site has no Jekyll dependency.
- **Netlify:** connect this repository; `netlify.toml` runs the static copy build and publishes `_site`.

The public calendar is deployed through GitHub Pages at https://hangyul-son.github.io/global-tech-team-features/. Source updates require a repository change and successful deployment; the weekly workflow performs both automatically. Deployments also ensure the Pages source is GitHub Actions where the token permits it, so an unrelated branch does not replace the calendar. If GitHub refuses that setting change, a repository administrator must select **Settings > Pages > Source > GitHub Actions** once. The cloud development environment's Publish action snapshots the development machine; it does not publish this website to GitHub Pages or Netlify.
