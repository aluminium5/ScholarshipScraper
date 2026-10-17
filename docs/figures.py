"""Generate the report's figures as PNGs.

Box heights are derived from font metrics rather than guessed, so text can never
overflow its box: everything is expressed in inches and converted to axis units
once the figure height is known.
"""

from __future__ import annotations

import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

OUT = pathlib.Path(__file__).parent
DPI = 200

INK = "#1e293b"
MUTED = "#5b6b7f"
LINE = "#94a3b8"
ACCENT = "#4338ca"
TEAL = "#0f766e"
VIOLET = "#6d28d9"
WARN = "#b45309"
FILL_A, FILL_B, FILL_V, FILL_C, FILL_W = (
    "#eef2ff", "#f0fdfa", "#f5f3ff", "#f8fafc", "#fffbeb",
)

TITLE_PT = 9.0
BODY_PT = 7.4
PAD_IN = 0.085          # inner padding, inches
TITLE_GAP_IN = 0.055    # gap under the title

plt.rcParams.update({"font.family": "DejaVu Sans"})


class Sheet:
    """A drawing surface that thinks in inches but draws in 0..1 axis units."""

    def __init__(self, w_in: float, h_in: float):
        self.fig, self.ax = plt.subplots(figsize=(w_in, h_in))
        self.w_in, self.h_in = w_in, h_in
        self.ax.set_xlim(0, 1)
        self.ax.set_ylim(0, 1)
        self.ax.axis("off")

    def v(self, inches: float) -> float:
        """Vertical inches → axis units."""
        return inches / self.h_in

    def line_h(self, pt: float) -> float:
        """Height of one text line at `pt`, with leading, in axis units."""
        return self.v(pt / 72.0 * 1.55)

    def box_h(self, n_lines: int) -> float:
        h = 2 * self.v(PAD_IN) + self.line_h(TITLE_PT)
        if n_lines:
            h += self.v(TITLE_GAP_IN) + n_lines * self.line_h(BODY_PT)
        return h

    def box(self, x, y_top, w, title, lines=(), fill=FILL_C, edge=LINE, color=INK):
        """Draw a box whose TOP edge sits at y_top. Returns (x, y_bottom, w, h)."""
        lines = list(lines)
        h = self.box_h(len(lines))
        y = y_top - h
        self.ax.add_patch(
            mpatches.FancyBboxPatch(
                (x, y), w, h,
                boxstyle="round,pad=0,rounding_size=0.012",
                facecolor=fill, edgecolor=edge, linewidth=1.2,
            )
        )
        cursor = y_top - self.v(PAD_IN) - self.line_h(TITLE_PT) / 2
        self.ax.text(x + w / 2, cursor, title, ha="center", va="center",
                     fontsize=TITLE_PT, fontweight="bold", color=color)
        cursor -= self.line_h(TITLE_PT) / 2 + self.v(TITLE_GAP_IN)
        for line in lines:
            cursor -= self.line_h(BODY_PT) / 2
            self.ax.text(x + w / 2, cursor, line, ha="center", va="center",
                         fontsize=BODY_PT, color=MUTED)
            cursor -= self.line_h(BODY_PT) / 2
        return (x, y, w, h)

    def arrow(self, p, q, color=LINE):
        self.ax.annotate("", xy=q, xytext=p,
                         arrowprops=dict(arrowstyle="-|>", color=color,
                                         linewidth=1.2, shrinkA=1, shrinkB=1))

    def label(self, x, y, text, color=MUTED, ha="center", pt=6.9, style="normal"):
        self.ax.text(x, y, text, ha=ha, va="center", fontsize=pt, color=color,
                     style=style,
                     bbox=dict(boxstyle="round,pad=0.22", facecolor="white",
                               edgecolor="none"))

    def save(self, name: str):
        self.fig.savefig(OUT / name, dpi=DPI, bbox_inches="tight", facecolor="white")
        plt.close(self.fig)


def bottom(b):   # y of a box's bottom edge
    return b[1]


def mid_x(b):
    return b[0] + b[2] / 2


