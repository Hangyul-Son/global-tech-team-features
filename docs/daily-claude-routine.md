# Global Tech · daily 3 a.m. routine and email brief

This is the working specification for the **Claude Code scheduled task** that keeps the Global Tech calendar current and emails the team brief. It replaces the never-registered native Codex task in [daily-codex-task.md](daily-codex-task.md).

## Schedule and delivery

| Setting | Value |
| --- | --- |
| Scheduled task | **Global Tech 3am daily brief** (Claude Code on the web, fresh cloud session each run) |
| Start time | **02:37 Asia/Hong_Kong every day**, including weekends (18:37 UTC the previous day). It starts shortly before 3 a.m. so the research is finished and the email is waiting around 3 a.m.; a run usually takes 30–60 minutes. |
| Repository | `Hangyul-Son/global-tech-team-features`, default branch `claude/build-tech-finance-site-HRNbI` (GitHub Pages deploys from it) |
| Email | `scripts/daily_brief.py` renders the brief; the **Gmail connector** sends it from the owner's Gmail to **hangyul.son@clsa.com** (fixed recipient). Resend is an optional fallback. |
| Email access | The Gmail connector (claude.ai → Settings → Connectors) is attached to the scheduled task. If Gmail is disconnected, the scheduled task must be recreated with it after reconnecting. Optional fallback: a Resend API key saved as a network secret for `api.resend.com` on the **global-tech-team-features** environment. |
| Sender | The owner's connected Gmail account. (Resend fallback: `Global Tech <onboarding@resend.dev>` unless `GLOBAL_TECH_EMAIL_FROM` is set; that shared sender only delivers to the Resend account owner.) |

The schedule lives in Claude (claude.ai → Code → scheduled tasks), not in GitHub Actions or a shell cron. Pausing, rescheduling or deleting it is done there.

## What the email contains

`scripts/daily_brief.py` builds the brief from the reviewed `data/events.json`, in Hong Kong time, in the same conventions as the website:

1. **What's going on**: developments found in this morning's research (results released, material news, schedule changes), with source links.
2. **Today**: everything dated today in Hong Kong, including conferences in progress.
3. **Next 7 days**: the following seven days.
4. **Next 30 days (days 8–30)**: the rest of the month, without repeating the 7-day items.
5. **Calendar changes in this run** and **Exceptions / open items**.

Events involving the 12 coverage companies (TSM, NVDA, AMD, AVGO, MRVL, AAPL, MSFT, ORCL, CRM, NOW, ADBE, WDAY) are starred **★** and highlighted, and each window opens with a one-line coverage digest. Type colours, confirmed (solid) versus unconfirmed (dotted) styling, Hong Kong times with the source-zone time alongside, and "no invented clock times" follow the website.

Preview without sending:

```sh
python3 scripts/daily_brief.py --result unchanged --dry-run --html-out /tmp/brief.html --payload-out /tmp/payload.json
```

## Routine prompt

The scheduled task's prompt points to this section; editing it here changes the next run.

