# Catalyst — technology earnings & events

A public, read-only research calendar for semiconductor, software and AI infrastructure catalysts. Calendar and list views share the same dataset and filters. Visitors can browse, filter and open source briefs; there are no write endpoints, event editors or credentials in the client.

## Run locally

Use the existing checkout. Cloud tasks are already isolated; do not create a worktree for setup.

```sh
cd /workspace/train-me-to-be-a-better-financial-analyst
python3 -m http.server 8000 --bind 127.0.0.1
```

Python 3.10+ is sufficient to serve, validate, build and refresh sources. There is no npm install or application build dependency. Node.js is used only for the optional JavaScript syntax check. Serve over HTTP; opening `index.html` directly does not support dataset fetching.

```sh
python3 -m unittest discover -s tests -v
node --check js/events.js
python3 scripts/build_site.py
```

The build writes ignored `_site/` assets. Existing finance research is preserved in `research.html`, and the Chinese learning application remains in `chinese.html`.

Optional browser checks use Python Playwright and `/usr/bin/chromium`, already available in the current cloud machine. With the server running:

```sh
python3 tests/browser_smoke.py
```

These checks exercise both views, priority filtering, source details, keyboard dismissal, empty states, safe text rendering, cross-month events and the mobile layout. They freeze the browser clock to the dataset's seed month. They do not validate external websites or licensed feeds.

## Coverage

The 12 priority companies are TSMC (TSM), NVIDIA, AMD, Broadcom, Marvell Technology, Apple, Microsoft, Oracle, Salesforce, ServiceNow, Adobe and Workday. Gold stars and borders identify their events in both views and event briefs. Multi-company events are priority events if at least one covered company participates.

The wider universe includes ASML, Lam Research, Samsung, SK hynix, Micron, MediaTek, Amazon, Alphabet, Meta and Anthropic. Hyperscaler earnings are included for capex context. GTC, OCP, re:Invent, Ignite, investor days and a potential Anthropic IPO are monitoring targets. An undated watch item does not assert that an event or IPO is scheduled. Dividends and routine corporate actions are not seeded.

## Data integrity and maintenance through Codex

`data/events.json` is the sole reviewed event store. Public visitors cannot modify it. Ask Codex to add, update or delete events in that file, then validate and deploy the change.

- **confirmed**: explicit event date, an official source, a review timestamp and evidence in `basis`. Never infer the event date from a news article's publication date or a fiscal quarter-end. Preserve source timezone labels and distinguish a release from an earnings call.
- **estimated**: a month-level, unverified editorial planning assumption based on customary reporting cadence, not a Bloomberg/Refinitiv consensus estimate. `window` is `YYYY-MM`; `date`, `time` and `verifiedAt` are null. An adjacent reporting month is possible. Estimates appear below the calendar, never on a fabricated day.
- **unannounced**: an undated monitoring target, not a scheduled event. Both `date` and `window` are null. An IPO watch is not a prediction of a listing date.

`date` and optional `endDate` use `YYYY-MM-DD` in the source's event calendar timezone. `time` is human-readable with the source timezone. The UI does not convert an unknown release time to the visitor's timezone. The “today” indicator uses Hong Kong time. Confirmed entries more than 14 days past verification display a recheck label; confirmation is not a guarantee that a schedule has not changed.

### Check official pages

```sh
python3 scripts/refresh_events.py
```

This dependency-free command checks the official sources listed in the dataset with TLS verification enabled, at most four concurrent requests and 20-second timeouts. It writes `data/source-checks.json`, including per-source retrieval status and nearby event/date text for review. It returns nonzero if no sources are retrieved. A partial run is explicitly partial. HTTP 200 does not prove a JavaScript calendar was rendered; zero candidates does not prove there are no events.

The command **does not automatically publish or confirm events**. Review candidates in Codex; open the official source, establish the actual event date and timezone, and update the reviewed event record. Replace the matching estimated earnings window, rather than adding a duplicate. Only set `verifiedAt` for events actually reviewed. Update `lastSuccessfulRefresh` and `verificationNote` to describe the reviewed scope; a source-check run alone must not update that field.

The initial source check retrieved 18 of 27 sources. Six events were reviewed from TSMC, AMD, Microsoft and Marvell IR pages on October 15, 2026. Some other sites return errors or require JavaScript. Remaining estimates and watch items have not been verified. The earnings planning horizon is October 2026–March 2027; extend it through Codex as coverage rolls forward. An empty later month is not a claim that no events will happen.

There is **no live Bloomberg or Refinitiv integration** and no scheduled background refresh. Those sources require licensed access and public redistribution rights; do not scrape their authenticated products or put keys in browser code. A future licensed feed should run server-side or in a private CI ingestion step, normalize dates into this schema and preserve provenance. No credentials are needed for the current public-source workflow.

## Public hosting

The site can be served worldwide without an application server, database or visitor login. It is prepared for either hosting option:

- **GitHub Pages:** the existing `deploy-pages.yml` validates and builds the static artifact, then deploys on pushes to `main` or `claude/build-tech-finance-site-HRNbI`, or manual workflow dispatch. Configure the repository's Pages source to **GitHub Actions**. The redundant Jekyll deployment was removed because the site has no Jekyll dependency.
- **Netlify:** connect this repository; `netlify.toml` runs the static copy build and publishes `_site`.

The public calendar is deployed through GitHub Pages at https://hangyul-son.github.io/train-me-to-be-a-better-financial-analyst/. Source updates require a repository change and successful deployment. The cloud development environment's Publish action snapshots the development machine; it does not publish this website to GitHub Pages or Netlify.