# --------------------------------------------------------- Fig 1: architecture
def architecture() -> None:
    s = Sheet(7.4, 6.5)
    gap = s.v(0.40)
    y = 0.985

    browser = s.box(0.300, y, 0.400, "Student's browser", [], fill="#ffffff")
    y = bottom(browser) - gap

    static = s.box(0.145, y, 0.710, "Vercel  ·  static build",
                   ["frontend/dist — React 18 + Vite + TypeScript",
                    "Dashboard · Portfolio · Application tracker"],
                   fill=FILL_A, edge=ACCENT, color=ACCENT)
    y = bottom(static) - gap

    api = s.box(0.145, y, 0.710, "Vercel  ·  Python serverless function",
                ["api/index.py  →  backend.main:app  (FastAPI)",
                 "routers:  auth · scholarships · portfolio",
                 "applications · cron"],
                fill=FILL_B, edge=TEAL, color=TEAL)
    y = bottom(api) - s.v(0.62)

    db = s.box(0.025, y, 0.405, "Neon Postgres",
               ["users", "scholarships", "portfolios",
                "applications", "refresh_runs"], fill=FILL_C)
    ingest = s.box(0.570, y, 0.405, "services/ingest.py",
                   ["scrapers/nsp", "scrapers/buddy4study",
                    "scrapers/vidyasaarathi",
                    "seed/scholarships.json"], fill=FILL_C)

    y = min(bottom(db), bottom(ingest)) - gap
    cron = s.box(0.025, y, 0.405, "Vercel Cron",
                 ["GET /api/cron/refresh", "00:30 UTC daily",
                  "Bearer CRON_SECRET"], fill=FILL_W, edge=WARN, color=WARN)
    portals = s.box(0.570, y, 0.405, "Live portals",
                    ["httpx + BeautifulSoup", "scholarships.gov.in",
                     "buddy4study.com", "vidyasaarathi.co.in"], fill="#ffffff")

    # Flow
    s.arrow((0.50, bottom(browser)), (0.50, 0.985 - (0.985 - bottom(static)) + static[3]))
    s.label(0.50, (bottom(browser) + static[1] + static[3]) / 2, "HTTPS")

    s.arrow((0.50, bottom(static)), (0.50, api[1] + api[3]))
    s.label(0.50, (bottom(static) + api[1] + api[3]) / 2,
            "relative  /api/*   —   same origin, so no CORS")

    s.arrow((0.36, bottom(api)), (0.23, db[1] + db[3]))
    s.label(0.215, (bottom(api) + db[1] + db[3]) / 2 + s.v(0.05),
            "SQLAlchemy · NullPool")
    s.arrow((0.64, bottom(api)), (0.77, ingest[1] + ingest[3]))
    s.label(0.800, (bottom(api) + ingest[1] + ingest[3]) / 2 + s.v(0.05),
            "admin refresh")

    s.arrow((0.570, mid_x(db) + 0.17), (0.430, mid_x(db) + 0.17))  # placeholder
    s.ax.patches[-1].remove() if False else None

    # ingest → db
    y_mid = db[1] + db[3] / 2
    s.arrow((0.570, y_mid), (0.430, y_mid))
    s.label(0.500, y_mid + s.v(0.10), "upsert")

    s.arrow((mid_x(ingest), bottom(ingest)), (mid_x(ingest), portals[1] + portals[3]))
    s.label(mid_x(ingest), (bottom(ingest) + portals[1] + portals[3]) / 2, "fetch + parse")

    s.arrow((mid_x(cron), cron[1] + cron[3]), (mid_x(cron), bottom(db)), color=WARN)
    s.label(mid_x(cron), (cron[1] + cron[3] + bottom(db)) / 2, "triggers refresh",
            color=WARN)

    s.save("fig_architecture.png")


# ------------------------------------------------------------ Fig 2: ingest flow
def ingest_flow() -> None:
    s = Sheet(7.4, 5.6)
    gap = s.v(0.38)
    y = 0.985

    trig = s.box(0.330, y, 0.340, "Refresh triggered", ["cron  ·  admin button"],
                 fill=FILL_W, edge=WARN, color=WARN)
    y = bottom(trig) - gap

    cols = [
        ("NSP", ["31 central schemes"], FILL_A, ACCENT),
        ("Buddy4Study", ["sitemap-driven crawl"], FILL_B, TEAL),
        ("Vidyasaarathi", ["15 open schemes"], FILL_V, VIOLET),
    ]
    boxes = []
    for i, (name, note, fill, edge) in enumerate(cols):
        x = 0.025 + i * 0.330
        b = s.box(x, y, 0.300, name, note + ["isolated try / except"],
                  fill=fill, edge=edge, color=edge)
        boxes.append(b)
        s.arrow((0.50, bottom(trig)), (mid_x(b), b[1] + b[3]))

    y = min(bottom(b) for b in boxes) - gap
    rule = s.box(0.025, y, 0.950, "Per-source outcome decides what may change",
                 ["returned records   →   upsert, then deactivate this source's unseen rows",
                  "raised, or returned nothing   →   leave every existing row untouched"],
                 fill="#ffffff")
    for b in boxes:
        s.arrow((mid_x(b), bottom(b)), (mid_x(b), rule[1] + rule[3]))

    y = bottom(rule) - gap
    exp = s.box(0.025, y, 0.460, "Expire past deadlines",
                ["deadline < today  →  is_active = false"], fill=FILL_C)
    seed = s.box(0.515, y, 0.460, "Seed fallback",
                 ["table empty  →  load 75 curated",
                  "scholarships from JSON"], fill=FILL_C)
    s.arrow((mid_x(exp), bottom(rule)), (mid_x(exp), exp[1] + exp[3]))
    s.arrow((mid_x(seed), bottom(rule)), (mid_x(seed), seed[1] + seed[3]))

    y = min(bottom(exp), bottom(seed)) - gap
    rec = s.box(0.190, y, 0.620, "Record the run  →  refresh_runs",
                ["per source: fetched / inserted / updated / deactivated / errors",
                 "powers the dashboard's “Updated 3h ago”"],
                fill=FILL_W, edge=WARN, color=WARN)
    s.arrow((mid_x(exp), bottom(exp)), (0.36, rec[1] + rec[3]))
    s.arrow((mid_x(seed), bottom(seed)), (0.64, rec[1] + rec[3]))

    s.save("fig_ingest.png")


