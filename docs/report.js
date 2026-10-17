/**
 * Builds the ScholarTrack project report as a .docx.
 *
 * Content is factual: every number here was measured from the repository or a
 * live run, not estimated.
 */
const fs = require('fs');
const path = require('path');
const {
  AlignmentType, BorderStyle, Document, Footer, HeadingLevel, ImageRun,
  LevelFormat, PageBreak, PageNumber, Packer, Paragraph, ShadingType, Table,
  TableCell, TableOfContents, TableRow, TextRun, WidthType,
} = require('docx');

const OUT = path.join(__dirname, 'ScholarTrack_Project_Report.docx');

// A4 content width = 11906 - 2*1440 ≈ 9026 DXA.
const CONTENT_W = 9026;
const INK = '1E293B';
const MUTED = '475569';
const ACCENT = '3730A3';
const RULE = 'CBD5E1';
const HEAD_FILL = 'EEF2FF';
const ZEBRA = 'F8FAFC';

/* ------------------------------------------------------------------ helpers */
const P = (text, opts = {}) =>
  new Paragraph({
    spacing: { after: opts.after ?? 140, line: opts.line ?? 276 },
    alignment: opts.align,
    indent: opts.indent,
    children: [
      new TextRun({
        text,
        size: opts.size ?? 22,
        bold: opts.bold,
        italics: opts.italics,
        color: opts.color ?? INK,
        font: opts.font,
      }),
    ],
  });

/** A paragraph built from [{text, bold, italics, code}] parts. */
const RichP = (parts, opts = {}) =>
  new Paragraph({
    spacing: { after: opts.after ?? 140, line: 276 },
    alignment: opts.align,
    indent: opts.indent,
    children: parts.map(
      (p) =>
        new TextRun({
          text: p.text,
          bold: p.bold,
          italics: p.italics,
          size: opts.size ?? 22,
          color: p.color ?? opts.color ?? INK,
          font: p.code ? 'Consolas' : undefined,
        }),
    ),
  });

const H1 = (text) =>
  new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 200 },
    children: [new TextRun({ text, bold: true, size: 30, color: ACCENT })],
  });

const H2 = (text) =>
  new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 280, after: 140 },
    children: [new TextRun({ text, bold: true, size: 25, color: INK })],
  });

const H3 = (text) =>
  new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 220, after: 110 },
    children: [new TextRun({ text, bold: true, size: 23, color: MUTED })],
  });

const Bullet = (text, level = 0) =>
  new Paragraph({
    numbering: { reference: 'bullets', level },
    spacing: { after: 90, line: 276 },
    children: [new TextRun({ text, size: 22, color: INK })],
  });

/** Bullet whose lead-in phrase is bold. */
const BulletLead = (lead, rest, level = 0) =>
  new Paragraph({
    numbering: { reference: 'bullets', level },
    spacing: { after: 90, line: 276 },
    children: [
      new TextRun({ text: lead, bold: true, size: 22, color: INK }),
      new TextRun({ text: rest, size: 22, color: INK }),
    ],
  });

const Code = (lines) =>
  new Paragraph({
    spacing: { before: 60, after: 160, line: 240 },
    shading: { type: ShadingType.CLEAR, fill: 'F1F5F9' },
    indent: { left: 220, right: 220 },
    border: {
      top: { style: BorderStyle.SINGLE, size: 2, color: 'E2E8F0' },
      bottom: { style: BorderStyle.SINGLE, size: 2, color: 'E2E8F0' },
      left: { style: BorderStyle.SINGLE, size: 10, color: ACCENT },
      right: { style: BorderStyle.SINGLE, size: 2, color: 'E2E8F0' },
    },
    children: lines.flatMap((l, i) => [
      ...(i ? [new TextRun({ break: 1 })] : []),
      new TextRun({ text: l, font: 'Consolas', size: 18, color: '0F172A' }),
    ]),
  });

const Caption = (text) =>
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 60, after: 240 },
    children: [new TextRun({ text, size: 18, italics: true, color: MUTED })],
  });

const cell = (text, { bold, fill, width, align, code } = {}) =>
  new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: fill ? { type: ShadingType.CLEAR, fill } : undefined,
    margins: { top: 70, bottom: 70, left: 110, right: 110 },
    children: [
      new Paragraph({
        alignment: align,
        spacing: { after: 0, line: 252 },
        children: [
          new TextRun({
            text,
            bold,
            size: 19,
            color: bold ? INK : MUTED,
            font: code ? 'Consolas' : undefined,
          }),
        ],
      }),
    ],
  });

/**
 * @param {string[]} headers
 * @param {string[][]} rows
 * @param {number[]} weights relative column widths
 */
const makeTable = (headers, rows, weights, opts = {}) => {
  const total = weights.reduce((a, b) => a + b, 0);
  const widths = weights.map((w) => Math.round((w / total) * CONTENT_W));
  // Rounding must not change the sum, or Google Docs mis-renders the table.
  widths[widths.length - 1] = CONTENT_W - widths.slice(0, -1).reduce((a, b) => a + b, 0);

  return new Table({
    columnWidths: widths,
    width: { size: CONTENT_W, type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: RULE },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE },
      left: { style: BorderStyle.NONE },
      right: { style: BorderStyle.NONE },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: 'E2E8F0' },
      insideVertical: { style: BorderStyle.NONE },
    },
    rows: [
      new TableRow({
        tableHeader: true,
        children: headers.map((h, i) =>
          cell(h, { bold: true, fill: HEAD_FILL, width: widths[i] }),
        ),
      }),
      ...rows.map(
        (r, ri) =>
          new TableRow({
            children: r.map((c, i) =>
              cell(c, {
                width: widths[i],
                fill: ri % 2 ? ZEBRA : undefined,
                code: opts.codeCols?.includes(i),
                bold: opts.boldCols?.includes(i),
              }),
            ),
          }),
      ),
    ],
  });
};

/**
 * Two signature columns, each a name over a role.
 * Cells hold real paragraphs: a "\n" inside a run is not a line break in docx.
 */
const signatureBlock = (columns) => {
  const w = Math.round(CONTENT_W / columns.length);
  const widths = columns.map(() => w);
  widths[widths.length - 1] = CONTENT_W - w * (columns.length - 1);
  return new Table({
    columnWidths: widths,
    width: { size: CONTENT_W, type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.NONE },
      bottom: { style: BorderStyle.NONE },
      left: { style: BorderStyle.NONE },
      right: { style: BorderStyle.NONE },
      insideHorizontal: { style: BorderStyle.NONE },
      insideVertical: { style: BorderStyle.NONE },
    },
    rows: [
      new TableRow({
        children: columns.map(
          ([name, role], i) =>
            new TableCell({
              width: { size: widths[i], type: WidthType.DXA },
              margins: { top: 60, bottom: 60, left: 160, right: 160 },
              children: [
                new Paragraph({
                  alignment: AlignmentType.CENTER,
                  spacing: { after: 60 },
                  border: { top: { style: BorderStyle.SINGLE, size: 6, color: RULE } },
                  children: [new TextRun({ text: name, bold: true, size: 21, color: INK })],
                }),
                new Paragraph({
                  alignment: AlignmentType.CENTER,
                  spacing: { after: 0 },
                  children: [new TextRun({ text: role, size: 19, color: MUTED })],
                }),
              ],
            }),
        ),
      }),
    ],
  });
};