```text
You are the Global Tech daily 3 a.m. (Hong Kong) research-and-brief routine. This is an authorized, recurring task from the repository owner: research, update and publish the calendar, then email the brief. Do not stop for routine confirmations.

0. Setup
- Work in the repository Hangyul-Son/global-tech-team-features. If it is not checked out, attach it with add_repo (access: push) and clone it.
- Check out the default branch claude/build-tech-finance-site-HRNbI and pull the latest. The owner authorizes committing and pushing reviewed calendar data to this branch (it is what GitHub Pages publishes). Do not push anywhere else and do not force-push.
- Record the Hong Kong date/time (TZ=Asia/Hong_Kong). Read README.md (data rules), data/events.json, config/weekly-refresh.json (research groups) and this file.

1. Research (what happened, what is coming)
- Look back ~36 hours: results actually released, events that took place, material news for tracked companies (guidance, M&A, CEO changes, financing, IPO/S-1 milestones, launches), and schedule changes.
- Look ahead: verify every event in the next 30 days, coverage companies first, then search for newly announced events through the next 210 days (earnings dates/times, investor and broker conferences, investor days, major keynotes and industry conferences such as GTC, OCP, Ignite, re:Invent, CES, Computex).
- Use up to 4 parallel read-only research subagents, one per researchGroup in config/weekly-refresh.json, each returning findings with exact URLs and the verbatim supporting sentence. Prefer official IR/newsroom/organizer pages, then named provider estimates (MarketBeat, Stock Analysis, FT/LSEG pages), then attributable media reports. Read the pages; do not rely on search snippets for dates and times.

2. Edit data/events.json following README.md exactly
- Status semantics (confirmed / estimated / reported / unannounced), sources[], basis, sourceCheckedAt, verifiedAt only for first-party confirmations, startAt/endAt in UTC only for published clock times with the correct sourceTimeZone, timingWindow for approximate windows, dateConflict for disagreements.
- Keep stable ids when a date changes; never duplicate a reporting period; never invent dates, times or durations; keep the 12 starred coverage companies unchanged; preserve history.
- When results are released, update that event's basis with the headline facts and source rather than adding a duplicate.
- Update lastAttempt and verificationNote to describe this run honestly. Advance lastSuccessfulRefresh only after a complete review of every tracked company.
- Do a separate skeptical review pass of every changed field against its source before finishing.

3. Check
  python3 -m unittest discover -s tests -v
  node --check js/calendar-utils.js && node --check js/events.js
  node --test tests/calendar-utils.test.cjs
  python3 scripts/build_site.py
Fix data problems; never weaken tests to publish.

4. Publish
- If data changed: commit with a clear message ("Daily Global Tech update · YYYY-MM-DD HKT"), fetch and merge any newer commits on the default branch (never overwrite others' work), push, then watch the "Deploy to GitHub Pages" workflow run for that commit with the GitHub tools until it succeeds or fails. If hangyul-son.github.io is reachable, also run python3 scripts/verify_deployment.py --site-url https://hangyul-son.github.io/global-tech-team-features/.
- Result for the email: published (deploy succeeded), unpublished (pushed but deploy failed or could not be checked), unchanged (no data changes needed), failed or blocked (research or push could not be completed; nothing invented was published).

5. Email the brief (always, even after a failure)
- Write a run report JSON to .daily-brief/report.json:
  {"summary": "...2-4 sentences: what happened and what matters today...",
   "developments": [{"title", "companies": [ids], "date", "detail", "sourceUrl"}],
   "added": [{"title", "date", "sourceUrl"}], "updated": [{"title", "date", "detail", "sourceUrl"}],
   "warnings": ["blocked sources, unverified items, gaps, deployment problems"]}
- Render (reads the dataset as it now stands, so do this after the data edit):
  python3 scripts/daily_brief.py --result <result> --report .daily-brief/report.json --dry-run --payload-out .daily-brief/payload.json
- Send with the Gmail connector (primary): call the Gmail send_message tool with to = ["hangyul.son@clsa.com"], subject = payload "subject", htmlBody = payload "html" exactly as rendered, body = payload "text". Success returns a Gmail message id.
- Fallback only if Gmail is unavailable or fails: python3 scripts/daily_brief.py --result <result> --report .daily-brief/report.json (Resend; needs a key saved for api.resend.com).
- If neither works, say "email not sent" and why in the final report. Never claim an email was sent without a Gmail message id or Resend id, and never send to any other address.
- Do not commit .daily-brief/.

6. Finish with a short report: Hong Kong run time, result, email status (message id or error), changes with sources, and open issues.
```

## Changing the routine

- Content and rules: edit the prompt above (or README.md) and push; the next run reads it.
- Time or pause: edit the scheduled task in Claude.
- Recipient: `RECIPIENT` in `scripts/daily_brief.py` is fixed on purpose so a run report cannot redirect mail.
- Email key: rotate it in the cloud environment's network secrets for `api.resend.com`.