# ------------------------------------------------------------- Fig 3: ER diagram
def er_diagram() -> None:
    s = Sheet(7.4, 4.05)

    def entity(x, y_top, w, title, fields, fill, edge):
        n = len(fields)
        h = 2 * s.v(PAD_IN) + s.line_h(TITLE_PT) + s.v(0.04) + n * s.line_h(BODY_PT)
        y = y_top - h
        s.ax.add_patch(mpatches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.012",
            facecolor="white", edgecolor=edge, linewidth=1.2))
        head_h = s.v(PAD_IN) + s.line_h(TITLE_PT)
        s.ax.add_patch(mpatches.Rectangle(
            (x + 0.003, y_top - head_h), w - 0.006, head_h - 0.004,
            facecolor=fill, edgecolor="none"))
        s.ax.text(x + w / 2, y_top - head_h / 2, title, ha="center", va="center",
                  fontsize=TITLE_PT, fontweight="bold", color=INK)
        cur = y_top - head_h - s.v(0.04)
        for f in fields:
            cur -= s.line_h(BODY_PT) / 2
            s.ax.text(x + 0.018, cur, f, ha="left", va="center",
                      fontsize=BODY_PT, color=MUTED)
            cur -= s.line_h(BODY_PT) / 2
        return (x, y, w, h)

    user = entity(0.030, 0.975, 0.290, "User",
                  ["id   PK", "email   UNIQUE", "password_hash", "name", "created_at"],
                  FILL_A, ACCENT)
    port = entity(0.030, 0.470, 0.290, "Portfolio",
                  ["id   PK", "user_id   FK, UNIQUE", "personal · academic",
                   "family · bank", "documents · cv", "updated_at"], FILL_A, ACCENT)
    app = entity(0.370, 0.790, 0.270, "Application",
                 ["id   PK", "user_id   FK", "scholarship_id   FK", "status",
                  "applied_on", "notes", "updated_at"], FILL_B, TEAL)
    sch = entity(0.690, 0.975, 0.280, "Scholarship",
                 ["id   PK", "source", "external_id", "title · provider",
                  "deadline · opens_at", "apply_url · info_url", "level · tags",
                  "is_active"], FILL_B, TEAL)
    entity(0.690, 0.430, 0.280, "RefreshRun",
           ["id   PK", "started_at", "finished_at", "ok", "trigger", "summary"],
           FILL_C, LINE)

    # User 1—1 Portfolio
    s.arrow((mid_x(user), bottom(user)), (mid_x(user), port[1] + port[3]))
    s.label(mid_x(user), (bottom(user) + port[1] + port[3]) / 2, "1  —  1   has one")

    # User 1—N Application
    s.arrow((user[0] + user[2], bottom(user) + user[3] * 0.45),
            (app[0], app[1] + app[3] * 0.80))
    s.label(0.348, 0.705, "1 — N", pt=7.2, color=ACCENT)

    # Application N—1 Scholarship
    s.arrow((app[0] + app[2], app[1] + app[3] * 0.80),
            (sch[0], bottom(sch) + sch[3] * 0.42))
    s.label(0.664, 0.705, "N — 1", pt=7.2, color=ACCENT)

    s.save("fig_er.png")


if __name__ == "__main__":
    architecture()
    ingest_flow()
    er_diagram()
    for f in sorted(OUT.glob("fig_*.png")):
        print(f"  {f.name}  {f.stat().st_size // 1024} KB")