const figure = (file, widthPx, heightPx) =>
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 160, after: 0 },
    children: [
      new ImageRun({
        type: 'png',
        data: fs.readFileSync(path.join(__dirname, file)),
        transformation: { width: widthPx, height: heightPx },
      }),
    ],
  });

const rule = () =>
  new Paragraph({
    spacing: { before: 60, after: 160 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE } },
    children: [new TextRun({ text: '' })],
  });

const pageBreak = () => new Paragraph({ children: [new PageBreak()] });

/* -------------------------------------------------------------- title page */
const titlePage = [
  new Paragraph({ spacing: { before: 1400, after: 0 }, children: [] }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 120 },
    children: [new TextRun({ text: 'ScholarTrack', bold: true, size: 64, color: ACCENT })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 420 },
    children: [
      new TextRun({
        text: 'A Scholarship Discovery and Application Tracking System for Indian Students',
        size: 26,
        color: MUTED,
      }),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 560 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE } },
    children: [new TextRun({ text: '' })],
  }),
  P('A PROJECT REPORT', { align: AlignmentType.CENTER, size: 22, bold: true, after: 100 }),
  P('submitted in partial fulfilment of the requirements for the award of the degree of',
    { align: AlignmentType.CENTER, size: 20, color: MUTED, after: 160 }),
  P('BACHELOR OF TECHNOLOGY', { align: AlignmentType.CENTER, size: 24, bold: true, after: 100 }),
  P('in', { align: AlignmentType.CENTER, size: 20, color: MUTED, after: 100 }),
  P('COMPUTER SCIENCE AND ENGINEERING',
    { align: AlignmentType.CENTER, size: 22, bold: true, after: 560 }),

  P('Submitted by', { align: AlignmentType.CENTER, size: 20, color: MUTED, after: 90 }),
  P('[ Student Name ]        [ Enrolment Number ]',
    { align: AlignmentType.CENTER, size: 22, bold: true, after: 420 }),

  P('Under the guidance of', { align: AlignmentType.CENTER, size: 20, color: MUTED, after: 90 }),
  P('[ Guide Name and Designation ]',
    { align: AlignmentType.CENTER, size: 22, bold: true, after: 560 }),

  P('[ Department Name ]', { align: AlignmentType.CENTER, size: 22, bold: true, after: 80 }),
  P('[ Institute Name ]', { align: AlignmentType.CENTER, size: 22, bold: true, after: 80 }),
  P('Academic Year 2026 – 27', { align: AlignmentType.CENTER, size: 21, color: MUTED, after: 0 }),
  pageBreak(),
];

/* ---------------------------------------------------- certificate + declaration */
const certificate = [
  H1('Certificate'),
  P('This is to certify that the project report titled “ScholarTrack — A Scholarship Discovery and Application Tracking System for Indian Students” is a bona fide record of the work carried out by [ Student Name ], bearing enrolment number [ Enrolment Number ], in partial fulfilment of the requirements for the award of the degree of Bachelor of Technology in Computer Science and Engineering.',
    { after: 200 }),
  P('The work presented in this report was carried out under my supervision during the academic year 2026–27, and has not been submitted elsewhere for the award of any other degree or diploma.',
    { after: 900 }),
  signatureBlock([
    ['[ Guide Name ]', 'Project Guide'],
    ['[ Head of Department ]', 'Head of the Department'],
  ]),
  pageBreak(),

  H1('Declaration'),
  P('I declare that this project report represents my own work, that all sources consulted are acknowledged in the references, and that the scholarship data reproduced in this report was obtained from publicly accessible pages of the respective portals.',
    { after: 200 }),
  P('Where the behaviour of an external website is described, it reflects the state of that website on the date of observation recorded in the report. Portals change their markup without notice, and the figures quoted here are those measured at the time of writing.',
    { after: 900 }),
  P('[ Student Name ]', { bold: true, after: 60 }),
  P('[ Enrolment Number ]', { color: MUTED, after: 60 }),
  P('Date: ____________', { color: MUTED, after: 0 }),
  pageBreak(),
];

/* -------------------------------------------------------------- abstract/TOC */
const abstract = [
  H1('Abstract'),
  P('Scholarships for Indian students are published across many unconnected portals. The National Scholarship Portal carries central government schemes, Buddy4Study aggregates private and corporate programmes, and Vidyasaarathi hosts corporate CSR funds. A student who wants to know what is open today, and what closes first, must visit each portal separately, and then retype the same personal, academic and bank details into every application form. Deadlines are missed not because students are unaware of scholarships, but because the information is scattered and the effort of applying is repetitive.',
    { after: 160 }),
  P('ScholarTrack is a web application that addresses this. It collects open scholarships from three live portals into a single list ordered by the nearest deadline, stores the details a student reuses on every form with a one-click copy control beside each field, and tracks each application through the stages Saved, Applied, Under review, Awarded and Rejected. A deliberate design rule governs the Apply action: it must open the specific scholarship’s own page, never a portal home page, and a scraper that cannot determine such a page discards the record rather than publish a misleading link.',
    { after: 160 }),
  P('The system is built with a FastAPI backend, a React and TypeScript front end, and PostgreSQL, and is deployed as a static site plus a Python serverless function with a daily scheduled refresh. The principal engineering difficulty proved to be not the user interface but the acquisition of reliable data: each of the three portals publishes its listings in a different and partly undocumented way, and two of them actively mislead a naive scraper. The solutions to those three problems, and the resilience rules that stop a single failing portal from degrading the application, form the substance of this report.',
    { after: 160 }),
  P('The implemented system retrieves 58 open scholarships from the three portals in a single refresh, carries a curated fallback of 75 verified records for the case where every scraper fails, and is covered by 157 automated tests.',
    { after: 240 }),
  RichP([
    { text: 'Keywords: ', bold: true },
    { text: 'web scraping, data aggregation, scholarship management, FastAPI, React, serverless deployment, fault tolerance, deep linking.' },
  ]),
  pageBreak(),

  H1('Table of Contents'),
  new TableOfContents('Contents', { hyperlink: true, headingStyleRange: '1-3' }),
  P('', { after: 0 }),
  RichP([{ text: 'If the entries below are blank, open the document in Word and choose References › Update Table, or press Ctrl+A then F9. Word builds the table from the heading styles when the field is refreshed.', italics: true, color: MUTED }], { size: 18 }),
  pageBreak(),
];

