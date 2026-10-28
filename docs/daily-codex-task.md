# Update and publish Global Tech daily

This is the saved specification for a **native scheduled Codex task**. Saving this file does not register a scheduled task. No native task was created by this repository change; creation must be confirmed in the platform's Scheduled/Automations controls.

## Task settings

- Name: **Update and publish Global Tech daily**
- Frequency: every day, **02:00 Asia/Hong_Kong** (overnight, including weekends)
- Equivalent UTC time: **18:00 on the preceding UTC date**, every day
- Recurrence, if the task editor accepts an RRULE: `FREQ=DAILY;BYHOUR=2;BYMINUTE=0;BYSECOND=0`, with timezone `Asia/Hong_Kong`
- Repository: `Hangyul-Son/global-tech-team-features`
- Branch: resolve and use the repository's current default branch on every run
- Model: the most capable model available in the account's native Codex scheduler, selected explicitly in the task controls. As of October 28, 2026, OpenAI's model documentation names **Astra (`gpt-6-astra`)** as the most capable model for complex code, apps and research; choose it if offered. A model offered in the ChatGPT conversation picker is not necessarily available to repository automations.
- Reasoning: **Ultra**, if supported by that model and scheduler; otherwise the highest setting actually offered, with the limitation disclosed. Select it explicitly in the task controls.
- Runtime: a Codex task with repository read/write access, public-web research, command execution and GitHub authentication. Use a cloud runtime if offered; a local desktop task requires the computer and app to stay running.
- Notification: the platform's task-completion notification. Enable native email delivery to `hangyul.son@clsa.com` if the platform supports that destination. No external email service is required by this specification.

This daily specification supersedes the previous Sunday-only request. Update any existing Global Tech schedule instead of creating overlapping daily and weekly tasks.

The model, reasoning and notification settings must be selected and verified in the actual scheduler. Prompt wording does not configure those controls or automatically upgrade a pinned model when a stronger one becomes available. Review the selected model when the platform offers a new model; never claim that a different or unobservable model meets the strongest-model requirement. No OpenAI API key or GitHub research cron is needed. Public-site publishing remains handled by `.github/workflows/deploy-pages.yml` after Codex pushes the reviewed changes.

## Task prompt

Copy the following complete instructions into the native task, or attach this file as durable task context:

