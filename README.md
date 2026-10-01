# AllDataSI

Source for www.alldatasi.com, served by GitHub Pages.

## What's here

| Path | What it is |
|---|---|
| `index.html` | Home page: intro, list of posts, latest filings |
| `posts/<slug>/index.html` | One folder per blog post |
| `filings/index.html` | AI Cloud Filings Desk dashboard |
| `filings/data/filings.json` | Filing data, rewritten every morning by the updater |
| `scripts/update_filings.py` | Pulls filings from SEC EDGAR (standard library only) |
| `scripts/companies.json` | Which companies the dashboard tracks |
| `.github/workflows/update-filings.yml` | Runs the updater daily and commits the new data |
| `assets/site.css` | Shared fonts, colors, header and footer |
| `CNAME` | Tells GitHub Pages to serve the site at www.alldatasi.com |

## Day-to-day

- **New post:** copy `posts/nscale-hype-cycle/` to a new folder, edit the text, and add a link card for it on `index.html` (newest first).
- **Track another company:** add a line to `scripts/companies.json`. Pre-IPO companies with no ticker also need `"cik"`, from sec.gov/edgar/search.
- **Refresh filings now:** Actions tab → Update SEC filings → Run workflow.
- **If the daily run fails:** open the failed run on the Actions tab. The usual causes are a missing `SEC_CONTACT_EMAIL` secret, or the workflow lacking permission to push (Settings → Actions → General → Workflow permissions → Read and write).

## DNS (at Atom)

| Type | Host | Value |
|---|---|---|
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |
| CNAME | www | YOUR-GITHUB-USERNAME.github.io |