/* ------------------------------------------------------------------ chapter 1 */
const ch1 = [
  H1('1.  Introduction'),

  H2('1.1  Background'),
  P('The Government of India and a large number of private trusts, companies and foundations fund scholarships for students at school, undergraduate, postgraduate and doctoral levels. Central government schemes are published on the National Scholarship Portal (NSP), which in the 2026–27 cycle lists schemes from fifteen ministries and departments. Private and corporate scholarships are scattered: some appear on aggregator sites such as Buddy4Study, some on corporate social responsibility platforms such as Vidyasaarathi, and many only on the funding organisation’s own website.',
    { after: 140 }),
  P('There is no single place where a student can see everything that is currently open to them. Each portal presents its own listing, in its own order, with its own notion of what counts as a deadline.',
    { after: 140 }),

  H2('1.2  Motivation'),
  P('Two observations motivated this project.',
    { after: 140 }),
  BulletLead('Discovery is fragmented. ', 'A student must know which portals exist, visit each one, and mentally merge the results. Portals typically order listings by recency or by internal category, not by urgency, so the scholarship closing in three days is not necessarily visible before the one closing in three months.'),
  BulletLead('Application is repetitive. ', 'Every form asks for substantially the same information: name, date of birth, category, income, institution, marks, bank details, and a list of documents held. A student applying to eight scholarships retypes this eight times, and a transcription error in a bank IFSC or an income figure can invalidate an application.'),
  P('A system that solves only the first problem is a search engine; one that solves only the second is a form filler. The combination is what makes the tool worth opening repeatedly during an application season.',
    { after: 140 }),

  H2('1.3  Objectives'),
  P('The project set out to achieve the following.', { after: 140 }),
  Bullet('Aggregate open scholarships from multiple live Indian portals into one list, refreshed automatically each day.'),
  Bullet('Order that list by urgency, with the nearest deadline first and expired scholarships hidden by default.'),
  Bullet('Guarantee that the Apply action opens the specific scholarship’s own page rather than a portal home page.'),
  Bullet('Store a reusable portfolio of the student’s details, with a copy control on every field.'),
  Bullet('Track the status of each application through a defined set of stages.'),
  Bullet('Ensure the application continues to serve useful data when one portal, or every portal, becomes unavailable.'),
  Bullet('Store no sensitive identifiers: no Aadhaar numbers, no full bank account numbers, and no plaintext passwords.'),

  H2('1.4  Scope'),
  P('The system covers three portals: the NSP Central Sector listing, Buddy4Study, and Vidyasaarathi. State-level portals such as MahaDBT, and the NSP tabs for Centrally Sponsored and State schemes, are outside the present scope; the scraper interface is designed so that adding them requires no change to the ingest pipeline. The application does not submit forms on the student’s behalf: every portal requires an authenticated session and, in the case of NSP, a One Time Registration, so ScholarTrack deep-links into the correct page and leaves the submission to the student.',
    { after: 140 }),

  H2('1.5  Organisation of the Report'),
  P('Chapter 2 surveys the existing portals and comparable tools. Chapter 3 states the problem precisely. Chapter 4 records the requirements. Chapter 5 presents the system design, including the architecture, the data model and the ingest contract. Chapter 6 describes the implementation, and in particular the three scraping problems that dominated the development effort. Chapter 7 describes the testing strategy and Chapter 8 the results obtained. Chapter 9 states the limitations honestly, and Chapter 10 concludes with directions for future work.',
    { after: 140 }),
  pageBreak(),
];

/* ------------------------------------------------------------------ chapter 2 */
const ch2 = [
  H1('2.  Literature Survey and Existing Systems'),

  H2('2.1  The Portals Surveyed'),
  P('Three portals were studied in detail. Each was examined by retrieving its listing page and inspecting the delivered markup, rather than by relying on published documentation, because none of the three documents a public interface for programmatic access.',
    { after: 160 }),
  makeTable(
    ['Portal', 'Operator', 'Content', 'How listings are delivered'],
    [
      ['National Scholarship Portal', 'Government of India', 'Central government schemes from 15 ministries', 'Server-rendered HTML; schemes grouped in per-ministry accordions'],
      ['Buddy4Study', 'Private aggregator', 'Private, corporate and government scholarships', 'Client-rendered; listing absent from the delivered HTML'],
      ['Vidyasaarathi', 'Protean eGov Technologies', 'Corporate CSR scholarship funds', 'Server-rendered shell; scheme data embedded in a JavaScript array'],
    ],
    [2.0, 1.7, 2.4, 3.0],
  ),
  Caption('Table 2.1  The three portals aggregated by ScholarTrack, as observed in October 2026.'),

  H2('2.2  Limitations of the Existing Portals'),
  P('Each portal serves its own operator’s purpose well, and the criticism below is of their fitness for the student’s cross-portal task, not of their quality.',
    { after: 140 }),
  BulletLead('No cross-portal view. ', 'A scholarship on Buddy4Study is invisible from NSP and vice versa. The student performs the merge manually.'),
  BulletLead('Ordering is not by urgency. ', 'NSP groups schemes by ministry. Within a ministry the order is not by closing date, so urgency must be read off each entry individually.'),
  BulletLead('Deadline semantics differ. ', 'NSP publishes several dates per scheme — the student application deadline, a defective-application verification date, an institute verification date and a nodal officer verification date. Only the first is the date a student must act on, but all four are presented in the same visual style.'),
  BulletLead('No per-scheme public page on two portals. ', 'NSP exposes no individual page for a scheme: the student logs in, completes One Time Registration and then selects the scheme from a list. Vidyasaarathi builds per-scheme URLs that return HTTP 404 without an authenticated session.'),
  BulletLead('No personal state. ', 'None of the three remembers which scholarships a given student has shortlisted or applied to, nor stores reusable applicant details.'),

  H2('2.3  Comparable Tools'),
  P('Scholarship aggregators exist commercially, Buddy4Study itself being the largest in India. They typically require registration, monetise through advertising and partner placement, and present listings ordered by commercial arrangement rather than by deadline. Generic job-application trackers such as spreadsheet templates solve the tracking problem but perform no discovery. A tool that combines automated multi-portal discovery, urgency ordering, a reusable portfolio and per-student tracking, without commercial placement, was not found during the survey.',
    { after: 140 }),

  H2('2.4  Technologies Reviewed'),
  P('Two scraping approaches were considered. A headless browser such as Playwright or Selenium executes JavaScript and can therefore read any client-rendered page, but it requires a browser binary of several hundred megabytes and cannot run inside a standard serverless function. The alternative, an HTTP client combined with an HTML parser, is small and fast but cannot execute JavaScript. The second approach was selected to keep deployment on a serverless platform feasible, which made the extraction of data from the two client-rendered portals a research problem in its own right; Chapter 6 records how it was solved without executing any JavaScript.',
    { after: 140 }),
  pageBreak(),
];

