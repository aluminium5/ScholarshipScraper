"""Ingest service tests: the resilience rules in spec §7.5 and §11.

These use stub scrapers rather than the network, so the guarantees are tested
directly: a broken scraper must not wipe its source, and the seed must carry the
dashboard when everything fails.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from backend.models import RefreshRun, Scholarship
from backend.scrapers.base import BaseScraper, ScrapedScholarship
from backend.services import ingest as ingest_module
from backend.services.ingest import load_seed_if_empty, run_ingest


class StubScraper(BaseScraper):
    """Returns a fixed list, or raises, without touching the network."""

    def __init__(
        self,
        source: str,
        records: list[ScrapedScholarship] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.source = source
        self._records = records or []
        self._error = error
        self.calls = 0

    def fetch(self, client):  # noqa: ANN001 - client is unused by the stub
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._records


def make_record(source: str, external_id: str, **overrides) -> ScrapedScholarship:
    defaults = {
        "source": source,
        "external_id": external_id,
        "title": f"{source} scholarship {external_id}",
        "apply_url": f"https://example.org/{source}/{external_id}",
        "deadline": date.today() + timedelta(days=30),
        "provider": "Example Provider",
        "level": "ug",
        "tags": ["merit"],
    }
    defaults.update(overrides)
    return ScrapedScholarship(**defaults)


@pytest.fixture
def use_scrapers(monkeypatch):
    """Swap the registry for stubs."""

    def _use(*scrapers: BaseScraper):
        monkeypatch.setattr(ingest_module, "ACTIVE_SCRAPERS", list(scrapers))
        return scrapers

    return _use


@pytest.fixture
def no_seed(monkeypatch, tmp_path):
    """Point the seed loader at a path that does not exist."""
    monkeypatch.setattr(ingest_module, "SEED_PATH", tmp_path / "absent.json")


def _titles(db, source: str | None = None, active_only: bool = False) -> set[str]:
    stmt = select(Scholarship)
    if source:
        stmt = stmt.where(Scholarship.source == source)
    if active_only:
        stmt = stmt.where(Scholarship.is_active.is_(True))
    return {row.title for row in db.execute(stmt).scalars()}


class TestUpsert:
    def test_inserts_new_records(self, db, use_scrapers, no_seed) -> None:
        use_scrapers(StubScraper("nsp", [make_record("nsp", "a"), make_record("nsp", "b")]))
        run = run_ingest(db, trigger="test")
        assert run.ok
        assert run.summary["nsp"]["inserted"] == 2
        assert len(_titles(db)) == 2

    def test_second_run_updates_rather_than_duplicates(self, db, use_scrapers, no_seed) -> None:
        use_scrapers(StubScraper("nsp", [make_record("nsp", "a")]))
        run_ingest(db, trigger="test")
        use_scrapers(StubScraper("nsp", [make_record("nsp", "a", title="Renamed")]))
        run = run_ingest(db, trigger="test")

        assert run.summary["nsp"]["updated"] == 1
        assert run.summary["nsp"]["inserted"] == 0
        assert _titles(db) == {"Renamed"}

    def test_a_thinner_rescrape_does_not_blank_known_fields(
        self, db, use_scrapers, no_seed
    ) -> None:
        use_scrapers(
            StubScraper("nsp", [make_record("nsp", "a", award_amount="INR 50,000")])
        )
        run_ingest(db, trigger="test")
        use_scrapers(StubScraper("nsp", [make_record("nsp", "a", award_amount=None)]))
        run_ingest(db, trigger="test")

        row = db.execute(select(Scholarship)).scalar_one()
        assert row.award_amount == "INR 50,000"

    def test_unique_on_source_and_external_id(self, db, use_scrapers, no_seed) -> None:
        # The same external_id from two sources is two different scholarships.
        use_scrapers(
            StubScraper("nsp", [make_record("nsp", "same")]),
            StubScraper("buddy4study", [make_record("buddy4study", "same")]),
        )
        run_ingest(db, trigger="test")
        assert db.execute(select(Scholarship)).scalars().all().__len__() == 2


class TestDeepLinkRule:
    def test_a_record_without_a_path_is_skipped(self, db, use_scrapers, no_seed) -> None:
        use_scrapers(
            StubScraper(
                "nsp",
                [
                    make_record("nsp", "good"),
                    make_record("nsp", "bad", apply_url="https://scholarships.gov.in"),
                ],
            )
        )
        run = run_ingest(db, trigger="test")
        assert run.summary["nsp"]["skipped"] == 1
        assert run.summary["nsp"]["inserted"] == 1
        assert all(
            "scholarships.gov.in" != r.apply_url.rstrip("/").split("//")[-1]
            for r in db.execute(select(Scholarship)).scalars()
        )

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.buddy4study.com",
            "https://www.buddy4study.com/",
            "https://scholarships.gov.in/",
            "",
        ],
    )
    def test_bare_homepages_are_rejected(self, db, use_scrapers, no_seed, url) -> None:
        use_scrapers(StubScraper("nsp", [make_record("nsp", "x", apply_url=url)]))
        run = run_ingest(db, trigger="test")
        assert run.summary["nsp"]["inserted"] == 0
        assert run.summary["nsp"]["skipped"] == 1

    def test_a_path_is_enough(self, db, use_scrapers, no_seed) -> None:
        # NSP's shared application form has a path, so it is allowed (spec §6).
        use_scrapers(
            StubScraper(
                "nsp",
                [make_record("nsp", "x", apply_url="https://scholarships.gov.in/ApplicationForm/")],
            )
        )
        run = run_ingest(db, trigger="test")
        assert run.summary["nsp"]["inserted"] == 1


class TestStaleRows:
    def test_unseen_rows_are_deactivated(self, db, use_scrapers, no_seed) -> None:
        use_scrapers(StubScraper("nsp", [make_record("nsp", "a"), make_record("nsp", "b")]))
        run_ingest(db, trigger="test")

        # "b" has gone from the portal.
        use_scrapers(StubScraper("nsp", [make_record("nsp", "a")]))
        run = run_ingest(db, trigger="test")

        assert run.summary["nsp"]["deactivated"] == 1
        assert _titles(db, active_only=True) == {"nsp scholarship a"}
        # The row is kept, just not shown.
        assert len(_titles(db)) == 2

    def test_past_deadlines_are_deactivated(self, db, use_scrapers, no_seed) -> None:
        use_scrapers(
            StubScraper(
                "nsp",
                [
                    make_record("nsp", "open", deadline=date.today() + timedelta(days=5)),
                    make_record("nsp", "gone", deadline=date.today() - timedelta(days=1)),
                ],
            )
        )
        run = run_ingest(db, trigger="test")
        assert run.summary["_totals"]["expired"] == 1
        assert _titles(db, active_only=True) == {"nsp scholarship open"}

    def test_an_undated_scholarship_never_expires(self, db, use_scrapers, no_seed) -> None:
        use_scrapers(StubScraper("nsp", [make_record("nsp", "a", deadline=None)]))
        run_ingest(db, trigger="test")
        assert len(_titles(db, active_only=True)) == 1


class TestErrorIsolation:
    def test_one_broken_scraper_does_not_stop_the_others(
        self, db, use_scrapers, no_seed
    ) -> None:
        good = StubScraper("nsp", [make_record("nsp", "a")])
        broken = StubScraper("buddy4study", error=RuntimeError("site down"))
        other = StubScraper("vidyasaarathi", [make_record("vidyasaarathi", "v")])
        use_scrapers(good, broken, other)

        run = run_ingest(db, trigger="test")

        assert run.ok is False  # the run reports the failure
        assert run.summary["nsp"]["inserted"] == 1
        assert run.summary["vidyasaarathi"]["inserted"] == 1
        assert "site down" in run.summary["buddy4study"]["errors"][0]
        assert run.summary["_totals"]["sources_with_errors"] == ["buddy4study"]

    def test_a_failing_scraper_does_not_wipe_its_own_source(
        self, db, use_scrapers, no_seed
    ) -> None:
        """The core resilience rule (spec §7.5.3, §11)."""
        use_scrapers(StubScraper("buddy4study", [make_record("buddy4study", "keep")]))
        run_ingest(db, trigger="test")
        assert _titles(db, active_only=True) == {"buddy4study scholarship keep"}

        # Next day the site is down.
        use_scrapers(StubScraper("buddy4study", error=TimeoutError("timed out")))
        run = run_ingest(db, trigger="test")

        assert run.summary["buddy4study"]["deactivated"] == 0
        assert _titles(db, source="buddy4study", active_only=True) == {
            "buddy4study scholarship keep"
        }

    def test_an_empty_but_successful_scrape_does_not_wipe_either(
        self, db, use_scrapers, no_seed
    ) -> None:
        # Vidyasaarathi legitimately returns nothing when no scheme is open;
        # that must not retire rows captured while schemes were open.
        use_scrapers(StubScraper("vidyasaarathi", [make_record("vidyasaarathi", "a")]))
        run_ingest(db, trigger="test")

        use_scrapers(StubScraper("vidyasaarathi", []))
        run = run_ingest(db, trigger="test")

        assert run.summary["vidyasaarathi"]["deactivated"] == 0
        assert len(_titles(db, active_only=True)) == 1

    def test_every_scraper_failing_still_records_a_run(
        self, db, use_scrapers, no_seed
    ) -> None:
        use_scrapers(
            StubScraper("nsp", error=RuntimeError("a")),
            StubScraper("buddy4study", error=RuntimeError("b")),
        )
        run = run_ingest(db, trigger="test")
        assert run.ok is False
        assert run.finished_at is not None
        assert db.execute(select(RefreshRun)).scalars().all()


class TestSeedFallback:
    def test_seed_loads_when_the_table_is_empty(self, db, use_scrapers) -> None:
        """The app still shows data if every scraper fails (spec §11)."""
        use_scrapers(
            StubScraper("nsp", error=RuntimeError("down")),
            StubScraper("buddy4study", error=RuntimeError("down")),
            StubScraper("vidyasaarathi", error=RuntimeError("down")),
        )
        run = run_ingest(db, trigger="test")

        assert run.summary["_totals"]["seeded"] > 0
        rows = db.execute(select(Scholarship)).scalars().all()
        assert len(rows) > 0

    def test_seeded_rows_are_real_and_deep_linked(self, db) -> None:
        assert load_seed_if_empty(db) > 0
        for row in db.execute(select(Scholarship)).scalars():
            assert row.title
            assert row.apply_url.startswith("https://")
            # Never a bare portal homepage (spec §6).
            path = row.apply_url.split("://", 1)[1].partition("/")[2]
            assert path.strip("/"), row.apply_url

    def test_seed_is_not_loaded_when_rows_already_exist(self, db, use_scrapers) -> None:
        use_scrapers(StubScraper("nsp", [make_record("nsp", "a")]))
        run = run_ingest(db, trigger="test")
        assert run.summary["_totals"]["seeded"] == 0
        assert len(_titles(db)) == 1

    def test_seed_loading_is_idempotent(self, db) -> None:
        first = load_seed_if_empty(db)
        second = load_seed_if_empty(db)
        assert first > 0
        assert second == 0

    def test_seed_covers_several_sources(self, db) -> None:
        load_seed_if_empty(db)
        sources = {row.source for row in db.execute(select(Scholarship)).scalars()}
        assert len(sources) >= 2


class TestRefreshRun:
    def test_run_is_recorded_with_a_summary(self, db, use_scrapers, no_seed) -> None:
        use_scrapers(StubScraper("nsp", [make_record("nsp", "a")]))
        run = run_ingest(db, trigger="manual:someone@example.com")

        stored = db.execute(select(RefreshRun)).scalars().all()
        assert len(stored) == 1
        assert stored[0].trigger == "manual:someone@example.com"
        assert stored[0].finished_at is not None
        assert run.summary["nsp"]["fetched"] == 1
