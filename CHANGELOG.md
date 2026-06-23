# Changelog

This project follows a lightweight changelog format. Dates are intentionally omitted for the initial public import because the repository is being opened after a period of local development.

## Initial Public Release

### Foundation

- Built a full-stack research workspace with FastAPI, Next.js, TypeScript and Tailwind CSS.
- Added fund search, ranking, detail views, comparison, watchlist management and AI-assisted chat.
- Integrated AKShare as the primary public market data source.
- Added SQLite persistence for local development and Redis-backed caching for runtime data.

### Data Reliability

- Added separate cache TTLs for fund NAV, stock quotes, fund rankings, fund holdings and realtime estimates.
- Improved batch quote loading to reduce duplicate requests and stabilize portfolio screens.
- Added fallback behavior for data-source errors, including stale successful snapshots where appropriate.
- Added explicit warning fields so downstream UI can distinguish official NAV, imported snapshots and realtime estimates.

### Realtime Fund Estimation

- Added single-fund and batch realtime estimate APIs.
- Estimated fund movement from disclosed holdings and live stock quotes.
- Returned contribution breakdowns, coverage ratios, confidence labels and data-quality warnings.
- Marked low-coverage estimates as partial or unavailable instead of presenting them as complete results.

### Portfolio Workflow

- Added a page-level portfolio overview API that returns preferences, holdings, watchlist items, exposure, alerts and strategy in one response.
- Added quick-loading mode so the portfolio page can render local snapshots first and refresh live data afterward.
- Added estimated daily return, estimated NAV, estimate confidence and warning fields to portfolio items.
- Improved portfolio detail handling with cached fund detail lookups and an isolated modal view.

### Frontend Experience

- Added lightweight client-side response caching and request de-duplication.
- Improved dashboard interactions for selected funds, sectors and chat history previews.
- Added realtime estimate cards to fund detail views.
- Improved API error formatting for validation and data-source failures.
- Refined theme and layout behavior across dashboard, fund, sector and portfolio pages.

### Open Source Readiness

- Rewrote the README around a clear open-source positioning and local setup flow.
- Added architecture notes, roadmap, disclaimer, contribution guide, security policy and MIT license.
- Removed local logs, research drafts and implementation notes from the public repository.
- Hardened `.gitignore`, `.editorconfig` and `.gitattributes` to reduce accidental noise in future contributions.