/* ------------------------------------------------------------------ chapter 3 */
const ch3 = [
  H1('3.  Problem Statement'),
  P('To design and implement a web application that aggregates currently open scholarships for Indian students from multiple independent portals into a single list ordered by nearest deadline; that stores a reusable portfolio of applicant details for rapid reuse; that tracks the progress of each application; and that does so under the following constraints:',
    { after: 160 }),
  Bullet('every Apply action must open the specific scholarship’s own page, and never a portal home page;'),
  Bullet('the failure of any one portal must not remove, corrupt or hide data previously collected from that portal, nor prevent the other portals from being refreshed;'),
  Bullet('the application must continue to present useful scholarship data even if every portal is simultaneously unavailable;'),
  Bullet('no Aadhaar number, full bank account number or plaintext password may be stored;'),
  Bullet('data acquisition must run within the execution limits of a serverless function, precluding any headless browser.'),
  P('The difficulty of the problem lies almost entirely in the first two constraints. Collecting data from a cooperative source is routine; collecting it reliably from three uncooperative sources, while guaranteeing that a failure degrades nothing, is the engineering contribution of this work.',
    { after: 140 }),
  pageBreak(),
];

/* ------------------------------------------------------------------ chapter 4 */
const ch4 = [
  H1('4.  System Requirements'),

  H2('4.1  Functional Requirements'),
  makeTable(
    ['ID', 'Requirement'],
    [
      ['FR-1', 'A student can create an account with name, email and password, and sign in subsequently.'],
      ['FR-2', 'The dashboard lists open scholarships ordered by nearest deadline, with undated scholarships last.'],
      ['FR-3', 'Expired scholarships are hidden by default and can be shown on request.'],
      ['FR-4', 'Scholarships can be filtered by free text, source portal, study level, audience tag and closing window.'],
      ['FR-5', 'Each listing shows a countdown to its deadline, coloured by urgency.'],
      ['FR-6', 'Selecting a scholarship opens a detail panel with eligibility, dates and a guidelines link.'],
      ['FR-7', 'Apply opens the scholarship’s own page in a new tab and records it in the tracker as Saved.'],
      ['FR-8', 'A student can store personal, academic, family, bank, document and CV details, and copy any field with one click.'],
      ['FR-9', 'A student can move an application between Saved, Applied, Under review, Awarded and Rejected.'],
      ['FR-10', 'A scheduled job refreshes the catalogue daily; a designated administrator can trigger a refresh manually.'],
    ],
    [0.9, 8.5],
  ),
  Caption('Table 4.1  Functional requirements.'),

  H2('4.2  Non-Functional Requirements'),
  makeTable(
    ['ID', 'Requirement'],
    [
      ['NFR-1', 'A failing portal must leave that portal’s previously collected records unchanged.'],
      ['NFR-2', 'The application must present scholarship data even when all portals fail.'],
      ['NFR-3', 'Passwords must be stored only as salted hashes; no identity numbers may be stored at all.'],
      ['NFR-4', 'A student may read or modify only their own portfolio and applications.'],
      ['NFR-5', 'A refresh must complete within the serverless function execution limit of 60 seconds.'],
      ['NFR-6', 'The interface must remain usable at mobile screen widths.'],
      ['NFR-7', 'Scraping must respect each portal’s robots.txt and use a bounded request rate.'],
    ],
    [0.9, 8.5],
  ),
  Caption('Table 4.2  Non-functional requirements.'),

  H2('4.3  Software and Hardware Requirements'),
  makeTable(
    ['Component', 'Requirement'],
    [
      ['Runtime', 'Python 3.12 (backend), Node.js 18 or later (front-end build)'],
      ['Database', 'PostgreSQL 15 or later in production; SQLite for local development'],
      ['Hosting', 'A platform supporting static hosting, Python serverless functions and scheduled invocation'],
      ['Development machine', 'Any system capable of running Python and Node.js; 4 GB RAM is sufficient'],
      ['Client', 'Any modern browser with JavaScript enabled'],
    ],
    [2.2, 7.2],
  ),
  Caption('Table 4.3  Software and hardware requirements.'),
  pageBreak(),
];

/* ------------------------------------------------------------------ chapter 5 */
const ch5 = [
  H1('5.  System Design'),

  H2('5.1  Architectural Overview'),
  P('The system is a three-tier application deployed on a serverless platform. The presentation tier is a compiled single-page React application served as static files. The application tier is a FastAPI service running as a Python serverless function, reached through a path rewrite so that the browser calls relative paths of the form /api/… on the same origin; no cross-origin configuration is therefore required in production. The data tier is a managed PostgreSQL database.',
    { after: 140 }),
  P('A scheduled invocation calls the refresh endpoint once each day. That endpoint runs the ingest service, which executes each scraper, reconciles the results against the database and records a summary of the run.',
    { after: 60 }),
  figure('fig_architecture.png', 468, 410),
  Caption('Figure 5.1  System architecture. The browser calls relative /api paths on the same origin; the ingest service upserts scraped records on the composite key (source, external_id).'),

  H3('5.1.1  Why connections are not pooled'),
  P('Serverless functions are frozen between invocations. A connection pool held in process memory is therefore useless at best, and at worst leaks database connections that the pool believes are still open. The application accordingly uses a null pool, opening and closing a connection per request, and delegates pooling to the database provider’s own connection pooler. This is the reason the deployment requires the pooled connection string rather than the direct one.',
    { after: 140 }),

  H2('5.2  Database Design'),
  P('Five entities are modelled. The portfolio sections are stored as JSON columns because their shape is driven by form layout, changes frequently, and is never queried field by field; the remaining attributes are ordinary typed columns.',
    { after: 60 }),
  figure('fig_er.png', 468, 261),
  Caption('Figure 5.2  Entity relationships. Scholarship carries a unique constraint on (source, external_id), which de-duplicates records across refreshes; Application carries one on (user_id, scholarship_id), so a student has at most one tracker row per scholarship.'),

  makeTable(
    ['Entity', 'Purpose', 'Notable constraints'],
    [
      ['User', 'Account and credentials', 'email unique; password stored only as a bcrypt hash'],
      ['Scholarship', 'One scholarship from one source', '(source, external_id) unique; apply_url must contain a path'],
      ['Portfolio', 'Reusable applicant details', 'one per user; bank section limited to the last four account digits'],
      ['Application', 'Tracker entry', '(user_id, scholarship_id) unique; status constrained to five values'],
      ['RefreshRun', 'Audit of each ingest run', 'stores per-source counts and error text'],
    ],
    [1.5, 3.0, 4.9],
  ),
  Caption('Table 5.1  Entities and their constraints.'),

  H2('5.3  The Deep-Link Rule'),
  P('The single most important design decision concerns what the Apply button opens. A naive aggregator links to the portal, leaving the student to search for the scholarship again; this destroys most of the value of aggregation. The rule adopted is that a scraper must produce a URL that identifies the specific scholarship, and that a record for which no such URL can be determined is discarded and logged rather than published with a misleading link.',
    { after: 140 }),
  P('The rule is enforced in the ingest service rather than trusted to each scraper: before any record is written, its apply URL is checked to contain a path component. A bare origin such as https://www.buddy4study.com is rejected; https://www.buddy4study.com/page/kotak-kanya-scholarship is accepted.',
    { after: 140 }),
  P('Two portals genuinely publish no per-scholarship page. NSP requires One Time Registration and in-session scheme selection; Vidyasaarathi returns 404 for its own generated detail URLs unless a session is present. For these, the apply URL is the specific application entry point — the NSP application form, and the Vidyasaarathi Open Schemes tab — and the interface displays a notice naming the exact scheme the student must select after signing in. This is a documented, visible exception rather than a silent fallback, and both still satisfy the path requirement.',
    { after: 140 }),

  H2('5.4  The Ingest Contract'),
  P('A refresh must never leave the dashboard worse than it found it. This principle is expressed as six rules, implemented in the ingest service and verified by automated tests.',
    { after: 140 }),
  Bullet('Each scraper runs inside its own exception boundary, so one failure cannot stop the others or abort the run.'),
  Bullet('Records are inserted or updated against the composite key (source, external_id).'),
  Bullet('Only a source that actually returned records may deactivate its own unseen rows. A source that raised an exception, or returned nothing, leaves every existing row untouched.'),
  Bullet('Any scholarship whose deadline has passed is deactivated, independently of what the scrapers returned.'),
  Bullet('If the scholarship table is entirely empty, a curated fallback file is loaded.'),
  Bullet('The run and its per-source counts are written to an audit table, which supplies the “last updated” indicator in the interface.'),
  P('The third rule deserves emphasis because it is the one most easily got wrong. The obvious implementation of “mark anything not seen in this run as closed” deletes an entire source’s catalogue the first time that site has an outage. Distinguishing “the portal says these scholarships are gone” from “we could not reach the portal” is the difference between a system that degrades gracefully and one that destroys its own data.',
    { after: 60 }),
  figure('fig_ingest.png', 468, 356),
  Caption('Figure 5.3  The refresh pipeline. The outcome of each scraper independently determines what that source is permitted to change.'),

  H2('5.5  Module Decomposition'),
  makeTable(
    ['Module', 'Responsibility'],
    [
      ['backend/config.py', 'Environment configuration; rewrites the database URL to the driver form; SQLite fallback'],
      ['backend/db.py', 'Engine and session management; null pooling for serverless execution'],
      ['backend/models.py', 'SQLAlchemy entity definitions'],
      ['backend/schemas.py', 'Pydantic request and response schemas, including the storage restrictions'],
      ['backend/auth.py', 'Password hashing, token issue and verification, current-user dependency'],
      ['backend/routers/', 'HTTP endpoints for auth, scholarships, portfolio, applications and refresh'],
      ['backend/scrapers/', 'One module per portal plus a shared base of parsing helpers'],
      ['backend/services/ingest.py', 'Orchestration, reconciliation and the seed fallback'],
      ['frontend/src/pages/', 'Login, Dashboard, Portfolio and Applications screens'],
      ['frontend/src/components/', 'Shared presentation components including the detail drawer and copy control'],
    ],
    [2.6, 6.8],
    { codeCols: [0] },
  ),
  Caption('Table 5.2  Module responsibilities.'),
  pageBreak(),
];

