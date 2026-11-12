# Write-up: report and brief

`report.html` is the full report and `brief.html` the short brief. Both are single self-contained files: open them in a browser.

## How the pages are built

- `report_template.html`, `brief_template.html`: the page sources. Each has one `__DATA__` slot.
- `report_data.json`, `brief_data.json`: the numbers the charts and number slots read. `python3 writeup/build_data.py OUT.json` collects them from the committed results (no new analysis), including the report's `ladder` key from `results/dose8b/analysis/` and `results/scale32b_s3/analysis/followup.json`.
- `build.py`: template plus data gives `report.html` and `brief.html`.
- Numbers written into the prose (not read from the data files) are traced one by one to a results file in `number_trace.md`.

## Checks run before each change

- `./snap.sh TAG` builds both pages, dumps their rendered text (`rtext.js`, Playwright) and writes a list of every number shown. Diffing two snapshots (`diff <(sort a) <(sort b)`) shows exactly which numbers an edit added or removed; each one must be in `number_trace.md`.
- `./render_text.sh`: writes `rendered/report.txt` and `rendered/brief.txt` (the rendered text, first line `sha256 <hash of the .html>`). `tests/test_inventory.py` matches the results inventory's anchors against these files and fails if the hash is stale, so rerun it after every rebuild.
- `node shots.js`: desktop and phone, light and dark, checking for horizontal overflow, broken anchors and script errors.
- `node plain.js report.html OUT`: pulls out the "In plain words" boxes for a non-specialist read.
