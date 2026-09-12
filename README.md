# Hiring Demand Radar — CareersNetwork

Internal dashboard of U.S. hiring-demand momentum by sales vertical.
Data: Indeed Hiring Lab (CC-BY). Rebuilds and redeploys itself weekly.

## Files
- `index.html` — the dashboard (self-contained; this is what Netlify serves)
- `hiring_demand_engine.py` — pulls fresh Indeed data, rebuilds index.html
- `dashboard_template.html` — the design template the engine fills in
- `vertical_table.csv` — plain data table (sanity-check / Excel)
- `.github/workflows/weekly-refresh.yml` — the Monday auto-refresh

## How the automation works
Every Monday, GitHub re-runs the engine (fresh Indeed data) and deploys the
new index.html to Netlify. Zero manual steps. You can also trigger it anytime
from the repo's **Actions** tab → "Weekly hiring-demand refresh" → **Run workflow**.

## One-time setup (do this once)
1. Create a Netlify site (drag this folder to app.netlify.com → Add new site → Deploy manually).
2. Get a Netlify **auth token**: Netlify → User settings → Applications → Personal access tokens → New.
3. Get your Netlify **Site ID**: your site → Site configuration → General → Site ID.
4. In the GitHub repo → Settings → Secrets and variables → Actions → New repository secret, add:
   - `NETLIFY_AUTH_TOKEN` = the token from step 2
   - `NETLIFY_SITE_ID` = the Site ID from step 3
That's it. The Monday job now runs on its own.

## Manual rebuild (optional, if you ever want to run it yourself)
    pip install pandas
    python hiring_demand_engine.py
Then re-deploy index.html to Netlify.