/* ------------------------------------------------------------------ chapter 6 */
const ch6 = [
  H1('6.  Implementation'),

  H2('6.1  Technology Stack'),
  makeTable(
    ['Layer', 'Technology', 'Reason for selection'],
    [
      ['Front end', 'React 18, Vite, TypeScript', 'Component model suits the dashboard; strict typing catches API contract drift at build time'],
      ['Styling', 'Tailwind CSS', 'Utility classes keep the visual language consistent without a separate stylesheet to maintain'],
      ['Server state', 'TanStack Query', 'Caching and invalidation of server data without hand-written reducers'],
      ['Back end', 'FastAPI, Pydantic v2', 'Request validation derived from type annotations; schema-level enforcement of storage rules'],
      ['Persistence', 'SQLAlchemy 2', 'Typed ORM with explicit session control'],
      ['Database', 'PostgreSQL (managed), SQLite locally', 'Zero-setup local development; managed Postgres in production'],
      ['Scraping', 'httpx, BeautifulSoup, lxml', 'No browser binary, so the refresh runs inside a serverless function'],
      ['Authentication', 'bcrypt, JSON Web Tokens', 'Standard password hashing; stateless tokens suit a function that holds no session'],
    ],
    [1.5, 2.3, 5.6],
  ),
  Caption('Table 6.1  Technology selections.'),

  H2('6.2  Data Acquisition'),
  P('All three scrapers implement one interface: a fetch method returning a list of normalised records. Each uses a realistic browser user agent, a fifteen-second timeout and at most two retries. Parsing is separated from retrieval, so every parser is a pure function from markup to records and can be tested against saved HTML without network access. The sections below describe what each portal required; they are the substance of the implementation effort.',
    { after: 160 }),

  H3('6.2.1  National Scholarship Portal'),
  P('The NSP listing is server-rendered, so retrieval is a single request. Schemes appear inside per-ministry accordions: the ministry name is the accordion header, each scheme title is a level-six heading, and the dates appear as styled badges. Three details required care.',
    { after: 140 }),
  BulletLead('Selecting the correct date. ', 'Each scheme publishes up to four dates. Only the student application deadline is actionable, so the parser matches that label specifically and ignores the verification dates that follow it.'),
  BulletLead('Irregular whitespace. ', 'The portal emits labels containing doubled spaces, for example “Student Application  Open till”. A literal match for the single-spaced label finds nothing. All label matching is therefore performed after collapsing whitespace runs, a defect that produced zero results until it was diagnosed.'),
  BulletLead('Missing and relative documents. ', 'A scheme without published guidelines is rendered with the literal attribute value “null”, which a naive parser stores as a URL; and some guideline links are relative, which do not resolve when opened from a different origin. Both cases are now normalised, the first to an absent value and the second to an absolute URL.'),
  P('Scheme identifiers are derived by hashing the normalised title rather than by using the guidelines filename, because those filenames incorporate the academic year and change annually, which would cause every scheme to be re-inserted as new each year.',
    { after: 140 }),

  H3('6.2.2  Buddy4Study'),
  P('Buddy4Study presented the hardest problem. Its listing page is rendered entirely on the client: the delivered HTML is a shell of approximately 22 kilobytes containing no scholarship markup. The framework’s embedded state payload, which would ordinarily carry the server-supplied data, was found to contain only interface translation strings. The runtime data is fetched from a documented-nowhere API whose path could not be determined from the shipped bundles.',
    { after: 140 }),
  P('The resolution came from the site’s own search-engine provisions. The robots file declares a sitemap; that sitemap lists approximately 1,350 individual scholarship URLs, each with a last-modified timestamp. Each such page, unlike the listing, is server-rendered for indexing purposes and embeds a complete state payload containing every edition of that programme across years, with an ISO-formatted deadline, the award description, the eligibility text, the application launch date and the canonical page slug. Discovery therefore comes from the sitemap and the data from the individual pages, with no JavaScript executed at any point.',
    { after: 140 }),
  P('Two further characteristics had to be accommodated. The site answers an unknown slug with HTTP 200 and its generic title rather than a 404, so validity is determined by inspecting the returned title rather than the status code. And since visiting 1,350 pages cannot complete inside a serverless invocation, the crawl is bounded by a configurable limit, visiting the most recently modified pages first on the reasoning that newly opened scholarships appear there. The consequence, stated plainly, is that this source contributes variety rather than exhaustive coverage.',
    { after: 140 }),

  H3('6.2.3  Vidyasaarathi'),
  P('Vidyasaarathi is server-rendered, but its scheme cards are not present in the HTML. The open schemes are embedded in the page as a JavaScript array literal which the page’s own rendering function converts into cards at load time. Extracting the array literal and parsing it as JSON yields the full set of records, each carrying the scheme name, the sponsoring organisation, start and end dates, the award amount, an income ceiling and a gender criterion.',
    { after: 140 }),
  P('Two properties of this page produced incorrect results before they were understood, and both are worth recording because neither is visible from a casual inspection.',
    { after: 140 }),
  BulletLead('A misleading empty-state message. ', 'The string “Currently No Schemes are Available” is present in the delivered page at all times, because it is the alternative branch inside the rendering function’s own source code. A scraper that tests for this string in the page text concludes that no schemes exist even when fifteen are open. The emptiness test is therefore applied to the page with script and style elements removed.'),
  BulletLead('A non-Unicode encoding. ', 'The page is served as ISO-8859-1 and contains Windows-1252 byte values for typographic quotation marks. Decoding it as UTF-8 raises an exception, so the response encoding is pinned explicitly.'),
  P('The portal constructs per-scheme detail URLs from an entity code and a scheme identifier, but every such URL returns 404 without an authenticated session. Under the deep-link rule the apply URL is consequently the Open Schemes tab, with each record’s description naming the scheme to select after signing in — the same treatment applied to NSP, and for the same reason.',
    { after: 140 }),

  H2('6.3  The Seed Fallback'),
  P('A curated file of 75 verified open scholarships is loaded if, and only if, the scholarship table is entirely empty. Its purpose is to guarantee that a first deployment, or a catastrophic simultaneous failure of all three portals, still presents a working dashboard rather than an empty one. The file is generated by a script that runs the live scrapers and writes the result, so it can be refreshed rather than hand-maintained; this matters because it stores real deadlines and therefore goes stale.',
    { after: 140 }),
  P('Five hand-checked private programmes are included alongside the scraped records. Where no deadline could be confirmed on an official page, the deadline is recorded as absent rather than estimated: such entries remain visible and sort last. During preparation of this file, five curated entries were found to point at organisation home pages, which the deep-link rule forbids; three were corrected to verified programme pages and two were removed because the funder’s site is a single-page application that returns HTTP 200 for every path, making verification impossible. The generator now refuses to write a record whose apply URL lacks a path.',
    { after: 140 }),

  H2('6.4  Application Programming Interface'),
  makeTable(
    ['Method and path', 'Access', 'Purpose'],
    [
      ['POST /api/auth/signup', 'Public', 'Create an account, returning a token'],
      ['POST /api/auth/login', 'Public', 'Authenticate, returning a token'],
      ['GET /api/auth/me', 'Student', 'Return the authenticated account'],
      ['GET /api/scholarships', 'Student', 'List with filters; ordered by deadline ascending, undated last'],
      ['GET /api/scholarships/{id}', 'Student', 'Retrieve one scholarship'],
      ['GET /api/scholarships/meta', 'Student', 'Counts by source, level and tag, and last refresh time'],
      ['GET, PUT /api/portfolio', 'Student', 'Read and replace the portfolio'],
      ['GET, POST /api/applications', 'Student', 'List the tracker; create or update an entry'],
      ['PATCH, DELETE /api/applications/{id}', 'Student', 'Update status or notes; remove an entry'],
      ['GET /api/cron/refresh', 'Scheduler', 'Run the ingest, authorised by a shared secret'],
      ['POST /api/admin/refresh', 'Administrator', 'Run the ingest on demand'],
      ['GET /api/health', 'Public', 'Liveness check'],
    ],
    [3.6, 1.5, 4.3],
    { codeCols: [0] },
  ),
  Caption('Table 6.2  Application programming interface.'),
  P('Each scholarship returned in a list carries both the number of days remaining and the requesting student’s own tracking status, so the dashboard renders from a single request. Two behaviours are deliberate and are covered by tests: creating an application is an upsert that never regresses a status, so pressing Apply again on a scholarship already marked Awarded leaves it Awarded; and the scheduled refresh endpoint returns a service-unavailable response, rather than running, if its shared secret has not been configured.',
    { after: 140 }),

  H2('6.5  Security and Data Minimisation'),
  Bullet('Passwords are stored as bcrypt hashes and are never returned by any endpoint.'),
  Bullet('Authentication uses signed tokens carrying the account identifier and an expiry.'),
  Bullet('The bank section accepts only the last four digits of an account number; a longer value is rejected as a validation error.'),
  Bullet('No schema anywhere defines a field for an Aadhaar number or a full account number, and every portfolio section forbids unknown fields, so an attempt to submit one is rejected rather than quietly stored.'),
  Bullet('The document checklist records only whether a document is held and its expiry, never a document number.'),
  Bullet('Sign-in returns an identical response for an unknown address and an incorrect password, so account existence cannot be probed.'),
  Bullet('A request for another student’s application returns not-found rather than forbidden, so identifiers cannot be enumerated.'),

  H2('6.6  User Interface'),
  P('The interface follows a deliberately plain visual language: a light neutral background, a single indigo accent, the Inter typeface, an eight-pixel spacing grid, and one-pixel borders in preference to shadows. It comprises four screens.',
    { after: 140 }),
  BulletLead('Login. ', 'A single centred card that switches between sign-in and registration.'),
  BulletLead('Dashboard. ', 'A summary strip showing scholarships closing this week, the number open, the number applied to and the time of the last refresh; a search field; filter chips for source, level, audience tag and closing window; and the deadline-ordered list. Each entry shows a countdown badge, rendered red at three days or fewer and amber at ten or fewer. Selecting an entry opens a side panel with eligibility, dates, the guidelines link and, where applicable, the notice naming the scheme to select after signing in.'),
  BulletLead('Portfolio. ', 'Six tabbed sections with a copy control beside every field. This is the screen that saves the student the most time, and the copy control is its reason for existing; it falls back to a hidden text area where the clipboard interface is unavailable.'),
  BulletLead('Applications. ', 'Five columns, one per status, each card carrying a status selector and a deadline countdown.'),
  pageBreak(),
];

