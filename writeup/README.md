# Write-up: report and brief

`report.html` is the full report and `brief.html` the two-page brief. Both are single self-contained files: open them in a browser. Both are still drafts for review.

## How the pages are built

- `report_template.html`, `brief_template.html`: the page sources. Each has one `__DATA__` slot.
- `report_data.json`, `brief_data.json`: the numbers the charts and number slots read. `python3 writeup/build_data.py OUT.json` collects them from the committed results (no new analysis). The report's `ladder` key comes from `results/dose8b/analysis/dose.json` and was spliced in separately.
- `build.py`: template plus data gives `report.html` and `brief.html`.
- Numbers written into the prose (not read from the data files) are traced one by one to a results file in `number_trace.md`.

## Checks run before each change

- `./snap.sh TAG` builds both pages, dumps their rendered text (`rtext.js`, Playwright) and writes a list of every number shown. Diffing two snapshots (`diff <(sort a) <(sort b)`) shows exactly which numbers an edit added or removed; each one must be in `number_trace.md`.
- `python3 deai_lint.py report.html brief.html`: a style lint (0 flags).
- `node shots.js`: desktop and phone, light and dark, checking for horizontal overflow, broken anchors and script errors.
- `node plain.js report.html OUT`: pulls out the "In plain words" boxes for a non-specialist read.
