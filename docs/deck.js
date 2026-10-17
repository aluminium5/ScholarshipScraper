/**
 * ScholarTrack — 8-slide project pitch deck.
 *
 * Built as a structured deck: a theme, named layouts, placeholders and sections,
 * so it can be restyled in one place and edited in PowerPoint without fighting it.
 */
const path = require('path');
const pptxgen = require('pptxgenjs');
const { applyTheme } = require(
  'C:/Users/Atharv/.claude/skills/synced/f2b0ee80-210e-4147-935f-a2c98aa6023b_7cfd962e-4e25-462a-bc98-6f59c96fc5f3/pptx/scripts/apply_theme.js',
);

const OUT = path.join(__dirname, 'ScholarTrack_Presentation.pptx');

/* Palette taken from the product itself: deep indigo for structure, teal for
   data sources, amber for deadline urgency — the thing the app is about. */
const THEME = {
  name: 'ScholarTrack',
  headFontFace: 'Cambria',
  bodyFontFace: 'Calibri',
  colors: {
    dk1: '0F172A', lt1: 'FFFFFF',
    dk2: '1E293B', lt2: 'F1F5F9',
    accent1: '4338CA', // indigo — primary
    accent2: '0F766E', // teal — sources / data
    accent3: 'B45309', // amber — deadlines, warnings
    accent4: '64748B', // slate — muted text
    accent5: '6D28D9', // violet — third source
    accent6: '047857', // green — results
    hlink: '4338CA', folHlink: '6D28D9',
  },
};

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE'; // 13.33 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = 'ScholarTrack — Scholarship Discovery and Application Tracker';
pres.author = 'ScholarTrack';
pres.company = 'ScholarTrack';

const C = pres.SchemeColor;
const W = 13.33;
const M = 0.62; // side margin

/* ------------------------------------------------------------------ layouts */
pres.defineSlideMaster({
  title: 'DARK_TITLE',
  background: { color: THEME.colors.dk1 },
  objects: [
    {
      placeholder: {
        options: {
          name: 'title', type: 'title', x: M, y: 2.35, w: W - 2 * M, h: 1.5,
          fontSize: 48, bold: true, color: C.background1, align: 'left',
        },
        text: '',
      },
    },
    {
      placeholder: {
        options: {
          name: 'body', type: 'body', x: M, y: 3.95, w: W - 2 * M, h: 1.5,
          fontSize: 18, color: 'CBD5E1', align: 'left',
        },
        text: '',
      },
    },
  ],
});

pres.defineSlideMaster({
  title: 'LIGHT_CONTENT',
  background: { color: C.background1 },
  objects: [
    {
      placeholder: {
        options: {
          name: 'title', type: 'title', x: M, y: 0.42, w: W - 2 * M, h: 0.78,
          fontSize: 32, bold: true, color: C.text1, align: 'left',
        },
        text: '',
      },
    },
    {
      placeholder: {
        options: {
          name: 'kicker', type: 'body', x: M, y: 1.16, w: W - 2 * M, h: 0.4,
          fontSize: 15, color: THEME.colors.accent4, align: 'left',
        },
        text: '',
      },
    },
  ],
  slideNumber: { x: W - 0.78, y: 6.95, w: 0.4, h: 0.3, fontSize: 10, color: 'B6C0CC', align: 'right' },
});

/* ------------------------------------------------------------------ helpers */
const txt = (slide, text, o) =>
  slide.addText(text, { isTextBox: true, margin: 0, ...o });

/** A soft card. No edge stripes: a tint plus a hairline only. */
const card = (slide, { x, y, w, h, fill = C.background2, line, name }) =>
  slide.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.1,
    fill: { color: fill },
    line: line ? { color: line, width: 1 } : { color: 'E2E8F0', width: 1 },
    objectName: name,
  });

/** A number in a filled circle, used as the repeated visual motif. */
const numberDot = (slide, { x, y, n, color, d = 0.46 }) => {
  slide.addShape(pres.ShapeType.ellipse, {
    x, y, w: d, h: d, fill: { color }, line: { color, width: 0 },
    objectName: `dot-${n}`,
  });
  txt(slide, String(n), {
    x, y, w: d, h: d, align: 'center', valign: 'middle',
    fontSize: 13, bold: true, color: 'FFFFFF',
  });
};

/** Large figure with a small label underneath. */
const stat = (slide, { x, y, w, value, label, color }) => {
  txt(slide, value, {
    x, y, w, h: 0.92, align: 'center', valign: 'bottom',
    fontSize: 54, bold: true, color,
  });
  txt(slide, label, {
    x, y: y + 0.95, w, h: 0.62, align: 'center', valign: 'top',
    fontSize: 13, color: THEME.colors.accent4,
  });
};