/* ------------------------------------------------------------------ chapter 7 */
const ch7 = [
  H1('7.  Testing'),

  H2('7.1  Strategy'),
  P('Testing concentrated on the two areas where failure would be both likely and damaging: the parsers, which depend on markup outside the project’s control, and the ingest reconciliation, where an error destroys data. Parsers are tested against HTML captured from the live portals and committed to the repository, so a parser can be corrected without network access and a future change to a portal produces a reproducible failure. Reconciliation is tested with substitute scrapers that return fixed results or raise on demand, which allows outage behaviour to be asserted directly.',
    { after: 160 }),

  H2('7.2  Coverage'),
  makeTable(
    ['Suite', 'Tests', 'What it establishes'],
    [
      ['Parsers', '75', 'Field extraction from real captured markup; date formats; the deep-link rule; detection of the soft 404 and of the misleading empty-state message; safe handling of malformed input'],
      ['Ingest', '28', 'A failing source changes nothing it owns; one failure does not stop the others; the fallback loads when all fail; records lacking a path are rejected; a thinner re-scrape cannot blank a stored field'],
      ['API', '54', 'Authentication; per-student isolation; deadline ordering; every filter; the Apply upsert behaviour; enforcement of the storage restrictions'],
      ['Total', '157', 'All passing'],
    ],
    [1.3, 1.0, 7.1],
    { boldCols: [] },
  ),
  Caption('Table 7.1  Automated test coverage.'),

  H2('7.3  Representative Cases'),
  P('Four cases illustrate what the suite protects against.',
    { after: 140 }),
  BulletLead('Outage does not destroy data. ', 'A source is populated, then its scraper is made to raise. The test asserts that the deactivation count is zero and that the previously collected rows remain active.'),
  BulletLead('A legitimate empty result is distinguished from a failure. ', 'A source that successfully returns no records likewise deactivates nothing, because Vidyasaarathi genuinely has no open schemes at some times of year.'),
  BulletLead('Complete failure still yields a usable dashboard. ', 'All three scrapers are made to raise against an empty database; the test asserts that the fallback loaded and that records are present.'),
  BulletLead('The deep-link rule is enforced centrally. ', 'Records whose apply URL is a bare origin are rejected and counted as skipped, while the NSP application form, which has a path, is accepted.'),

  H2('7.4  Defects Found by Testing'),
  P('The suite found several genuine defects during development, which is recorded here because it is the clearest evidence of its value.',
    { after: 140 }),
  Bullet('NSP guideline links with the literal value “null” were being stored as URLs, and relative links were stored unresolved and would not have opened.'),
  Bullet('Audience tags were being inferred from the full eligibility text, which commonly enumerates the categories a scholarship excludes; one record had acquired six spurious tags. Audience tags are now inferred from the title alone.'),
  Bullet('Study level was misclassified where eligibility text named the qualifying school examination before the course being funded, so a graduation scholarship was filed as a school scholarship.'),
  Bullet('The tag filter was applied after the result limit, so matching scholarships beyond the first page were omitted and the reported total was wrong.'),
  Bullet('Five curated fallback entries pointed at organisation home pages, in violation of the deep-link rule; the loader had been skipping them silently, so a test over the loaded rows did not reveal it. The file itself is now validated.'),
  pageBreak(),
];

