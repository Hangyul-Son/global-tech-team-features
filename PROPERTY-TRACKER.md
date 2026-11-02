# Hong Kong Home Lens

Public tracker: https://hangyul-son.github.io/global-tech-team-features/hong-kong-property/

The existing Global Tech calendar stays at the site root. The property dashboard and public datasets live only under `hong-kong-property/`.

## Coverage

- Interactive map for 24 representative estates across all 18 administrative districts, focused on Taikoo Shing, Park Avenue (Olympic), and Park Central (Tseung Kwan O).
- Sale advertisements from the defined 28Hse Taikoo Shing, Olympic, and TKO central search regions. All expected provider pages are checked, with counts and per-source failures exposed. Ads are not unique physical flats; availability is unconfirmed. Bedrooms and unknown numeric fields remain explicit. No whole-market completeness claim.
- Actual quarterly estate sale-price proxy observations and transaction counts. Five-year comparisons use matching completed quarters and require at least ten transactions at both endpoints. Current-quarter partial data is separate. No invented district rental history.
- Official RVD monthly territory-wide purchase/rent indexes, dated ECB HKD/KRW reference rate, and saleable area conversions: sq ft / m² / 평.

## Refresh and alert

The existing Pages workflow runs Mondays 08:15 Asia/Hong_Kong, or manually with `refresh_property=true`. A push commit containing `[refresh-property]` also runs the updater for initial unattended verification. `scripts/refresh_property.py` uses standard-library source adapters. It updates only four property JSON files, retains dated last-good data on failures, and reports new/missing source ad IDs and asking-price changes without treating incomplete pagination as removals.

The same workflow commits data and deploys the updated checkout, avoiding reliance on GITHUB_TOKEN pushes triggering a second workflow. Existing calendar validation and deployment checks remain. `scripts/verify_property.py` compares all four public dataset hashes with the checkout. A separate ChatGPT task delivers the user's weekly brief; it is not a browser notification or a guaranteed email service.

The original 90-day estate summaries and example unit observations retain their own historical dates until explicitly reverified. New ad observations, quarterly series, official indexes and FX do not silently overwrite those scopes. Currency is stored in HKD and areas in saleable sq ft. Shortlists and imported observations stay in each visitor's browser localStorage and are not shared.

## Validation

`python3 scripts/refresh_property.py --offline-check`

Frontend syntax checks plus Chromium desktop/mobile checks cover currency and area display, focus maps, five-year history selection, listing filtering/pagination, and saved source ads. Data checks cover complete source pagination, unique source IDs, target-fit flags, exact asking price/area ratios, partial quarters, weak endpoint samples, source dates, and refresh retention.

Leaflet is locally hosted under `vendor/`, with its license. Street tiles require external OpenStreetMap access; the local public-domain Natural Earth coastline remains available if tiles fail. Attribution and coordinate sources are shown in the dashboard.

### Observed automated access limit

The first GitHub-hosted refresh on 2 November 2026 successfully fetched ECB and RVD data, but 28Hse returned HTTP403 for sale search pages and 23 of the24 estate trend pages. The writer retained the verified initial observations and their dates; the public status is partial, not a fresh source check. The dashboard surfaces this limitation prominently. Weekly runs and the separate ChatGPT alert continue to report source status. Do not bypass restrictions, forge source freshness, or infer zero/new/missing ads from failed coverage. A reliable whole-market live inventory would require an authorised provider feed; source advertisements never prove physical-flat availability.