/* ---------------------------------------------------------------- 1. title */
pres.addSection({ title: 'Opening' });
{
  const s = pres.addSlide({ masterName: 'DARK_TITLE', sectionTitle: 'Opening' });

  txt(s, 'PROJECT PRESENTATION', {
    x: M, y: 1.55, w: 8, h: 0.34, fontSize: 13, bold: true,
    color: THEME.colors.accent2, charSpacing: 3,
  });
  s.addText('ScholarTrack', { placeholder: 'title' });
  s.addText(
    'Finding every open scholarship in one place, ordered by what closes first',
    { placeholder: 'body' },
  );

  // Three quiet facts, as the only ornament on the slide.
  const facts = [
    ['3', 'live portals'],
    ['58', 'open scholarships'],
    ['157', 'automated tests'],
  ];
  facts.forEach(([v, l], i) => {
    const x = M + i * 2.6;
    txt(s, v, {
      x, y: 5.52, w: 1.1, h: 0.6, fontSize: 30, bold: true,
      color: C.background1, align: 'left',
    });
    txt(s, l, {
      x, y: 6.12, w: 2.3, h: 0.4, fontSize: 12, color: '94A3B8', align: 'left',
    });
  });

  s.addNotes(
    'ScholarTrack aggregates open scholarships for Indian students from three ' +
    'live portals into one list ordered by the nearest deadline, stores the ' +
    'details students retype on every form, and tracks each application. ' +
    'Everything shown today runs against the real portals.',
  );
}

/* -------------------------------------------------------------- 2. problem */
pres.addSection({ title: 'Problem' });
{
  const s = pres.addSlide({ masterName: 'LIGHT_CONTENT', sectionTitle: 'Problem' });
  s.addText('Scholarships are scattered, and applying repeats itself', { placeholder: 'title' });
  s.addText('Two separate problems, both costing students awards they qualify for', { placeholder: 'kicker' });

  const cards = [
    {
      n: 1, color: THEME.colors.accent1,
      head: 'Discovery is fragmented',
      body: 'Central schemes sit on NSP, private ones on Buddy4Study, corporate CSR funds on Vidyasaarathi. No portal shows another\u2019s listings, and none orders by urgency \u2014 so the scholarship closing in three days is not shown before the one closing in three months.',
    },
    {
      n: 2, color: THEME.colors.accent3,
      head: 'Applying is repetitive',
      body: 'Every form asks for the same name, date of birth, category, income, marks, bank details and document list. Eight applications means retyping it eight times, and one mistyped IFSC or income figure can invalidate the application.',
    },
  ];

  cards.forEach((c, i) => {
    const x = M + i * 6.25;
    card(s, { x, y: 1.85, w: 5.85, h: 3.5, name: `problem-${c.n}` });
    numberDot(s, { x: x + 0.42, y: 2.2, n: c.n, color: c.color });
    txt(s, c.head, {
      x: x + 1.05, y: 2.22, w: 4.4, h: 0.45, fontSize: 20, bold: true, color: C.text1,
    });
    txt(s, c.body, {
      x: x + 0.42, y: 2.95, w: 5.0, h: 2.2, fontSize: 14, color: THEME.colors.accent4,
      lineSpacingMultiple: 1.25,
    });
  });

  txt(s, 'Deadlines are missed not because students are unaware of scholarships, but because the information is scattered and the effort of applying repeats.', {
    x: M, y: 5.65, w: W - 2 * M, h: 0.6, fontSize: 15, italic: true,
    color: THEME.colors.accent1,
  });

  s.addNotes(
    'Worth stressing: this is not an awareness problem. Students know scholarships ' +
    'exist. The cost is in finding which are open right now, and in the repetition ' +
    'of applying. ScholarTrack attacks both.',
  );
}