```text
Update and publish Global Tech every day at 02:00 Asia/Hong_Kong using this platform's native Codex research and repository tools. Use the repository Hangyul-Son/global-tech-team-features. Resolve its current default branch and actual GitHub Pages URL each run. Use the most capable model and highest reasoning setting available to this native task, configured in the scheduler. Report the exact configured model and reasoning level when observable; if they are unavailable, do not infer them from this prompt or claim that the strongest model was used. Do not run scripts/weekly_refresh.py or scripts/send_weekly_email.py, call a separate model API, request an OpenAI API key, or create a GitHub/shell cron job.

This is an authorized recurring maintenance and publication task: research events, review and edit the calendar data, commit and push approved changes, wait for GitHub Pages deployment, verify the live site, and return a completion report. Do not stop for routine publishing confirmation. Respect repository rules and platform permissions; report an access blocker without claiming publication if the required access is unavailable.

1. Start from the latest default branch. Preserve existing user changes and historical events. Inspect repository instructions, README.md, data/events.json, data/source-checks.json, and the deployment workflow. Use Hong Kong time for the research date and report. The public website stays read-only.

2. Research EVERY company currently tracked in data/events.json, plus important industry-wide AI, cloud and semiconductor events. Preserve exactly these original 12 starred coverage companies: TSM, NVDA, AMD, AVGO, MRVL, AAPL, MSFT, ORCL, CRM, NOW, ADBE and WDAY. All other tracked companies remain in research scope with equal company-level importance. Do not promote other companies into starred coverage, create many speculative watch records for one company, or fill missing dates merely to balance the display. Keep related undated monitoring topics concise; the watchlist groups them into one alphabetically ordered card per company. Preserve the site title Global Tech, compact calendar/list layout, timezone controls and Outlook ICS export.

3. Check the previous 14 days and next 210 days for earnings releases/calls, investor and capital-markets days, major product/technology keynotes, conferences and material AI/cloud-capex catalysts. Track major editions of NVIDIA GTC, OCP, Microsoft Ignite, AWS re:Invent, Oracle AI World, Cloudflare Connect and MIT AI Conference. Search fresh official company IR/news/event indexes and organizer schedules, not only previously cited press releases. Include explicitly sourced longer IPO timing windows. Do not confuse past editions, publication dates, fiscal periods, investor days or IPO marketing with a future event/listing date. Skip dividends and routine corporate actions unless separately material. Keep Oracle AI World as a single conference entry: include its keynote/session details and source links in that event brief rather than recreating separate Oracle keynote cards.

4. Every event must expose source links and a clear evidence basis. Check official company/organizer sources first; use explicitly published estimates from named providers such as MarketBeat, Stock Analysis and FT/LSEG where primary dates are unannounced. Attributable public media reporting may support a reported date/window. Never imply licensed Bloomberg/Refinitiv access or bypass access restrictions. The optional python3 scripts/refresh_events.py command stages public evidence; it does not verify or update event dates by itself.

5. Verify that source text explicitly supports the company/event identity, actual event date, date status and any clock time or window. Read the linked evidence rather than relying on search snippets or HTTP 200. Confirm dates only from first-party evidence. Provider estimates stay estimated, with null verifiedAt. Earnings need actual published day-level dates; do not extrapolate reporting cadence. When no next date is sourced, report the gap instead of fabricating one. Preserve source disagreements in dateConflict and basis. IPO windows must remain timingWindow entries with date/endDate null until an exact date is supported.

6. Distinguish the release date/time from the conference call. Normalize a clock time only when explicitly sourced, using UTC RFC3339 startAt/endAt values and the correct IANA sourceTimeZone/DST rules. Use canonical YYYY-MM-DD source dates. Do not invent midnight, a duration, a time for an earnings estimate, or a date rollover for a date-only event. Confirmed events retain solid borders and unconfirmed dates/windows dotted borders. Stars indicate coverage only.

7. Perform a separate skeptical review pass against the sources before editing the final dataset. Verify every changed field, event edition, status and time. Preserve stable event IDs when an existing reporting date changes; add distinct IDs only for genuinely new periods/events. Check the final merged dataset for duplicate reporting periods and conflicting dates. Preserve historical records and the company universe. Update sourceCheckedAt/verifiedAt/timeCheckedAt only for facts actually rechecked. Advance asOf/lastSuccessfulRefresh only when a complete review supports them; keep the previous full-review timestamp if material research remains incomplete. Hold unsupported changes and list the exceptions.

8. Run the repository checks:
   python3 -m unittest discover -s tests -v
   node --check js/calendar-utils.js
   node --check js/events.js
   node --test tests/calendar-utils.test.cjs
   python3 scripts/build_site.py
   Run browser checks when UI behavior changes, using README.md instructions. Do not weaken checks to publish unsupported data. Do not make unrelated UI, script or company-universe changes as part of a routine data refresh.

9. Inspect the diff, commit only the reviewed calendar/source-data changes, and push to the current default branch using the platform's existing GitHub authentication. Reconcile any intervening user commits without overwriting them. Avoid overlapping refreshes; if a prior daily run is still active, report the overlap instead of racing it or overwriting its work. This push triggers .github/workflows/deploy-pages.yml; no manual daily deployment step or external-model credential is required. Wait for the deployment of this exact commit to succeed. If there are no data changes, check the current published dataset and report that no changes were needed. A failed or incomplete research run must not publish invented dates or advance full-review freshness stamps.

10. Obtain the actual current Pages URL from the deployment or repository Pages metadata; do not assume a repository slug will never change. Run python3 scripts/verify_deployment.py --site-url ACTUAL_PAGES_URL to confirm the public dataset matches the reviewed local bytes. Check that the public title is Global Tech and the calendar loads. Do not report success before the matching deployment and live verification succeed. If another branch replaces the site or an access check fails, report that clearly rather than claiming the update is live.

11. Return a concise completion report with the Hong Kong review date/time, live website link, meaningful additions/corrections and source links, deployment result, unresolved coverage/source issues, and the configured model/reasoning if observable. Report failures as well as successful or no-change runs. Use the platform's native task notification. Send an email heads-up to hangyul.son@clsa.com only if native delivery to that address is supported and configured; never claim an email was sent without evidence. Notification delivery problems must not block publication or cause an external email API fallback.
```

## Activation and verification

Open **Scheduled** in ChatGPT/Codex and create or update the task with this repository and prompt. Confirm that it appears as active with the daily 02:00 Hong Kong schedule, next run time, chosen model/reasoning and required repository tools. Disable any superseded weekly duplicate. Run it once from that interface and check its commit and matching Pages deployment (or verified no-change report), public-site verification and notification before relying on the daily recurrence. A saved specification, successful manual publication or active GitHub Pages workflow is not proof that a native daily research task is scheduled.

Native scheduling is described in [OpenAI's scheduled-task documentation](https://developers.openai.com/codex/app/automations). Availability and repository/tool access depend on the task runtime and workspace. This chat cannot register a native task unless a task-creation tool is actually exposed; a repository file is not a substitute for a registered schedule.

OpenAI's [model documentation](https://learn.chatgpt.com/docs/models) identifies Astra and describes Ultra. The scheduling documentation allows explicit model/reasoning selection but does not guarantee those options in every account. Native email/push controls are under **Settings > Notifications**; see [ChatGPT scheduled-task notifications](https://help.openai.com/en/articles/10291617-scheduled-tasks-in-chatgpt). An arbitrary recipient address is not guaranteed.