/* ------------------------------------------------------------------ chapter 8 */
const ch8 = [
  H1('8.  Results and Discussion'),

  H2('8.1  Data Retrieved'),
  P('A single refresh against the three live portals produced the following, measured on 17 October 2026.',
    { after: 60 }),
  makeTable(
    ['Source', 'Records', 'Deep link used', 'Notes'],
    [
      ['National Scholarship Portal', '31', 'Application form, with the scheme named in the interface', 'All with ministry, closing date and guidelines document'],
      ['Buddy4Study', '12', 'The scholarship’s own page', 'From a bounded crawl of the most recently modified pages'],
      ['Vidyasaarathi', '15', 'Open Schemes tab, with the scheme named', 'All carrying sponsor, amount and income ceiling'],
      ['Total', '58', '—', 'Ordered by nearest deadline, expired hidden'],
    ],
    [2.6, 1.0, 3.0, 2.8],
  ),
  Caption('Table 8.1  Records retrieved in one refresh.'),

  H2('8.2  Objectives Assessed'),
  makeTable(
    ['Objective', 'Outcome'],
    [
      ['Aggregate from multiple live portals', 'Achieved — three portals, 58 open scholarships, refreshed daily'],
      ['Order by nearest deadline, hide expired', 'Achieved — verified by automated test and by inspection'],
      ['Apply opens a scholarship-specific page', 'Achieved — enforced centrally; two documented exceptions carry an on-screen notice'],
      ['Reusable portfolio with copy controls', 'Achieved — six sections, copy control on every field'],
      ['Application status tracking', 'Achieved — five stages; Apply records the scholarship automatically'],
      ['Resilience to portal failure', 'Achieved — demonstrated by test and by a simulated total outage'],
      ['Store no sensitive identifiers', 'Achieved — enforced at the schema level'],
      ['Deployment with scheduled refresh', 'Configured; deployment to the hosting platform was in progress at the time of writing'],
    ],
    [3.4, 6.0],
  ),
  Caption('Table 8.2  Assessment against the objectives of Section 1.3.'),

  H2('8.3  Resilience Demonstrated'),
  P('The behaviour required by NFR-1 and NFR-2 was exercised directly rather than argued for. With all three scrapers made to fail against an empty database, the run was correctly reported as unsuccessful, each of the three sources was named in the error summary, and the dashboard nevertheless presented 75 scholarships from the fallback, ordered by nearest deadline. With a populated database and a single scraper failing, that source’s records were left entirely unchanged while the other two refreshed normally.',
    { after: 140 }),

  H2('8.4  Implementation Size'),
  makeTable(
    ['Component', 'Lines of code'],
    [
      ['Backend application (Python)', '3,024'],
      ['Automated tests (Python)', '1,394'],
      ['Front end (TypeScript and TSX)', '2,477'],
      ['Total', '6,895'],
    ],
    [5.0, 4.4],
  ),
  Caption('Table 8.3  Implementation size, excluding generated files and dependencies.'),

  H2('8.5  Discussion'),
  P('The distribution of effort was not what was anticipated at the outset. The user interface, the data model and the API were largely routine. Essentially all of the difficulty lay in data acquisition, and specifically in the fact that two of the three portals present information in a form that defeats direct inspection: one does not deliver its listing to the client at all, and the other delivers text that actively contradicts the data it also delivers. In both cases the eventual solution did not involve executing JavaScript, which would have precluded serverless deployment, but came instead from reading what each site publishes for other purposes — a sitemap in the first case, an embedded data array in the second.',
    { after: 140 }),
  P('The second observation concerns failure handling. The natural implementation of a refresh — fetch everything, then mark whatever was not seen as closed — is correct only while every fetch succeeds, and silently destroys a catalogue the first time a site is unreachable. Treating “the portal reports no scholarships” and “the portal could not be reached” as distinct outcomes is a small change in code and a large change in behaviour, and it is the reason the system can be left to refresh unattended.',
    { after: 140 }),
  pageBreak(),
];