/* ------------------------------------------------------------- 3. solution */
pres.addSection({ title: 'Solution' });
{
  const s = pres.addSlide({ masterName: 'LIGHT_CONTENT', sectionTitle: 'Solution' });
  s.addText('One dashboard, ordered by what closes first', { placeholder: 'title' });
  s.addText('Four capabilities, each answering one part of the problem', { placeholder: 'kicker' });

  const rows = [
    ['Aggregate and rank', 'Three portals merged into one list, nearest deadline first, expired hidden. Refreshed automatically every day.', THEME.colors.accent2],
    ['Deep-link to the scholarship', 'Apply opens that scholarship\u2019s own page \u2014 never a portal home page. A record with no specific page is discarded, not published with a misleading link.', THEME.colors.accent1],
    ['Reusable portfolio', 'Personal, academic, family, bank, document and CV details stored once, with a copy button beside every field.', THEME.colors.accent5],
    ['Track every application', 'Saved \u2192 Applied \u2192 Under review \u2192 Awarded or Rejected. Pressing Apply records the scholarship automatically.', THEME.colors.accent6],
  ];

  rows.forEach(([head, body, color], i) => {
    const y = 1.78 + i * 1.22;
    numberDot(s, { x: M + 0.05, y: y + 0.08, n: i + 1, color });
    txt(s, head, {
      x: M + 0.75, y, w: 3.5, h: 0.42, fontSize: 17, bold: true, color: C.text1,
    });
    txt(s, body, {
      x: M + 4.3, y: y - 0.02, w: W - M - 4.3 - M, h: 1.0, fontSize: 13.5,
      color: THEME.colors.accent4, lineSpacingMultiple: 1.2,
    });
  });

  s.addNotes(
    'The deep-link rule is the one to dwell on. A naive aggregator links to the ' +
    'portal and leaves the student to search again, which destroys most of the ' +
    'value of aggregating. We enforce it centrally rather than trusting each scraper.',
  );
}

/* --------------------------------------------------------- 4. architecture */
pres.addSection({ title: 'Design' });
{
  const s = pres.addSlide({ masterName: 'LIGHT_CONTENT', sectionTitle: 'Design' });
  s.addText('How it is built', { placeholder: 'title' });
  s.addText('React front end, FastAPI on a serverless function, managed Postgres, daily scheduled refresh', { placeholder: 'kicker' });

  // Sized by available height (1187x1041 source), then pushed to the right
  // margin so the slide reads as two balanced columns.
  const archH = 5.28;
  const archW = archH * (1187 / 1041);
  s.addImage({
    path: path.join(__dirname, 'fig_architecture.png'),
    x: W - M - archW, y: 1.66, w: archW, h: archH, objectName: 'architecture',
  });

  const notes = [
    ['Same-origin API', 'The browser calls relative /api paths, so production needs no CORS configuration at all.'],
    ['No pooled connections', 'Serverless functions freeze between calls, so a held pool leaks connections. We use a null pool and let the database\u2019s own pooler do the work.'],
    ['No headless browser', 'Scraping uses an HTTP client and an HTML parser only, so the refresh fits inside a serverless function.'],
  ];
  notes.forEach(([h, b], i) => {
    const y = 1.78 + i * 1.44;
    txt(s, h, { x: M, y, w: 5.5, h: 0.36, fontSize: 16, bold: true, color: THEME.colors.accent1 });
    txt(s, b, {
      x: M, y: y + 0.38, w: 5.55, h: 1.0, fontSize: 13,
      color: THEME.colors.accent4, lineSpacingMultiple: 1.2,
    });
  });

  s.addNotes(
    'Three constraints shaped this: same-origin removes CORS, null pooling is ' +
    'forced by serverless execution, and ruling out a headless browser is what ' +
    'made data acquisition the hard part of the project.',
  );
}

