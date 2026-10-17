# Submission documents

| File | What it is |
|---|---|
| `ScholarTrack_Project_Report.docx` | Full project report: 10 chapters, 13 tables, 3 figures |
| `ScholarTrack_Presentation.pptx` | 8-slide pitch deck, with speaker notes on every slide |
| `figures/` | Architecture, ingest-pipeline and ER diagrams (PNG, 200 dpi) |

## Before submitting

The report's title page, certificate and declaration contain placeholders in
square brackets — student name, enrolment number, guide, department, institute.
Fill those in.

The table of contents is a Word field and is built from the heading styles. It
renders blank until refreshed: open the document and press Ctrl+A then F9, or
use References › Update Table.

## Regenerating

The documents are generated, not hand-edited, so a change to the project can be
reflected by re-running the generators rather than editing the files:

```bash
python docs/figures.py     # redraw the three diagrams
node docs/report.js        # rebuild the .docx
node docs/deck.js          # rebuild the .pptx
```

`report.js` and `deck.js` need `docx` and `pptxgenjs` respectively
(`npm install docx pptxgenjs`), and `figures.py` needs `matplotlib`. The
generators read the figures from the directory they are run from, so run them
from `docs/`.

Every figure quoted in these documents was measured from the repository or from
a live refresh on 17 October 2026 — scholarship counts, test counts and lines of
code included. If the project changes, re-measure rather than editing the prose.