/* ------------------------------------------------------------------ chapter 9 */
const ch9 = [
  H1('9.  Limitations'),
  P('The following limitations are stated plainly, as they bear on any assessment of the system and on any future work.',
    { after: 140 }),
  BulletLead('Buddy4Study coverage is partial. ', 'The crawl is bounded so that a refresh completes within the serverless execution limit, and the great majority of programmes have a current edition that has already closed. This source therefore contributes breadth of type rather than completeness.'),
  BulletLead('Two portals cannot be deep-linked to a page. ', 'NSP and Vidyasaarathi publish no per-scheme public page, so the student is directed to the correct application entry point together with the scheme name rather than to the scheme itself.'),
  BulletLead('NSP coverage is limited to the Central Sector listing. ', 'The Centrally Sponsored and State scheme tabs are driven by form submissions and are not yet retrieved.'),
  BulletLead('The fallback file ages. ', 'It stores real deadlines, so once every dated entry has passed it would present nothing. It must be regenerated periodically; a script is provided for this.'),
  BulletLead('Classification is heuristic. ', 'Study level and audience tags are inferred from text and will occasionally mislabel an unusually worded scheme. They are filtering aids, not authoritative statements of eligibility.'),
  BulletLead('Scraping is inherently fragile. ', 'None of the three portals offers a documented interface, and any of them may change its markup without notice. The parsers are isolated and individually tested to make such a change cheap to repair, but it will require repair.'),
  BulletLead('The token is held in browser storage. ', 'This is appropriate for an application of this kind but means the token is readable by any script running on the origin.'),
  pageBreak(),
];

/* ----------------------------------------------------------------- chapter 10 */
const ch10 = [
  H1('10.  Conclusion and Future Scope'),

  H2('10.1  Conclusion'),
  P('ScholarTrack demonstrates that the scholarship information published across several independent Indian portals can be consolidated into a single, urgency-ordered view, and that doing so is compatible with a small serverless deployment and with respect for each portal’s stated access policy. The system retrieves 58 currently open scholarships from three portals, preserves a verified fallback of 75 records against total failure, stores a reusable applicant portfolio with per-field copy controls, and tracks applications through five stages. It is covered by 157 automated tests.',
    { after: 140 }),
  P('The two findings of substance are methodological rather than architectural. The first is that data a site does not expose to direct inspection is often obtainable from what that site publishes for search engines or embeds for its own rendering code, and that this route avoids the browser automation that would otherwise make serverless deployment impossible. The second is that in any system which synchronises against external sources, the handling of failure must distinguish absence from unavailability; the two look identical in the result of a fetch and have opposite correct responses.',
    { after: 140 }),

  H2('10.2  Future Scope'),
  BulletLead('State portals. ', 'MahaDBT and comparable state systems carry a large volume of scholarships relevant to students in particular states, and would fit the existing scraper interface without modification to the pipeline.'),
  BulletLead('Eligibility matching. ', 'The portfolio already records category, income, study level and marks. These are precisely the criteria scholarships are filtered by, so the dashboard could rank by eligibility rather than requiring the student to filter manually.'),
  BulletLead('Deadline notification. ', 'Electronic mail or push notification for scholarships closing within a chosen window, for which the countdown data is already computed.'),
  BulletLead('Document vault. ', 'Encrypted storage of the certificates students repeatedly upload, which would require careful treatment given the data-minimisation position taken in this work.'),
  BulletLead('Complete Buddy4Study coverage. ', 'Moving the crawl to a scheduled worker without a request timeout would allow the full catalogue to be retrieved.'),
  BulletLead('Change detection. ', 'Alerting the maintainer when a portal’s markup changes, so that a parser can be repaired before a refresh silently returns nothing.'),
  pageBreak(),
];

/* ---------------------------------------------------------------- references */
const refs = [
  H1('References'),
  P('[1]  Ministry of Education, Government of India, “National Scholarship Portal — All Scholarships,” scholarships.gov.in. Accessed 17 October 2026.', { after: 110 }),
  P('[2]  Buddy4Study, “Scholarships for Indian Students,” buddy4study.com. Accessed 17 October 2026.', { after: 110 }),
  P('[3]  Protean eGov Technologies, “Vidyasaarathi — Scholarship Schemes,” vidyasaarathi.co.in. Accessed 17 October 2026.', { after: 110 }),
  P('[4]  S. Ramírez, “FastAPI Documentation.” fastapi.tiangolo.com.', { after: 110 }),
  P('[5]  M. Bayer, “SQLAlchemy 2.0 Documentation.” docs.sqlalchemy.org.', { after: 110 }),
  P('[6]  Pydantic, “Pydantic v2 Documentation.” docs.pydantic.dev.', { after: 110 }),
  P('[7]  Meta Open Source, “React Documentation.” react.dev.', { after: 110 }),
  P('[8]  E. You and the Vite team, “Vite Documentation.” vite.dev.', { after: 110 }),
  P('[9]  L. Richardson, “Beautiful Soup Documentation.” crummy.com/software/BeautifulSoup.', { after: 110 }),
  P('[10]  T. Christie, “HTTPX Documentation.” python-httpx.org.', { after: 110 }),
  P('[11]  N. Provos and D. Mazières, “A Future-Adaptable Password Scheme,” Proceedings of the USENIX Annual Technical Conference, 1999.', { after: 110 }),
  P('[12]  M. Jones, J. Bradley and N. Sakimura, “JSON Web Token (JWT),” RFC 7519, Internet Engineering Task Force, 2015.', { after: 110 }),
  P('[13]  M. Koster, G. Illyes, H. Zeller and L. Sassman, “Robots Exclusion Protocol,” RFC 9309, Internet Engineering Task Force, 2022.', { after: 110 }),
  P('[14]  Tailwind Labs, “Tailwind CSS Documentation.” tailwindcss.com.', { after: 110 }),
  P('[15]  Vercel, “Python Runtime and Cron Jobs Documentation.” vercel.com/docs.', { after: 110 }),
];

/* ------------------------------------------------------------------ document */
const doc = new Document({
  creator: 'ScholarTrack',
  title: 'ScholarTrack — Project Report',
  description: 'Scholarship discovery and application tracking system for Indian students',
  styles: {
    default: {
      document: { run: { font: 'Calibri', size: 22, color: INK } },
    },
  },
  numbering: {
    config: [
      {
        reference: 'bullets',
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: '•',
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 460, hanging: 240 } } },
          },
          {
            level: 1,
            format: LevelFormat.BULLET,
            text: '◦',
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 900, hanging: 240 } } },
          },
        ],
      },
    ],
  },
  features: { updateFields: true },
  sections: [
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 }, // A4
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
        },
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({ text: 'ScholarTrack  —  ', size: 16, color: MUTED }),
                new TextRun({ children: [PageNumber.CURRENT], size: 16, color: MUTED }),
              ],
            }),
          ],
        }),
      },
      children: [
        ...titlePage,
        ...certificate,
        ...abstract,
        ...ch1, ...ch2, ...ch3, ...ch4, ...ch5,
        ...ch6, ...ch7, ...ch8, ...ch9, ...ch10,
        ...refs,
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log(`wrote ${OUT}  (${Math.round(buf.length / 1024)} KB)`);
});