/* ------------------------------------------------------- 5. the hard part */
pres.addSection({ title: 'Engineering' });
{
  const s = pres.addSlide({ masterName: 'LIGHT_CONTENT', sectionTitle: 'Engineering' });
  s.addText('Three portals, three different problems', { placeholder: 'title' });
  s.addText('None publishes an API. Two actively mislead a direct reading of the page', { placeholder: 'kicker' });

  const cols = [
    {
      name: 'NSP', color: THEME.colors.accent1, verdict: '31 schemes',
      problem: 'Four dates per scheme, only one actionable. Labels contain doubled spaces, so a literal match finds nothing. Missing documents render as the text \u201cnull\u201d.',
      fix: 'Match the student deadline specifically, after collapsing whitespace.',
    },
    {
      name: 'Buddy4Study', color: THEME.colors.accent2, verdict: '12 scholarships',
      problem: 'Listing rendered entirely in the browser. The delivered HTML holds no scholarships, and the embedded state carries only translation strings.',
      fix: 'Its sitemap lists 1,350 scholarship pages, and each one is server-rendered with full data for search engines.',
    },
    {
      name: 'Vidyasaarathi', color: THEME.colors.accent5, verdict: '15 schemes',
      problem: '\u201cCurrently No Schemes are Available\u201d appears even when 15 are open \u2014 it is a branch inside the page\u2019s own script. Served as ISO-8859-1.',
      fix: 'Read the embedded data array; test for emptiness only after stripping scripts.',
    },
  ];

  cols.forEach((c, i) => {
    const x = M + i * 4.08;
    const w = 3.82;
    card(s, { x, y: 1.78, w, h: 4.26, name: `portal-${c.name}` });
    txt(s, c.name, {
      x: x + 0.3, y: 1.98, w: w - 0.6, h: 0.4, fontSize: 18, bold: true, color: c.color,
    });
    txt(s, c.verdict, {
      x: x + 0.3, y: 2.38, w: w - 0.6, h: 0.3, fontSize: 12, bold: true,
      color: THEME.colors.accent4,
    });
    txt(s, 'THE PROBLEM', {
      x: x + 0.3, y: 2.82, w: w - 0.6, h: 0.26, fontSize: 9.5, bold: true,
      color: THEME.colors.accent3, charSpacing: 1.5,
    });
    txt(s, c.problem, {
      x: x + 0.3, y: 3.1, w: w - 0.6, h: 1.42, fontSize: 12,
      color: THEME.colors.accent4, lineSpacingMultiple: 1.18,
    });
    txt(s, 'HOW IT WAS SOLVED', {
      x: x + 0.3, y: 4.56, w: w - 0.6, h: 0.26, fontSize: 9.5, bold: true,
      color: THEME.colors.accent6, charSpacing: 1.5,
    });
    txt(s, c.fix, {
      x: x + 0.3, y: 4.84, w: w - 0.6, h: 1.02, fontSize: 12,
      color: THEME.colors.accent4, lineSpacingMultiple: 1.18,
    });
  });

  txt(s, 'Neither solution executes JavaScript: both read what the site already publishes for other purposes.', {
    x: M, y: 6.22, w: W - 2 * M, h: 0.44, fontSize: 14, italic: true,
    color: THEME.colors.accent1,
  });

  s.addNotes(
    'This is the slide to spend time on \u2014 it is where the real engineering was. ' +
    'Buddy4Study: the sitemap is declared in robots.txt, and individual pages are ' +
    'server-rendered because the site wants them indexed. Vidyasaarathi: the ' +
    'empty-state string is the else-branch of its own renderer, which is why a ' +
    'naive scraper reports zero schemes while fifteen are open.',
  );
}

/* --------------------------------------------------------- 6. resilience */
{
  const s = pres.addSlide({ masterName: 'LIGHT_CONTENT', sectionTitle: 'Engineering' });
  s.addText('What happens when a portal goes down', { placeholder: 'title' });
  s.addText('Scraping breaks. The design assumes it, so a failure degrades nothing', { placeholder: 'kicker' });

  s.addImage({
    path: path.join(__dirname, 'fig_ingest.png'),
    x: 0.55, y: 1.72, w: 7.3, h: 5.55 * (902 / 1187) * (7.3 / 7.3),
    objectName: 'ingest-flow',
  });

  const points = [
    ['Failure is not absence', 'The obvious implementation \u2014 mark anything not seen as closed \u2014 deletes a whole catalogue the first time a site is unreachable.', THEME.colors.accent3],
    ['Only a source that returned data may retire its own rows', 'A scraper that raises, or returns nothing, changes nothing.', THEME.colors.accent1],
    ['A verified fallback of 75 scholarships', 'With all three portals failing, the dashboard still lists real scholarships in deadline order.', THEME.colors.accent6],
  ];
  points.forEach(([h, b, color], i) => {
    const y = 1.95 + i * 1.5;
    txt(s, h, { x: 8.25, y, w: 4.45, h: 0.62, fontSize: 15, bold: true, color });
    txt(s, b, {
      x: 8.25, y: y + 0.62, w: 4.45, h: 0.85, fontSize: 12.5,
      color: THEME.colors.accent4, lineSpacingMultiple: 1.2,
    });
  });

  s.addNotes(
    'Demonstrated, not argued: with all three scrapers forced to fail against an ' +
    'empty database, the run is correctly reported as failed, each source is named ' +
    'in the summary, and the dashboard still shows 75 scholarships in deadline order.',
  );
}

