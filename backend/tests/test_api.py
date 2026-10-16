"""API tests covering the acceptance checklist (spec §11)."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient


# --------------------------------------------------------------------- health
def test_health_needs_no_auth(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"ok": True}


# ----------------------------------------------------------------------- auth
class TestAuth:
    def test_signup_returns_a_token_and_the_user(self, client: TestClient) -> None:
        r = client.post(
            "/api/auth/signup",
            json={"name": "Asha", "email": "Asha@Example.com", "password": "hunter2hunter2"},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        # Email is normalised to lower case.
        assert body["user"]["email"] == "asha@example.com"
        assert body["user"]["is_admin"] is False

    def test_password_is_never_returned(self, client: TestClient) -> None:
        r = client.post(
            "/api/auth/signup",
            json={"name": "A", "email": "a@example.com", "password": "hunter2hunter2"},
        )
        assert "password" not in r.text
        assert "hunter2hunter2" not in r.text

    def test_password_is_hashed_not_stored_plainly(self, client: TestClient, db) -> None:
        from backend.models import User

        client.post(
            "/api/auth/signup",
            json={"name": "A", "email": "a@example.com", "password": "hunter2hunter2"},
        )
        user = db.query(User).filter_by(email="a@example.com").one()
        assert user.password_hash != "hunter2hunter2"
        assert user.password_hash.startswith("$2")  # bcrypt

    def test_duplicate_email_is_rejected(self, client: TestClient) -> None:
        payload = {"name": "A", "email": "dup@example.com", "password": "hunter2hunter2"}
        assert client.post("/api/auth/signup", json=payload).status_code == 201
        second = client.post("/api/auth/signup", json=payload)
        assert second.status_code == 409

    def test_duplicate_email_is_case_insensitive(self, client: TestClient) -> None:
        client.post(
            "/api/auth/signup",
            json={"name": "A", "email": "dup@example.com", "password": "hunter2hunter2"},
        )
        r = client.post(
            "/api/auth/signup",
            json={"name": "B", "email": "DUP@example.com", "password": "hunter2hunter2"},
        )
        assert r.status_code == 409

    def test_short_password_is_rejected(self, client: TestClient) -> None:
        r = client.post(
            "/api/auth/signup",
            json={"name": "A", "email": "a@example.com", "password": "short"},
        )
        assert r.status_code == 422

    def test_login_succeeds_and_is_case_insensitive(self, client: TestClient) -> None:
        client.post(
            "/api/auth/signup",
            json={"name": "A", "email": "a@example.com", "password": "hunter2hunter2"},
        )
        r = client.post(
            "/api/auth/login",
            json={"email": "A@EXAMPLE.COM", "password": "hunter2hunter2"},
        )
        assert r.status_code == 200
        assert r.json()["access_token"]

    def test_wrong_password_is_401(self, client: TestClient) -> None:
        client.post(
            "/api/auth/signup",
            json={"name": "A", "email": "a@example.com", "password": "hunter2hunter2"},
        )
        r = client.post(
            "/api/auth/login", json={"email": "a@example.com", "password": "nope"}
        )
        assert r.status_code == 401

    def test_unknown_email_is_indistinguishable_from_a_wrong_password(
        self, client: TestClient
    ) -> None:
        client.post(
            "/api/auth/signup",
            json={"name": "A", "email": "a@example.com", "password": "hunter2hunter2"},
        )
        wrong_pw = client.post(
            "/api/auth/login", json={"email": "a@example.com", "password": "nope"}
        )
        no_user = client.post(
            "/api/auth/login", json={"email": "ghost@example.com", "password": "nope"}
        )
        assert wrong_pw.status_code == no_user.status_code == 401
        assert wrong_pw.json()["detail"] == no_user.json()["detail"]

    def test_me_requires_a_token(self, client: TestClient) -> None:
        assert client.get("/api/auth/me").status_code == 401

    def test_me_rejects_a_forged_token(self, client: TestClient) -> None:
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
        assert r.status_code == 401

    def test_me_returns_the_caller(self, client: TestClient, auth) -> None:
        r = client.get("/api/auth/me", headers=auth)
        assert r.status_code == 200
        assert r.json()["email"] == "student@example.com"

    def test_admin_flag_comes_from_the_allowlist(self, client: TestClient, admin_auth) -> None:
        assert client.get("/api/auth/me", headers=admin_auth).json()["is_admin"] is True


# --------------------------------------------------------------- scholarships
class TestScholarships:
    def test_requires_auth(self, client: TestClient) -> None:
        assert client.get("/api/scholarships").status_code == 401

    def test_sorted_by_nearest_deadline(self, client: TestClient, auth, make_scholarship) -> None:
        today = date.today()
        make_scholarship(title="Later", deadline=today + timedelta(days=30))
        make_scholarship(title="Soonest", deadline=today + timedelta(days=2))
        make_scholarship(title="Middle", deadline=today + timedelta(days=10))

        titles = [i["title"] for i in client.get("/api/scholarships", headers=auth).json()["items"]]
        assert titles == ["Soonest", "Middle", "Later"]

    def test_undated_scholarships_sort_last(
        self, client: TestClient, auth, make_scholarship
    ) -> None:
        make_scholarship(title="No deadline", deadline=None)
        make_scholarship(title="Has deadline", deadline=date.today() + timedelta(days=40))

        titles = [i["title"] for i in client.get("/api/scholarships", headers=auth).json()["items"]]
        assert titles == ["Has deadline", "No deadline"]

    def test_expired_are_hidden_by_default(
        self, client: TestClient, auth, make_scholarship
    ) -> None:
        make_scholarship(title="Open", deadline=date.today() + timedelta(days=5))
        make_scholarship(title="Expired", deadline=date.today() - timedelta(days=1))

        body = client.get("/api/scholarships", headers=auth).json()
        assert [i["title"] for i in body["items"]] == ["Open"]

    def test_expired_can_be_included(self, client: TestClient, auth, make_scholarship) -> None:
        make_scholarship(title="Expired", deadline=date.today() - timedelta(days=1))
        body = client.get(
            "/api/scholarships", params={"include_expired": "true"}, headers=auth
        ).json()
        assert [i["title"] for i in body["items"]] == ["Expired"]

    def test_inactive_rows_are_hidden(self, client: TestClient, auth, make_scholarship) -> None:
        make_scholarship(title="Retired", is_active=False)
        assert client.get("/api/scholarships", headers=auth).json()["items"] == []

    def test_days_left_is_computed(self, client: TestClient, auth, make_scholarship) -> None:
        make_scholarship(deadline=date.today() + timedelta(days=3))
        assert client.get("/api/scholarships", headers=auth).json()["items"][0]["days_left"] == 3

    def test_days_left_is_null_without_a_deadline(
        self, client: TestClient, auth, make_scholarship
    ) -> None:
        make_scholarship(deadline=None)
        assert client.get("/api/scholarships", headers=auth).json()["items"][0]["days_left"] is None

    def test_search_matches_title_and_provider(
        self, client: TestClient, auth, make_scholarship
    ) -> None:
        make_scholarship(title="Pragati for Girls", provider="AICTE")
        make_scholarship(title="Something else", provider="UGC")

        by_title = client.get("/api/scholarships", params={"q": "pragati"}, headers=auth).json()
        assert [i["title"] for i in by_title["items"]] == ["Pragati for Girls"]

        by_provider = client.get("/api/scholarships", params={"q": "ugc"}, headers=auth).json()
        assert [i["title"] for i in by_provider["items"]] == ["Something else"]

    def test_filter_by_source_and_level(
        self, client: TestClient, auth, make_scholarship
    ) -> None:
        make_scholarship(source="nsp", level="pg", external_id="a")
        make_scholarship(source="manual", level="ug", external_id="b")

        assert client.get(
            "/api/scholarships", params={"source": "nsp"}, headers=auth
        ).json()["total"] == 1
        assert client.get(
            "/api/scholarships", params={"level": "ug"}, headers=auth
        ).json()["total"] == 1

    def test_tag_filter_requires_all_given_tags(
        self, client: TestClient, auth, make_scholarship
    ) -> None:
        make_scholarship(title="Girls merit", tags=["girls", "merit"])
        make_scholarship(title="Merit only", tags=["merit"])

        one = client.get("/api/scholarships", params={"tag": "girls"}, headers=auth).json()
        assert [i["title"] for i in one["items"]] == ["Girls merit"]

        both = client.get(
            "/api/scholarships", params=[("tag", "girls"), ("tag", "merit")], headers=auth
        ).json()
        assert [i["title"] for i in both["items"]] == ["Girls merit"]

        neither = client.get(
            "/api/scholarships", params=[("tag", "girls"), ("tag", "pwd")], headers=auth
        ).json()
        assert neither["items"] == []

    def test_due_within_days(self, client: TestClient, auth, make_scholarship) -> None:
        make_scholarship(title="This week", deadline=date.today() + timedelta(days=3))
        make_scholarship(title="Next month", deadline=date.today() + timedelta(days=40))
        make_scholarship(title="Undated", deadline=None)

        body = client.get(
            "/api/scholarships", params={"due_within_days": 7}, headers=auth
        ).json()
        # An undated scholarship has no known due date, so it cannot match.
        assert [i["title"] for i in body["items"]] == ["This week"]

    def test_detail_and_404(self, client: TestClient, auth, make_scholarship) -> None:
        row = make_scholarship(title="Detail me")
        assert client.get(f"/api/scholarships/{row.id}", headers=auth).json()["title"] == "Detail me"
        assert client.get("/api/scholarships/123456", headers=auth).status_code == 404

    def test_meta_counts(self, client: TestClient, auth, make_scholarship) -> None:
        make_scholarship(source="nsp", tags=["girls"], deadline=date.today() + timedelta(days=2))
        make_scholarship(source="nsp", tags=["merit"], deadline=date.today() + timedelta(days=60))
        make_scholarship(source="manual", deadline=date.today() - timedelta(days=5))

        meta = client.get("/api/scholarships/meta", headers=auth).json()
        assert meta["total_active"] == 2
        assert meta["closing_this_week"] == 1
        assert meta["expired_hidden"] == 1
        assert {s["source"]: s["count"] for s in meta["sources"]} == {"nsp": 2}
        assert meta["last_refresh_at"] is None

    def test_application_status_is_joined_in(
        self, client: TestClient, auth, make_scholarship
    ) -> None:
        row = make_scholarship()
        before = client.get("/api/scholarships", headers=auth).json()["items"][0]
        assert before["application_status"] is None

        client.post(
            "/api/applications",
            json={"scholarship_id": row.id, "status": "applied"},
            headers=auth,
        )
        after = client.get("/api/scholarships", headers=auth).json()["items"][0]
        assert after["application_status"] == "applied"
        assert after["application_id"]

    def test_another_users_status_does_not_leak(
        self, client: TestClient, auth, other_auth, make_scholarship
    ) -> None:
        row = make_scholarship()
        client.post(
            "/api/applications",
            json={"scholarship_id": row.id, "status": "awarded"},
            headers=auth,
        )
        theirs = client.get("/api/scholarships", headers=other_auth).json()["items"][0]
        assert theirs["application_status"] is None

    def test_apply_url_is_never_a_bare_portal_homepage(
        self, client: TestClient, auth, make_scholarship
    ) -> None:
        make_scholarship(apply_url="https://www.buddy4study.com/page/real-one")
        for item in client.get("/api/scholarships", headers=auth).json()["items"]:
            path = item["apply_url"].split("://", 1)[-1].partition("/")[2]
            assert path.strip("/"), f"{item['apply_url']} has no path"


# ------------------------------------------------------------------ portfolio
class TestPortfolio:
    def test_requires_auth(self, client: TestClient) -> None:
        assert client.get("/api/portfolio").status_code == 401

    def test_starts_empty_then_round_trips(self, client: TestClient, auth) -> None:
        empty = client.get("/api/portfolio", headers=auth).json()
        assert empty["personal"]["full_name"] is None

        payload = {
            "personal": {"full_name": "Asha Rao", "state": "Maharashtra", "dob": "2005-04-01"},
            "academic": {"current_course": "B.Tech", "cgpa_or_percentage": "8.7"},
            "family": {"annual_family_income": "240000"},
            "bank": {"bank_name": "SBI", "ifsc": "sbin0001234", "account_last4": "4321"},
            "documents": {"aadhaar": {"have": True}, "income_certificate": {"have": False}},
            "cv": {"summary": "Final year student", "skills": ["Python", "SQL"]},
        }
        saved = client.put("/api/portfolio", json=payload, headers=auth)
        assert saved.status_code == 200, saved.text
        body = saved.json()
        assert body["personal"]["full_name"] == "Asha Rao"
        assert body["academic"]["current_course"] == "B.Tech"
        assert body["cv"]["skills"] == ["Python", "SQL"]
        assert body["documents"]["aadhaar"]["have"] is True
        # IFSC is upper-cased on the way in.
        assert body["bank"]["ifsc"] == "SBIN0001234"

    def test_survives_a_fresh_login(self, client: TestClient, auth) -> None:
        client.put(
            "/api/portfolio",
            json={"personal": {"full_name": "Asha Rao"}},
            headers=auth,
        )
        again = client.post(
            "/api/auth/login",
            json={"email": "student@example.com", "password": "correct-horse-1"},
        ).json()["access_token"]
        body = client.get(
            "/api/portfolio", headers={"Authorization": f"Bearer {again}"}
        ).json()
        assert body["personal"]["full_name"] == "Asha Rao"

    def test_is_scoped_per_user(self, client: TestClient, auth, other_auth) -> None:
        client.put(
            "/api/portfolio", json={"personal": {"full_name": "Asha Rao"}}, headers=auth
        )
        theirs = client.get("/api/portfolio", headers=other_auth).json()
        assert theirs["personal"]["full_name"] is None

    def test_full_bank_account_number_is_rejected(self, client: TestClient, auth) -> None:
        r = client.put(
            "/api/portfolio",
            json={"bank": {"account_last4": "123456789012"}},
            headers=auth,
        )
        assert r.status_code == 422

    def test_no_field_exists_for_a_full_account_or_aadhaar_number(
        self, client: TestClient, auth
    ) -> None:
        # extra="forbid" means an attempt to smuggle one in is rejected.
        assert client.put(
            "/api/portfolio",
            json={"bank": {"account_number": "123456789012"}},
            headers=auth,
        ).status_code == 422
        assert client.put(
            "/api/portfolio",
            json={"personal": {"aadhaar_number": "1234 5678 9012"}},
            headers=auth,
        ).status_code == 422

    def test_unknown_document_keys_are_rejected(self, client: TestClient, auth) -> None:
        r = client.put(
            "/api/portfolio",
            json={"documents": {"passport_scan": {"have": True}}},
            headers=auth,
        )
        assert r.status_code == 422


# --------------------------------------------------------------- applications
class TestApplications:
    def test_requires_auth(self, client: TestClient) -> None:
        assert client.get("/api/applications").status_code == 401

    def test_create_and_list(self, client: TestClient, auth, make_scholarship) -> None:
        row = make_scholarship(title="Tracked")
        created = client.post(
            "/api/applications", json={"scholarship_id": row.id, "status": "saved"}, headers=auth
        )
        assert created.status_code == 201
        assert created.json()["status"] == "saved"

        listed = client.get("/api/applications", headers=auth).json()
        assert len(listed) == 1
        assert listed[0]["scholarship"]["title"] == "Tracked"
        assert listed[0]["scholarship"]["days_left"] is not None

    def test_apply_auto_saves_and_is_idempotent(
        self, client: TestClient, auth, make_scholarship
    ) -> None:
        row = make_scholarship()
        first = client.post(
            "/api/applications", json={"scholarship_id": row.id, "status": "saved"}, headers=auth
        ).json()
        second = client.post(
            "/api/applications", json={"scholarship_id": row.id, "status": "saved"}, headers=auth
        ).json()
        assert first["id"] == second["id"]
        assert len(client.get("/api/applications", headers=auth).json()) == 1

    def test_reapplying_does_not_downgrade_progress(
        self, client: TestClient, auth, make_scholarship
    ) -> None:
        row = make_scholarship()
        client.post(
            "/api/applications", json={"scholarship_id": row.id, "status": "awarded"}, headers=auth
        )
        # A second Apply click sends "saved"; the awarded status must survive.
        again = client.post(
            "/api/applications", json={"scholarship_id": row.id, "status": "saved"}, headers=auth
        ).json()
        assert again["status"] == "awarded"

    def test_applied_stamps_the_date(self, client: TestClient, auth, make_scholarship) -> None:
        row = make_scholarship()
        body = client.post(
            "/api/applications", json={"scholarship_id": row.id, "status": "applied"}, headers=auth
        ).json()
        assert body["applied_on"] == date.today().isoformat()

    def test_unknown_scholarship_is_404(self, client: TestClient, auth) -> None:
        r = client.post(
            "/api/applications", json={"scholarship_id": 999999, "status": "saved"}, headers=auth
        )
        assert r.status_code == 404

    def test_invalid_status_is_rejected(self, client: TestClient, auth, make_scholarship) -> None:
        row = make_scholarship()
        r = client.post(
            "/api/applications",
            json={"scholarship_id": row.id, "status": "definitely-not-a-status"},
            headers=auth,
        )
        assert r.status_code == 422

    def test_patch_status_and_notes(self, client: TestClient, auth, make_scholarship) -> None:
        row = make_scholarship()
        app_id = client.post(
            "/api/applications", json={"scholarship_id": row.id, "status": "saved"}, headers=auth
        ).json()["id"]

        patched = client.patch(
            f"/api/applications/{app_id}",
            json={"status": "under_review", "notes": "Documents uploaded"},
            headers=auth,
        )
        assert patched.status_code == 200
        assert patched.json()["status"] == "under_review"
        assert patched.json()["notes"] == "Documents uploaded"

    def test_delete(self, client: TestClient, auth, make_scholarship) -> None:
        row = make_scholarship()
        app_id = client.post(
            "/api/applications", json={"scholarship_id": row.id, "status": "saved"}, headers=auth
        ).json()["id"]
        assert client.delete(f"/api/applications/{app_id}", headers=auth).status_code == 204
        assert client.get("/api/applications", headers=auth).json() == []

    def test_cannot_touch_another_users_application(
        self, client: TestClient, auth, other_auth, make_scholarship
    ) -> None:
        row = make_scholarship()
        app_id = client.post(
            "/api/applications", json={"scholarship_id": row.id, "status": "saved"}, headers=auth
        ).json()["id"]

        assert client.patch(
            f"/api/applications/{app_id}", json={"status": "awarded"}, headers=other_auth
        ).status_code == 404
        assert client.delete(
            f"/api/applications/{app_id}", headers=other_auth
        ).status_code == 404
        assert client.get("/api/applications", headers=other_auth).json() == []


# -------------------------------------------------------------------- refresh
class TestRefreshEndpoints:
    def test_cron_rejects_a_missing_secret(self, client: TestClient) -> None:
        assert client.get("/api/cron/refresh").status_code == 401

    def test_cron_rejects_a_wrong_secret(self, client: TestClient) -> None:
        r = client.get(
            "/api/cron/refresh", headers={"Authorization": "Bearer wrong-secret"}
        )
        assert r.status_code == 401

    def test_cron_rejects_a_non_bearer_scheme(self, client: TestClient) -> None:
        r = client.get(
            "/api/cron/refresh", headers={"Authorization": "Basic test-cron-secret"}
        )
        assert r.status_code == 401

    def test_admin_refresh_requires_an_admin(self, client: TestClient, auth) -> None:
        assert client.post("/api/admin/refresh", headers=auth).status_code == 403

    def test_admin_refresh_requires_auth(self, client: TestClient) -> None:
        assert client.post("/api/admin/refresh").status_code == 401
