"""Parser unit tests against saved HTML fixtures (spec §10 step 4).

The fixtures are real captures:
  nsp.html                  - scholarships.gov.in/All-Scholarships, 16 Oct 2026
  buddy4study_detail.html   - /scholarship/satya-scholarship-program, 17 Oct 2026
  buddy4study_sitemap.xml   - trimmed from sitemap1.xml, 17 Oct 2026
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from backend.scrapers.base import (
    ScrapedScholarship,
    guess_level,
    infer_tags,
    normalize_space,
    parse_date,
    stable_id,
)
from backend.scrapers.buddy4study import (
    is_soft_404,
    parse_detail_page,
    parse_sitemap,
)
from backend.scrapers.nsp import APPLY_URL, parse_nsp_html
from backend.scrapers.vidyasaarathi import parse_vidyasaarathi_html

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ------------------------------------------------------------------- helpers
class TestParseDate:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("31-10-2026", date(2026, 10, 31)),
            ("01-06-2026", date(2026, 6, 1)),
            ("31/10/2026", date(2026, 10, 31)),
            ("2026-10-31", date(2026, 10, 31)),
            ("31 October 2026", date(2026, 10, 31)),
            ("1 Oct 2026", date(2026, 10, 1)),
            ("31st October, 2026", date(2026, 10, 31)),
            ("October 31, 2026", date(2026, 10, 31)),
            # Whitespace noise, as NSP emits it.
            ("  31-10-2026  ", date(2026, 10, 31)),
        ],
    )
    def test_parses(self, raw: str, expected: date) -> None:
        assert parse_date(raw) == expected

    @pytest.mark.parametrize(
        "raw", ["", None, "NA", "not a date", "32-13-2026", "31-10-26x", "<p>NA</p>"]
    )
    def test_rejects(self, raw: str | None) -> None:
        assert parse_date(raw) is None

    def test_day_first_for_ambiguous_dates(self) -> None:
        # Indian convention, and what NSP emits: 03-04-2026 is 3 April.
        assert parse_date("03-04-2026") == date(2026, 4, 3)


def test_normalize_space_collapses_nsp_double_spaces() -> None:
    raw = "Student Application  Open till :\n  31-10-2026 \xa0"
    assert normalize_space(raw) == "Student Application Open till : 31-10-2026"


def test_stable_id_is_deterministic_and_source_scoped() -> None:
    a = stable_id("nsp", "AICTE Pragati Scholarship")
    assert a == stable_id("nsp", "  aicte   pragati scholarship  ")
    assert a != stable_id("buddy4study", "AICTE Pragati Scholarship")


class TestGuessLevel:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("ICAR Junior Research Fellowships (JRF)", "phd"),
            ("National Scholarship For Post Graduate Studies", "pg"),
            ("AICTE Pragati Scholarship (Technical Degree)", "ug"),
            ("Pre Matric Scholarship For Students With Disabilities", "school"),
            ("Prime Minister's Scholarship Scheme", "any"),
        ],
    )
    def test_level(self, text: str, expected: str) -> None:
        assert guess_level(text) == expected

    def test_school_exam_as_a_prerequisite_does_not_mean_school_level(self) -> None:
        # Eligibility routinely names the qualifying school exam before the
        # course being funded; this is a graduation scholarship.
        text = (
            "Kotak Kanya Scholarship: passed Class 12 and secured admission to "
            "the first year of a graduation programme"
        )
        assert guess_level(text) == "ug"

    def test_school_is_used_when_nothing_higher_is_mentioned(self) -> None:
        assert guess_level("Pre Matric Scholarship for Class 9 students") == "school"

    def test_post_graduation_still_reads_as_pg(self) -> None:
        assert guess_level("Scholarship for post graduation students") == "pg"
        assert guess_level("Postgraduate scholarship") == "pg"

    def test_first_mention_wins(self) -> None:
        # "undergraduate" leads, so an "integrated master's" aside must not
        # flip this to pg.
        text = "first-year students in 3 to 5 year undergraduate or integrated master's courses"
        assert guess_level(text) == "ug"


class TestInferTags:
    def test_audience_tags_come_from_the_title_only(self) -> None:
        # Eligibility prose naming other categories must not tag the record.
        tags = infer_tags(
            "Vylor Agritech Scholarship",
            "Open to all students irrespective of SC, ST, OBC or minority status.",
        )
        assert "sc_st" not in tags
        assert "obc" not in tags
        assert "minority" not in tags

    @pytest.mark.parametrize(
        ("title", "tag"),
        [
            ("AICTE Pragati Scholarship For Girl Students", "girls"),
            ("Post Matric Scholarship For Students With Disabilities", "pwd"),
            ("Free Coaching For Scs OBCs", "sc_st"),
            ("Free Coaching For Scs OBCs", "obc"),
            ("Top Class Education For SC Students", "sc_st"),
            ("Merit Based Scheme", "merit"),
        ],
    )
    def test_tagged(self, title: str, tag: str) -> None:
        assert tag in infer_tags(title)

    def test_bsc_is_not_a_caste_tag(self) -> None:
        # The "Sc" of B.Sc must not be read as "SC".
        assert "sc_st" not in infer_tags("Scholarship for B.Sc and M.Sc students")

    def test_nature_tags_read_the_detail_text(self) -> None:
        assert "renewal" in infer_tags("Some Scheme", "This is a renewal only scheme.")


def test_scraped_scholarship_normalizes() -> None:
    record = ScrapedScholarship(
        source="nsp",
        external_id="x",
        title="  Spaced   Out    Title  ",
        apply_url="https://example.org/a",
        level="undergrad",  # not a valid level
        tags=["Merit", "merit", " girls ", ""],
    )
    assert record.title == "Spaced Out Title"
    assert record.level == "any"
    assert record.tags == ["merit", "girls"]


# ----------------------------------------------------------------------- NSP
class TestNspParser:
    @pytest.fixture(scope="class")
    def records(self) -> list[ScrapedScholarship]:
        return parse_nsp_html(_fixture("nsp.html"))

    def test_finds_every_scheme(self, records) -> None:
        # The fixture page lists 31 central-sector schemes.
        assert len(records) == 31

    def test_every_record_is_complete(self, records) -> None:
        for r in records:
            assert r.source == "nsp"
            assert r.external_id
            assert len(r.title) >= 8
            assert r.provider, f"no ministry for {r.title}"
            assert r.deadline is not None, f"no deadline for {r.title}"

    def test_deadline_is_the_student_application_date(self, records) -> None:
        # Every scheme on the captured page closed on 31-10-2026. The page also
        # shows later verification dates, which must not be picked up.
        assert {r.deadline for r in records} == {date(2026, 10, 31)}

    def test_opens_at_is_parsed(self, records) -> None:
        # Open dates genuinely vary by scheme on the captured page; most share
        # the 01-06-2026 cycle start, and every scheme has one.
        assert all(r.opens_at is not None for r in records)
        assert sum(r.opens_at == date(2026, 6, 1) for r in records) == 25
        assert {r.opens_at for r in records} == {
            date(2026, 6, 1),
            date(2026, 7, 15),
            date(2026, 7, 25),
            date(2026, 8, 3),
            date(2026, 9, 16),
        }

    def test_info_url_is_absolute_and_never_null(self, records) -> None:
        # The portal links some guidelines relatively and renders a missing
        # document as a bare "null"; neither may reach the UI.
        for r in records:
            if r.info_url is not None:
                assert r.info_url.startswith("https://"), r.title
                assert r.info_url.strip("/").lower() != "null"

    def test_missing_guidelines_become_none(self, records) -> None:
        # One scheme on the page links href="null" for its specifications.
        assert any(r.info_url is None for r in records)

    def test_apply_url_is_the_application_form_not_the_homepage(self, records) -> None:
        for r in records:
            assert r.apply_url == APPLY_URL
            assert r.apply_url.rstrip("/") != "https://scholarships.gov.in"

    def test_info_url_points_at_scheme_guidelines(self, records) -> None:
        assert any("schemeGuidelines" in (r.info_url or "") for r in records)

    def test_ministry_attribution(self, records) -> None:
        by_title = {r.title.lower(): r for r in records}
        pragati = next(t for t in by_title if "pragati" in t)
        assert "technical education" in by_title[pragati].provider.lower()

    def test_scheme_type_suffix_becomes_a_tag_and_leaves_the_title(self, records) -> None:
        for r in records:
            assert "based scheme)" not in r.title.lower()
        assert any("merit" in r.tags for r in records)
        assert any("need" in r.tags for r in records)

    def test_renewal_only_schemes_are_tagged(self, records) -> None:
        renewals = [r for r in records if "renewal" in r.tags]
        assert renewals, "expected at least one renewal-only scheme"
        assert any("csss" in r.title.lower() for r in renewals)

    def test_external_ids_are_unique(self, records) -> None:
        ids = [r.external_id for r in records]
        assert len(ids) == len(set(ids))

    def test_named_schemes_from_the_spec_are_present(self, records) -> None:
        titles = " | ".join(r.title.lower() for r in records)
        for needle in ("pragati", "saksham", "swanath", "yasasvi", "icar", "csss"):
            assert needle in titles, f"missing {needle}"

    def test_utf8_titles_survive(self, records) -> None:
        assert any("–" in r.title for r in records)  # en-dash in PM-USP

    def test_page_chrome_is_ignored(self, records) -> None:
        assert all("academic year" not in r.title.lower() for r in records)

    def test_empty_html_is_safe(self) -> None:
        assert parse_nsp_html("") == []
        assert parse_nsp_html("<html><body><h6>hi</h6></body></html>") == []


# --------------------------------------------------------------- Buddy4Study
class TestBuddy4StudyParser:
    def test_parses_only_the_open_edition(self) -> None:
        records = parse_detail_page(
            _fixture("buddy4study_detail.html"), date(2026, 10, 17)
        )
        # The brand page lists several years; only the 2026 medical edition is open.
        assert len(records) == 1
        record = records[0]
        assert record.title == "Satya Scholarship Program for Medical Courses 2026"
        assert record.deadline == date(2026, 10, 31)
        assert record.opens_at == date(2026, 9, 16)
        assert record.level == "ug"
        assert record.award_amount
        assert record.eligibility

    def test_apply_url_is_the_scholarship_page_not_the_portal(self) -> None:
        record = parse_detail_page(
            _fixture("buddy4study_detail.html"), date(2026, 10, 17)
        )[0]
        assert record.apply_url == (
            "https://www.buddy4study.com/page/satya-scholarship-program"
        )
        assert record.apply_url.rstrip("/") != "https://www.buddy4study.com"

    def test_closed_editions_are_dropped(self) -> None:
        # Far-future "today" closes every edition on the page.
        assert parse_detail_page(_fixture("buddy4study_detail.html"), date(2030, 1, 1)) == []

    def test_external_id_is_the_edition_slug(self) -> None:
        record = parse_detail_page(
            _fixture("buddy4study_detail.html"), date(2026, 10, 17)
        )[0]
        assert record.external_id == "satya-scholarship-program-for-medical-courses-2026"

    def test_sitemap_yields_scholarship_urls(self) -> None:
        urls = parse_sitemap(_fixture("buddy4study_sitemap.xml"))
        assert len(urls) == 12
        assert all("/scholarship/" in u for u in urls)

    def test_sitemap_ignores_other_url_shapes(self) -> None:
        xml = """<?xml version="1.0"?><urlset>
          <url><loc>https://www.buddy4study.com/scholarships</loc></url>
          <url><loc>https://www.buddy4study.com/scholarships/girls</loc></url>
          <url><loc>https://www.buddy4study.com/qna/something</loc></url>
          <url><loc>https://www.buddy4study.com/scholarship/real-one</loc></url>
        </urlset>"""
        assert parse_sitemap(xml) == [
            "https://www.buddy4study.com/scholarship/real-one"
        ]

    def test_sitemap_orders_newest_first(self) -> None:
        xml = """<?xml version="1.0"?><urlset>
          <url><loc>https://www.buddy4study.com/scholarship/old</loc>
               <lastmod>2026-01-01T00:00:00+05:30</lastmod></url>
          <url><loc>https://www.buddy4study.com/scholarship/new</loc>
               <lastmod>2026-10-15T00:00:00+05:30</lastmod></url>
        </urlset>"""
        assert parse_sitemap(xml)[0].endswith("/new")

    def test_soft_404_detection(self) -> None:
        generic = (
            "<html><head><title>Scholarship portal for Indian students | Find"
            " online scholarships info</title></head></html>"
        )
        assert is_soft_404(generic)
        assert parse_detail_page(generic) == []
        assert not is_soft_404("<html><head><title>Kotak Kanya Scholarship</title></head></html>")

    def test_garbage_input_is_safe(self) -> None:
        assert parse_detail_page("") == []
        assert parse_detail_page("<html></html>") == []
        assert parse_detail_page('<script id="__NEXT_DATA__">not json</script>') == []


# ------------------------------------------------------------- Vidyasaarathi
class TestVidyasaarathiParser:
    def test_no_schemes_message_returns_empty(self) -> None:
        html = """<html><body><div class="tab">
          <h3>Open Schemes</h3>
          <p>Currently No Schemes are Available.</p>
        </div></body></html>"""
        assert parse_vidyasaarathi_html(html) == []

    def test_empty_and_malformed_input_is_safe(self) -> None:
        assert parse_vidyasaarathi_html("") == []
        assert parse_vidyasaarathi_html("<html><body></body></html>") == []

    def test_listing_links_are_not_treated_as_schemes(self) -> None:
        # Only the listing page itself is linked: nothing is scholarship-specific.
        html = """<html><body>
          <a href="/Vidyasaarathi/scholarship">Scholarships</a>
          <a href="https://www.vidyasaarathi.co.in/">Home</a>
        </body></html>"""
        assert parse_vidyasaarathi_html(html) == []

    def test_parses_a_scheme_card(self) -> None:
        html = """<html><body>
          <div class="scheme-card">
            <h4>Tata Capital Pankh Scholarship for Engineering</h4>
            <p>Sponsored by Tata Capital</p>
            <p>Last Date : 30-11-2026</p>
            <p>Start Date : 01-10-2026</p>
            <p>Amount: Rs. 50,000 per annum</p>
            <a href="/Vidyasaarathi/scholarship/detail?schemeId=4821">View details</a>
          </div>
        </body></html>"""
        records = parse_vidyasaarathi_html(html)
        assert len(records) == 1
        record = records[0]
        assert record.title == "Tata Capital Pankh Scholarship for Engineering"
        assert record.deadline == date(2026, 11, 30)
        assert record.opens_at == date(2026, 10, 1)
        assert record.award_amount == "Rs. 50,000 per annum"
        assert record.apply_url.endswith("/Vidyasaarathi/scholarship/detail?schemeId=4821")
        assert record.source == "vidyasaarathi"