/* ----------------------------------------------------------- 7. results */
pres.addSection({ title: 'Results' });
{
  const s = pres.addSlide({ masterName: 'LIGHT_CONTENT', sectionTitle: 'Results' });
  s.addText('What the system delivers', { placeholder: 'title' });
  s.addText('Measured against the live portals on 17 October 2026', { placeholder: 'kicker' });

  const stats = [
    ['58', 'open scholarships\nin one refresh', THEME.colors.accent1],
    ['3', 'live portals\naggregated', THEME.colors.accent2],
    ['75', 'verified fallback\nrecords', THEME.colors.accent5],
    ['157', 'automated tests,\nall passing', THEME.colors.accent6],
  ];
  stats.forEach(([v, l, color], i) => {
    const x = M + i * 3.12;
    card(s, { x, y: 1.82, w: 2.86, h: 2.08, name: `stat-${i}` });
    stat(s, { x, y: 1.95, w: 2.86, value: v, label: l, color });
  });

  const checks = [
    'Nearest deadline first, expired hidden \u2014 verified by test and by inspection',
    'Every Apply opens a scholarship-specific page; two portals with no public page show the scheme name to select',
    'A failing portal leaves its own records untouched; all three failing still yields a working dashboard',
    'No Aadhaar number, no full account number, no plaintext password \u2014 enforced at the schema level',
  ];
  txt(s, 'Objectives met', {
    x: M, y: 4.22, w: 6, h: 0.36, fontSize: 16, bold: true, color: C.text1,
  });
  s.addText(
    checks.map((t, i) => ({
      text: t,
      options: { bullet: { code: '2713' }, breakLine: i !== checks.length - 1 },
    })),
    {
      x: M, y: 4.62, w: W - 2 * M, h: 1.75, fontSize: 13,
      color: THEME.colors.accent4, paraSpaceAfter: 7, isTextBox: true, margin: 0,
    },
  );

  s.addNotes(
    'The one objective not fully closed is deployment: the hosting configuration ' +
    'is written and the build verified, but the live deployment was still being ' +
    'brought up at the time of writing. Everything else is demonstrable.',
  );
}

/* --------------------------------------------- 8. limitations and next steps */
pres.addSection({ title: 'Closing' });
{
  const s = pres.addSlide({ masterName: 'DARK_TITLE', sectionTitle: 'Closing' });

  txt(s, 'HONEST LIMITS AND WHAT COMES NEXT', {
    x: M, y: 0.72, w: 9, h: 0.34, fontSize: 13, bold: true,
    color: THEME.colors.accent2, charSpacing: 3,
  });
  txt(s, 'Where it stops, and where it goes', {
    x: M, y: 1.12, w: W - 2 * M, h: 0.8, fontSize: 34, bold: true, color: 'FFFFFF',
  });

  const limits = [
    'Buddy4Study coverage is partial \u2014 the crawl is bounded to fit the function time limit',
    'NSP and Vidyasaarathi publish no per-scheme page, so Apply opens the correct entry point plus the scheme name',
    'The fallback file stores real deadlines and must be regenerated as they pass',
    'Level and tag classification is heuristic; it aids filtering, it is not authoritative',
  ];
  const next = [
    'State portals such as MahaDBT, through the same scraper interface',
    'Eligibility matching \u2014 the portfolio already holds category, income, level and marks',
    'Deadline notifications, using the countdown already computed',
    'Alerting when a portal\u2019s markup changes, so a parser is repaired before a refresh returns nothing',
  ];

  [['Limitations', limits, THEME.colors.accent3],
   ['Future scope', next, THEME.colors.accent2]].forEach(([head, items, color], i) => {
    const x = M + i * 6.3;
    txt(s, head, {
      x, y: 2.28, w: 5.7, h: 0.4, fontSize: 18, bold: true, color,
    });
    s.addText(
      items.map((t, j) => ({
        text: t,
        options: { bullet: true, breakLine: j !== items.length - 1 },
      })),
      {
        x, y: 2.78, w: 5.8, h: 2.7, fontSize: 13, color: 'CBD5E1',
        paraSpaceAfter: 9, isTextBox: true, margin: 0, lineSpacingMultiple: 1.15,
      },
    );
  });

  txt(s, 'ScholarTrack', {
    x: M, y: 6.25, w: 5, h: 0.5, fontSize: 22, bold: true, color: 'FFFFFF',
  });
  txt(s, 'Thank you \u2014 questions welcome', {
    x: W - M - 5, y: 6.35, w: 5, h: 0.4, fontSize: 14, color: '94A3B8', align: 'right',
  });

  s.addNotes(
    'Closing on limitations deliberately: every one of these is a consequence of a ' +
    'constraint we chose knowingly, and each has a stated route forward. Happy to ' +
    'take questions on any of the three scrapers.',
  );
}

pres.writeFile({ fileName: OUT }).then(async () => {
  await applyTheme(OUT, THEME);
  console.log('wrote', OUT);
});
