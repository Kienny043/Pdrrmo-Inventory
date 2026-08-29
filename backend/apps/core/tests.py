"""Tests for the reference-data constants, their two read-only endpoints,
the Step 3a Personnel / TrainingRecord models, and the Step 3b CRUD API."""

import datetime
import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from . import choices as core_choices
from . import models as core_models
from . import reference
from .choices import TRAINING_YEAR_MAX, TRAINING_YEAR_MIN, OrgAffiliation, Role
from .models import (
    Category,
    InventoryItem,
    InventoryRequest,
    ItemHolderLog,
    ManualAttendee,
    Personnel,
    Staff,
    StockMovement,
    TrainingRecord,
    TrainingRegistration,
    TrainingSchedule,
    UserProfile,
    profile_for,
)
from .views import PersonnelViewSet


class MunicipalityConstantsTests(TestCase):
    def test_counts(self):
        self.assertEqual(len(reference.DISTRICTS), 4)
        self.assertEqual(len(reference.MUNICIPALITIES), 41)
        self.assertEqual(len(reference.MUNICIPALITY_DISTRICT), 41)
        self.assertEqual(len(reference.MUNICIPALITY_CHOICES), 41)

    def test_per_district_counts(self):
        counts = {d: 0 for d in reference.DISTRICTS}
        for district in reference.MUNICIPALITY_DISTRICT.values():
            counts[district] += 1
        self.assertEqual(
            counts,
            {
                reference.FIRST_DISTRICT: 13,
                reference.SECOND_DISTRICT: 6,
                reference.THIRD_DISTRICT: 12,
                reference.FOURTH_DISTRICT: 10,
            },
        )

    def test_no_duplicate_municipalities(self):
        self.assertEqual(len(reference.MUNICIPALITIES), len(set(reference.MUNICIPALITIES)))

    def test_municipalities_sorted(self):
        self.assertEqual(list(reference.MUNICIPALITIES), sorted(reference.MUNICIPALITIES))

    def test_district_for_spot_checks(self):
        self.assertEqual(reference.district_for("Tayabas City"), reference.FIRST_DISTRICT)
        self.assertEqual(reference.district_for("Lucena City"), reference.SECOND_DISTRICT)
        self.assertEqual(reference.district_for("Catanauan"), reference.THIRD_DISTRICT)
        self.assertEqual(reference.district_for("Tagkawayan"), reference.FOURTH_DISTRICT)

    def test_district_for_unknown_raises(self):
        with self.assertRaises(KeyError):
            reference.district_for("Nowhere")

    def test_ordered_rows_are_district_then_name(self):
        rows = reference.municipalities_by_district_then_name()
        self.assertEqual(len(rows), 41)
        seen_districts = list(dict.fromkeys(district for _name, district in rows))
        self.assertEqual(seen_districts, list(reference.DISTRICTS))
        for district in reference.DISTRICTS:
            names = [n for n, d in rows if d == district]
            self.assertEqual(names, sorted(names))


class TrainingCatalogConstantsTests(TestCase):
    def test_counts(self):
        self.assertEqual(len(reference.ManagerialTraining.choices), 15)
        self.assertEqual(len(reference.SkillsTraining.choices), 12)
        self.assertEqual(len(reference.TRAINING_CATALOG_CHOICES), 27)
        self.assertEqual(len(reference.VALID_TRAINING_KEYS), 27)

    def test_no_key_collisions_across_groups(self):
        managerial = set(reference.ManagerialTraining.values)
        skills = set(reference.SkillsTraining.values)
        self.assertEqual(managerial & skills, set())

    def test_keys_within_max_length(self):
        longest = max(len(k) for k in reference.VALID_TRAINING_KEYS)
        self.assertLessEqual(longest, reference.TRAINING_KEY_MAX_LENGTH)

    def test_training_group_and_label(self):
        self.assertEqual(reference.training_group("ICS_L1"), reference.MANAGERIAL)
        self.assertEqual(reference.training_group("CSSR"), reference.SKILLS)
        self.assertEqual(
            reference.training_label("RDANA"),
            "Rapid Damage Assessment & Needs Analysis (RDANA)",
        )

    def test_catalog_rows_order_managerial_then_skills(self):
        rows = reference.training_catalog_rows()
        groups = [group for _key, _label, group in rows]
        self.assertEqual(groups, [reference.MANAGERIAL] * 15 + [reference.SKILLS] * 12)
        self.assertEqual(rows[0][0], "ICS_L1")
        self.assertEqual(rows[-1][0], "CSSR")


class ReferenceEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = get_user_model().objects.create_user("tester", password="pw")
        self.client.force_authenticate(user=user)

    def test_municipalities_endpoint(self):
        resp = self.client.get("/api/municipalities/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body), 41)
        self.assertEqual(body[0], {"name": "Burdeos", "district": reference.FIRST_DISTRICT})
        self.assertEqual(set(body[0].keys()), {"name", "district"})
        districts_in_order = list(dict.fromkeys(row["district"] for row in body))
        self.assertEqual(districts_in_order, list(reference.DISTRICTS))

    def test_training_catalog_endpoint(self):
        resp = self.client.get("/api/training-catalog/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body), 27)
        self.assertEqual(set(body[0].keys()), {"key", "label", "group"})
        self.assertEqual(body[0]["key"], "ICS_L1")
        self.assertEqual(body[0]["group"], "MANAGERIAL")
        self.assertEqual([r["group"] for r in body].count("MANAGERIAL"), 15)
        self.assertEqual([r["group"] for r in body].count("SKILLS"), 12)

    def test_endpoints_require_authentication(self):
        anon = APIClient()
        self.assertEqual(anon.get("/api/municipalities/").status_code, 403)
        self.assertEqual(anon.get("/api/training-catalog/").status_code, 403)


class PersonnelModelTests(TestCase):
    def _make(self, **overrides):
        data = {"name": "Juan Dela Cruz", "municipality": "Tayabas City"}
        data.update(overrides)
        return Personnel.objects.create(**data)

    def test_defaults(self):
        p = self._make()
        self.assertEqual(p.org_affiliation, OrgAffiliation.EMPLOYEE)
        self.assertEqual(p.employment_status, "")
        self.assertEqual(p.designation, "")
        self.assertFalse(p.is_archived)
        self.assertIsNone(p.archived_at)
        self.assertIsNone(p.archived_by)
        self.assertIsNotNone(p.created_at)
        self.assertIsNotNone(p.updated_at)

    def test_district_is_computed_not_stored(self):
        p = self._make(municipality="Tayabas City")
        self.assertEqual(p.district, reference.FIRST_DISTRICT)
        self.assertEqual(self._make(municipality="Lucena City").district, reference.SECOND_DISTRICT)
        self.assertFalse(any(f.name == "district" for f in Personnel._meta.get_fields()))

    def test_municipality_choice_validates(self):
        with self.assertRaises(ValidationError):
            self._make(municipality="Nowhere").full_clean()

    def test_employment_status_is_free_text(self):
        # No DB-level choices (spec Section 6 Q#1 open) — arbitrary value is fine.
        p = self._make(employment_status="Job Order")
        p.full_clean()
        self.assertEqual(p.employment_status, "Job Order")


class TrainingRecordModelTests(TestCase):
    def setUp(self):
        self.p = Personnel.objects.create(name="Juan Dela Cruz", municipality="Tayabas City")

    def test_links_personnel_to_catalog_key(self):
        r = TrainingRecord.objects.create(personnel=self.p, training_key="BLS", year_attained=2021)
        self.assertIn(r.training_key, reference.VALID_TRAINING_KEYS)
        self.assertEqual(list(self.p.training_records.values_list("training_key", flat=True)), ["BLS"])

    def test_invalid_training_key_fails_full_clean(self):
        with self.assertRaises(ValidationError):
            TrainingRecord(personnel=self.p, training_key="NOT_A_KEY", year_attained=2021).full_clean()

    def test_unique_together_personnel_training_key(self):
        TrainingRecord.objects.create(personnel=self.p, training_key="BLS", year_attained=2021)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TrainingRecord.objects.create(personnel=self.p, training_key="BLS", year_attained=2023)

    def test_same_key_allowed_for_different_personnel(self):
        other = Personnel.objects.create(name="Maria Santos", municipality="Lucena City")
        TrainingRecord.objects.create(personnel=self.p, training_key="BLS", year_attained=2021)
        TrainingRecord.objects.create(personnel=other, training_key="BLS", year_attained=2021)  # no raise

    def test_year_attained_bounds(self):
        for bad in (TRAINING_YEAR_MIN - 1, TRAINING_YEAR_MAX + 1):
            with self.assertRaises(ValidationError):
                TrainingRecord(personnel=self.p, training_key="SFA", year_attained=bad).full_clean()
        for ok in (TRAINING_YEAR_MIN, 2020, TRAINING_YEAR_MAX):
            TrainingRecord(personnel=self.p, training_key="SFA", year_attained=ok).full_clean()  # no raise


# --------------------------------------------------------------------------
# Step 3b — Personnel / Training Matrix CRUD API
# --------------------------------------------------------------------------

User = get_user_model()


def make_user(username, role=Role.STAFF, can_delete=False, superuser=False):
    if superuser:
        return User.objects.create_superuser(username, "", "pw")
    u = User.objects.create_user(username, password="pw")
    p = profile_for(u)  # signal already created it; this is the safe accessor
    p.role = role
    p.can_permanently_delete = can_delete
    p.save()
    return u


class UserProfileSignalTests(TestCase):
    def test_profile_auto_created_for_new_user(self):
        u = User.objects.create_user("fresh", password="pw")
        self.assertTrue(UserProfile.objects.filter(user=u).exists())
        self.assertEqual(u.profile.role, Role.STAFF)
        self.assertFalse(u.profile.can_permanently_delete)

    def test_profile_for_is_idempotent(self):
        u = User.objects.create_user("x", password="pw")
        self.assertEqual(profile_for(u).pk, profile_for(u).pk)
        self.assertEqual(UserProfile.objects.filter(user=u).count(), 1)


class PersonnelPermissionTests(TestCase):
    def setUp(self):
        self.staff = make_user("staff", role=Role.STAFF)
        self.admin = make_user("admin", role=Role.ADMIN)
        self.admin_del = make_user("admindel", role=Role.ADMIN, can_delete=True)
        self.superuser = make_user("root", superuser=True)
        self.p = Personnel.objects.create(name="Juan", municipality="Tayabas City")

    def _client(self, user=None):
        c = APIClient()
        if user:
            c.force_authenticate(user=user)
        return c

    def test_unauthenticated_blocked(self):
        self.assertEqual(self._client().get("/api/personnel/").status_code, 403)

    def test_staff_blocked_on_every_route(self):
        c = self._client(self.staff)
        pk = self.p.pk
        self.assertEqual(c.get("/api/personnel/").status_code, 403)
        self.assertEqual(c.post("/api/personnel/", {"name": "N", "municipality": "Lucban"}).status_code, 403)
        self.assertEqual(c.get(f"/api/personnel/{pk}/").status_code, 403)
        self.assertEqual(c.patch(f"/api/personnel/{pk}/", {"name": "X"}).status_code, 403)
        self.assertEqual(c.delete(f"/api/personnel/{pk}/").status_code, 403)
        self.assertEqual(c.post(f"/api/personnel/{pk}/restore/").status_code, 403)
        self.assertEqual(c.delete(f"/api/personnel/{pk}/permanent-delete/").status_code, 403)
        self.assertEqual(
            c.patch(f"/api/personnel/{pk}/training-record/BLS/", {"year_attained": 2020}).status_code,
            403,
        )

    def test_admin_allowed_on_crud_routes(self):
        c = self._client(self.admin)
        self.assertEqual(c.get("/api/personnel/").status_code, 200)
        created = c.post("/api/personnel/", {"name": "New", "municipality": "Lucban"})
        self.assertEqual(created.status_code, 201)
        pk = created.json()["id"]
        self.assertEqual(c.get(f"/api/personnel/{pk}/").status_code, 200)
        self.assertEqual(c.patch(f"/api/personnel/{pk}/", {"designation": "Lead"}).status_code, 200)
        self.assertEqual(
            c.patch(f"/api/personnel/{pk}/training-record/BLS/", {"year_attained": 2020}).status_code,
            200,
        )

    def test_permanent_delete_requires_flag(self):
        # archive first so the 409-precondition doesn't mask the permission check
        for u in (self.admin, self.admin_del):
            person = Personnel.objects.create(name="T", municipality="Lucban", is_archived=True)
            code = self._client(u).delete(f"/api/personnel/{person.pk}/permanent-delete/").status_code
            self.assertEqual(code, 403 if u is self.admin else 204)

    def test_superuser_is_admin_and_can_permanently_delete(self):
        c = self._client(self.superuser)
        self.assertEqual(c.get("/api/personnel/").status_code, 200)
        person = Personnel.objects.create(name="T", municipality="Lucban", is_archived=True)
        self.assertEqual(c.delete(f"/api/personnel/{person.pk}/permanent-delete/").status_code, 204)


class PersonnelArchiveLifecycleTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin", role=Role.ADMIN)
        self.admin_del = make_user("admindel", role=Role.ADMIN, can_delete=True)
        self.c = APIClient()
        self.c.force_authenticate(user=self.admin)
        self.p = Personnel.objects.create(name="Juan", municipality="Tayabas City")

    def test_delete_soft_archives_with_audit_stamp(self):
        resp = self.c.delete(f"/api/personnel/{self.p.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.p.refresh_from_db()
        self.assertTrue(self.p.is_archived)
        self.assertIsNotNone(self.p.archived_at)
        self.assertEqual(self.p.archived_by, self.admin)
        self.assertEqual(resp.json()["archived_by"], "admin")  # username string
        self.assertTrue(Personnel.objects.filter(pk=self.p.pk).exists())  # row still there

    def test_archive_is_idempotent(self):
        self.c.delete(f"/api/personnel/{self.p.pk}/")
        self.p.refresh_from_db()
        first_stamp = self.p.archived_at
        resp = self.c.delete(f"/api/personnel/{self.p.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.p.refresh_from_db()
        self.assertEqual(self.p.archived_at, first_stamp)  # unchanged, not re-stamped

    def test_restore_clears_archive_state(self):
        self.c.delete(f"/api/personnel/{self.p.pk}/")
        resp = self.c.post(f"/api/personnel/{self.p.pk}/restore/")
        self.assertEqual(resp.status_code, 200)
        self.p.refresh_from_db()
        self.assertFalse(self.p.is_archived)
        self.assertIsNone(self.p.archived_at)
        self.assertIsNone(self.p.archived_by)

    def test_restore_is_idempotent_on_active_record(self):
        resp = self.c.post(f"/api/personnel/{self.p.pk}/restore/")
        self.assertEqual(resp.status_code, 200)
        self.p.refresh_from_db()
        self.assertFalse(self.p.is_archived)

    def test_permanent_delete_blocked_unless_archived(self):
        c = APIClient()
        c.force_authenticate(user=self.admin_del)
        resp = c.delete(f"/api/personnel/{self.p.pk}/permanent-delete/")
        self.assertEqual(resp.status_code, 409)
        self.assertTrue(Personnel.objects.filter(pk=self.p.pk).exists())

    def test_permanent_delete_removes_row_and_cascades_records(self):
        TrainingRecord.objects.create(personnel=self.p, training_key="BLS", year_attained=2020)
        self.c.delete(f"/api/personnel/{self.p.pk}/")  # archive
        c = APIClient()
        c.force_authenticate(user=self.admin_del)
        resp = c.delete(f"/api/personnel/{self.p.pk}/permanent-delete/")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Personnel.objects.filter(pk=self.p.pk).exists())
        self.assertEqual(TrainingRecord.objects.count(), 0)

    def test_archived_record_is_read_only_except_restore(self):
        self.c.delete(f"/api/personnel/{self.p.pk}/")
        self.assertEqual(
            self.c.patch(f"/api/personnel/{self.p.pk}/", {"designation": "Nope"}).status_code, 409
        )
        self.assertEqual(
            self.c.patch(
                f"/api/personnel/{self.p.pk}/training-record/BLS/", {"year_attained": 2020}
            ).status_code,
            409,
        )
        # restore still works
        self.assertEqual(self.c.post(f"/api/personnel/{self.p.pk}/restore/").status_code, 200)

    def test_write_only_fields_ignored_in_patch_body(self):
        resp = self.c.patch(
            f"/api/personnel/{self.p.pk}/",
            {"is_archived": True, "district": "Fourth District", "archived_by": 999},
        )
        self.assertEqual(resp.status_code, 200)
        self.p.refresh_from_db()
        self.assertFalse(self.p.is_archived)
        self.assertEqual(resp.json()["district"], reference.FIRST_DISTRICT)  # still computed


class TrainingRecordCellTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin", role=Role.ADMIN)
        self.c = APIClient()
        self.c.force_authenticate(user=self.admin)
        self.p = Personnel.objects.create(name="Juan", municipality="Tayabas City")
        self.url = f"/api/personnel/{self.p.pk}/training-record/"

    def _patch(self, key, body):
        # JSON so `year_attained: null` round-trips (multipart can't encode None).
        return self.c.patch(self.url + key + "/", body, format="json")

    def test_upsert_creates_then_updates_in_place(self):
        r1 = self._patch("BLS", {"year_attained": 2021})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()["training_key"], "BLS")
        self.assertEqual(r1.json()["year_attained"], 2021)
        self.assertEqual(self.p.training_records.count(), 1)

        r2 = self._patch("BLS", {"year_attained": 2024})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["year_attained"], 2024)
        self.assertEqual(self.p.training_records.count(), 1)  # still one row

    def test_clear_deletes_cell_and_is_idempotent(self):
        self._patch("BLS", {"year_attained": 2021})
        r1 = self._patch("BLS", {"year_attained": None})
        self.assertEqual(r1.status_code, 204)
        self.assertEqual(self.p.training_records.count(), 0)
        r2 = self._patch("BLS", {"year_attained": None})  # nothing to clear
        self.assertEqual(r2.status_code, 204)

    def test_unknown_training_key_is_404(self):
        self.assertEqual(self._patch("NOPE", {"year_attained": 2021}).status_code, 404)

    def test_year_out_of_range_is_400(self):
        self.assertEqual(self._patch("BLS", {"year_attained": TRAINING_YEAR_MIN - 1}).status_code, 400)
        self.assertEqual(self._patch("BLS", {"year_attained": TRAINING_YEAR_MAX + 1}).status_code, 400)

    def test_missing_year_attained_key_is_400(self):
        self.assertEqual(self._patch("BLS", {}).status_code, 400)

    def test_upsert_falls_back_to_update_on_integrity_race(self):
        # Simulate a concurrent insert winning the race: the row already exists
        # and update_or_create raises IntegrityError on its create path.
        TrainingRecord.objects.create(personnel=self.p, training_key="BLS", year_attained=2019)
        with patch.object(
            TrainingRecord.objects, "update_or_create", side_effect=IntegrityError("dup")
        ):
            record = PersonnelViewSet._upsert_cell(self.p, "BLS", 2030)
        record.refresh_from_db()
        self.assertEqual(record.year_attained, 2030)
        self.assertEqual(self.p.training_records.count(), 1)


class PersonnelListFilterTests(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.c.force_authenticate(user=make_user("admin", role=Role.ADMIN))
        # Tayabas City + Lucban are First District; Lucena City is Second.
        self.tayabas = Personnel.objects.create(name="A", municipality="Tayabas City")
        self.lucban = Personnel.objects.create(name="B", municipality="Lucban")
        self.lucena = Personnel.objects.create(name="C", municipality="Lucena City")
        self.archived = Personnel.objects.create(
            name="D", municipality="Tayabas City", is_archived=True
        )

    def _names(self, query=""):
        resp = self.c.get(f"/api/personnel/{query}")
        self.assertEqual(resp.status_code, 200)
        return sorted(row["name"] for row in resp.json())

    def test_default_returns_active_only(self):
        self.assertEqual(self._names(), ["A", "B", "C"])

    def test_archived_true_returns_archived_only(self):
        self.assertEqual(self._names("?archived=true"), ["D"])

    def test_archived_false_same_as_default(self):
        self.assertEqual(self._names("?archived=false"), ["A", "B", "C"])

    def test_archived_all_returns_both(self):
        self.assertEqual(self._names("?archived=all"), ["A", "B", "C", "D"])

    def test_filter_by_municipality(self):
        self.assertEqual(self._names("?municipality=Tayabas City"), ["A"])

    def test_filter_by_district(self):
        self.assertEqual(self._names("?district=First District"), ["A", "B"])

    def test_unknown_municipality_returns_empty(self):
        self.assertEqual(self._names("?municipality=Nowhere"), [])

    def test_unknown_district_returns_empty(self):
        self.assertEqual(self._names("?district=Fifth District"), [])

    def test_training_records_always_embedded(self):
        TrainingRecord.objects.create(personnel=self.tayabas, training_key="BLS", year_attained=2020)
        row = next(r for r in self.c.get("/api/personnel/").json() if r["name"] == "A")
        self.assertEqual(row["training_records"], [
            {"training_key": "BLS", "year_attained": 2020, "updated_at": row["training_records"][0]["updated_at"]}
        ])
        detail = self.c.get(f"/api/personnel/{self.tayabas.pk}/").json()
        self.assertEqual(len(detail["training_records"]), 1)


# --------------------------------------------------------------------------
# Step 5a — Inventory core models (spec Section 3.1)
# --------------------------------------------------------------------------


class InventoryCoreModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("invtester", password="pw")
        self.cat = Category.objects.create(name="Radios", description="Comms gear")
        self.staff = Staff.objects.create(first_name="Ana", last_name="Cruz")
        self.item = InventoryItem.objects.create(
            category=self.cat, name="Handheld VHF", quantity=5, unit="unit"
        )

    # --- Category ---

    def test_category_defaults_and_str(self):
        self.assertEqual(str(self.cat), "Radios")
        self.assertIsNotNone(self.cat.created_at)
        self.assertIsNotNone(self.cat.updated_at)

    def test_category_name_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Category.objects.create(name="Radios")

    def test_category_has_no_icon_field(self):
        self.assertFalse(any(f.name == "icon" for f in Category._meta.get_fields()))

    # --- Staff ---

    def test_staff_full_name_and_defaults(self):
        self.assertEqual(self.staff.full_name, "Ana Cruz")
        self.assertEqual(str(self.staff), "Ana Cruz")
        self.assertEqual(self.staff.status, Staff.Status.PERMANENT)
        self.assertFalse(self.staff.is_archived)
        self.assertIsNone(self.staff.archived_at)
        self.assertIsNone(self.staff.archived_by)

    def test_staff_status_choice_validation(self):
        self.staff.status = "BOGUS"
        with self.assertRaises(ValidationError):
            self.staff.full_clean()

    def test_staff_archive_triple(self):
        # 2.3: full is_archived + archived_at + archived_by, like Personnel
        for name in ("is_archived", "archived_at", "archived_by"):
            self.assertTrue(any(f.name == name for f in Staff._meta.get_fields()), name)
        now = timezone.now()
        self.staff.is_archived = True
        self.staff.archived_at = now
        self.staff.archived_by = self.user
        self.staff.save()
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_archived)
        self.assertEqual(self.staff.archived_by, self.user)

    def test_staff_photo_is_imagefield_optional(self):
        from django.db.models import ImageField

        field = Staff._meta.get_field("photo")
        self.assertIsInstance(field, ImageField)
        self.assertTrue(field.null and field.blank)

    # --- InventoryItem ---

    def test_item_defaults_and_fk(self):
        self.assertEqual(self.item.category, self.cat)
        self.assertEqual(self.item.quantity, 5)
        self.assertEqual(self.item.condition, InventoryItem.Condition.GOOD)
        self.assertIsNone(self.item.memorandum_receipt)
        self.assertIn(self.item, self.cat.items.all())

    def test_item_condition_choice_validation(self):
        self.item.condition = "MELTED"
        with self.assertRaises(ValidationError):
            self.item.full_clean()

    def test_item_unit_is_free_text(self):
        self.item.unit = "whatever-crate"
        self.item.full_clean()  # no raise — 2.11

    def test_item_quantity_rejects_negative(self):
        self.item.quantity = -1
        with self.assertRaises(ValidationError):
            self.item.full_clean()

    def test_item_memorandum_receipt_set_null_on_staff_delete(self):
        self.item.memorandum_receipt = self.staff
        self.item.save()
        self.assertIn(self.item, self.staff.held_items.all())
        self.staff.delete()
        self.item.refresh_from_db()
        self.assertIsNone(self.item.memorandum_receipt)

    def test_item_archive_triple(self):
        for name in ("is_archived", "archived_at", "archived_by"):
            self.assertTrue(any(f.name == name for f in InventoryItem._meta.get_fields()), name)

    def test_category_delete_cascades_items(self):
        self.assertEqual(InventoryItem.objects.count(), 1)
        self.cat.delete()
        self.assertEqual(InventoryItem.objects.count(), 0)

    # --- ItemHolderLog ---

    def test_holder_log_relationships_and_action(self):
        log = ItemHolderLog.objects.create(
            item=self.item, staff=self.staff, action=ItemHolderLog.Action.ASSIGNED,
            performed_by=self.user, note="initial issue",
        )
        self.assertIn(log, self.item.holder_logs.all())
        self.assertIsNotNone(log.timestamp)
        log.action = "TELEPORTED"
        with self.assertRaises(ValidationError):
            log.full_clean()

    def test_holder_log_cascades_on_item_delete(self):
        ItemHolderLog.objects.create(item=self.item, action=ItemHolderLog.Action.ASSIGNED)
        self.item.delete()
        self.assertEqual(ItemHolderLog.objects.count(), 0)

    def test_holder_log_performed_by_set_null_on_user_delete(self):
        log = ItemHolderLog.objects.create(
            item=self.item, action=ItemHolderLog.Action.REMOVED, performed_by=self.user
        )
        self.user.delete()
        log.refresh_from_db()
        self.assertIsNone(log.performed_by)

    # --- StockMovement ---

    def test_stock_movement_fields(self):
        mv = StockMovement.objects.create(
            item=self.item, quantity=3, movement_type=StockMovement.MovementType.IN,
            performed_by=self.user,
        )
        self.assertIn(mv, self.item.movements.all())
        self.assertIsNotNone(mv.created_at)

    def test_stock_movement_type_validation_and_positive_quantity(self):
        mv = StockMovement(item=self.item, quantity=1, movement_type="SIDEWAYS")
        with self.assertRaises(ValidationError):
            mv.full_clean()
        mv2 = StockMovement(item=self.item, quantity=-2, movement_type=StockMovement.MovementType.OUT)
        with self.assertRaises(ValidationError):
            mv2.full_clean()

    def test_stock_movement_cascades_on_item_delete(self):
        StockMovement.objects.create(
            item=self.item, quantity=1, movement_type=StockMovement.MovementType.IN
        )
        self.item.delete()
        self.assertEqual(StockMovement.objects.count(), 0)

    # --- InventoryRequest ---

    def test_request_defaults_and_relationships(self):
        req = InventoryRequest.objects.create(
            requested_by=self.user, item=self.item, quantity=2
        )
        self.assertEqual(req.status, InventoryRequest.Status.PENDING)
        self.assertIsNone(req.decided_by)
        self.assertIsNone(req.decided_at)
        self.assertIn(req, self.user.inventory_requests.all())
        self.assertIn(req, self.item.requests.all())

    def test_request_status_validation(self):
        req = InventoryRequest(requested_by=self.user, item=self.item, quantity=1, status="MAYBE")
        with self.assertRaises(ValidationError):
            req.full_clean()

    def test_request_cascades_on_requester_delete(self):
        InventoryRequest.objects.create(requested_by=self.user, item=self.item, quantity=1)
        self.user.delete()
        self.assertEqual(InventoryRequest.objects.count(), 0)

    def test_request_decided_by_set_null_on_user_delete(self):
        decider = User.objects.create_user("decider", password="pw")
        req = InventoryRequest.objects.create(
            requested_by=self.user, item=self.item, quantity=1,
            status=InventoryRequest.Status.APPROVED, decided_by=decider,
            decided_at=timezone.now(),
        )
        decider.delete()
        req.refresh_from_db()
        self.assertIsNone(req.decided_by)
        self.assertIsNotNone(req.decided_at)


# --------------------------------------------------------------------------
# Step 5b — Training-event models (spec Section 3.2)
# --------------------------------------------------------------------------


class TrainingScheduleModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("sched", password="pw")
        self.sched = TrainingSchedule.objects.create(
            title="ICS Level 1 Batch 3",
            date_start=datetime.date(2026, 6, 1),
            created_by=self.user,
        )

    def test_defaults_and_str(self):
        self.assertEqual(str(self.sched), "ICS Level 1 Batch 3")
        self.assertEqual(self.sched.status, TrainingSchedule.Status.UPCOMING)
        self.assertEqual(self.sched.matrix_training_key, "")
        self.assertFalse(self.sched.is_archived)
        self.assertIsNone(self.sched.archived_at)
        self.assertIsNone(self.sched.archived_by)
        self.assertIsNotNone(self.sched.created_at)
        self.assertIsNotNone(self.sched.updated_at)

    def test_status_choice_validation(self):
        self.sched.status = "PENCILLED_IN"
        with self.assertRaises(ValidationError):
            self.sched.full_clean()

    def test_status_and_archive_are_orthogonal(self):
        # 2.3: archiving is not a status=CANCELLED overload.
        self.sched.status = TrainingSchedule.Status.COMPLETED
        self.sched.is_archived = True
        self.sched.archived_at = timezone.now()
        self.sched.archived_by = self.user
        self.sched.full_clean()
        self.sched.save()
        self.sched.refresh_from_db()
        self.assertEqual(self.sched.status, TrainingSchedule.Status.COMPLETED)
        self.assertTrue(self.sched.is_archived)
        self.assertEqual(self.sched.archived_by, self.user)

    def test_archive_triple_present(self):
        for name in ("is_archived", "archived_at", "archived_by"):
            self.assertTrue(
                any(f.name == name for f in TrainingSchedule._meta.get_fields()), name
            )

    def test_matrix_training_key_accepts_catalog_key_and_blank(self):
        self.sched.matrix_training_key = "ICS_L1"
        self.sched.full_clean()  # valid catalog key
        self.sched.matrix_training_key = ""
        self.sched.full_clean()  # blank = event only

    def test_matrix_training_key_rejects_non_catalog_value(self):
        self.sched.matrix_training_key = "NOT_A_KEY"
        with self.assertRaises(ValidationError):
            self.sched.full_clean()

    def test_matrix_training_key_is_not_nullable(self):
        self.assertFalse(TrainingSchedule._meta.get_field("matrix_training_key").null)

    def test_created_by_set_null_on_user_delete(self):
        self.user.delete()
        self.sched.refresh_from_db()
        self.assertIsNone(self.sched.created_by)


class TrainingRegistrationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("reg", password="pw")
        self.sched = TrainingSchedule.objects.create(
            title="WASAR", date_start=datetime.date(2026, 7, 1)
        )

    def test_defaults_and_relationships(self):
        r = TrainingRegistration.objects.create(training=self.sched, user=self.user)
        self.assertEqual(r.status, TrainingRegistration.Status.REGISTERED)
        self.assertIsNone(r.cancelled_at)
        self.assertFalse(r.attended)
        self.assertIsNotNone(r.registered_at)
        self.assertIn(r, self.sched.registrations.all())
        self.assertIn(r, self.user.training_registrations.all())

    def test_status_choice_validation(self):
        r = TrainingRegistration(training=self.sched, user=self.user, status="GHOSTED")
        with self.assertRaises(ValidationError):
            r.full_clean()

    def test_no_unique_together_on_training_user(self):
        # 2.6: a CANCELLED row plus a later REGISTERED row for the same pair
        # must both be allowed at the DB level.
        self.assertEqual(TrainingRegistration._meta.unique_together, ())
        TrainingRegistration.objects.create(
            training=self.sched, user=self.user,
            status=TrainingRegistration.Status.CANCELLED, cancelled_at=timezone.now(),
        )
        TrainingRegistration.objects.create(training=self.sched, user=self.user)  # no raise
        self.assertEqual(
            TrainingRegistration.objects.filter(training=self.sched, user=self.user).count(), 2
        )

    def test_cascade_on_training_delete(self):
        TrainingRegistration.objects.create(training=self.sched, user=self.user)
        self.sched.delete()
        self.assertEqual(TrainingRegistration.objects.count(), 0)

    def test_cascade_on_user_delete(self):
        TrainingRegistration.objects.create(training=self.sched, user=self.user)
        self.user.delete()
        self.assertEqual(TrainingRegistration.objects.count(), 0)


class ManualAttendeeModelTests(TestCase):
    def setUp(self):
        self.sched = TrainingSchedule.objects.create(
            title="CBDRRM", date_start=datetime.date(2026, 8, 1)
        )

    def _make(self, **overrides):
        data = {"training": self.sched, "name": "Pedro Reyes", "municipality": "Mauban"}
        data.update(overrides)
        return ManualAttendee.objects.create(**data)

    def test_defaults_and_relationships(self):
        a = self._make()
        self.assertEqual(a.org_affiliation, OrgAffiliation.EMPLOYEE)
        self.assertFalse(a.attended)
        self.assertEqual(a.designation, "")
        self.assertIsNotNone(a.created_at)
        self.assertIn(a, self.sched.manual_attendees.all())

    def test_municipality_choice_validation(self):
        with self.assertRaises(ValidationError):
            self._make(municipality="Atlantis").full_clean()

    def test_org_affiliation_choice_validation(self):
        with self.assertRaises(ValidationError):
            self._make(org_affiliation="CONTRACTOR").full_clean()

    def test_org_affiliation_uses_shared_choices_class(self):
        # 2.5: models.py imports choices.OrgAffiliation — it is the very same
        # class object, not a re-declared enum that merely looks identical.
        self.assertIs(core_models.OrgAffiliation, core_choices.OrgAffiliation)
        self.assertEqual(
            ManualAttendee._meta.get_field("org_affiliation").choices,
            core_choices.OrgAffiliation.choices,
        )

    def test_cascade_on_training_delete(self):
        self._make()
        self._make(name="Juana Cruz")
        self.assertEqual(self.sched.manual_attendees.count(), 2)
        self.sched.delete()
        self.assertEqual(ManualAttendee.objects.count(), 0)


# --------------------------------------------------------------------------
# Step 6a — catalog + custody CRUD (spec Section 4)
# --------------------------------------------------------------------------

# ImageField.save() writes bytes without image validation; the remove_photo
# PATCH path never re-validates the photo, so placeholder bytes are fine.
_FAKE_IMAGE = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


class Step6aPermissionTests(TestCase):
    def setUp(self):
        self.staff = make_user("s", role=Role.STAFF)
        self.admin = make_user("a", role=Role.ADMIN)
        self.admin_del = make_user("ad", role=Role.ADMIN, can_delete=True)
        self.cat = Category.objects.create(name="Radios")
        self.person = Staff.objects.create(first_name="Ana", last_name="Cruz")
        self.item = InventoryItem.objects.create(category=self.cat, name="VHF", quantity=3)

    def c(self, user):
        cl = APIClient()
        cl.force_authenticate(user=user)
        return cl

    def test_categories_admin_only(self):
        s = self.c(self.staff)
        self.assertEqual(s.get("/api/categories/").status_code, 403)
        self.assertEqual(s.post("/api/categories/", {"name": "X"}).status_code, 403)
        self.assertEqual(s.patch(f"/api/categories/{self.cat.pk}/", {"name": "Y"}).status_code, 403)
        self.assertEqual(s.delete(f"/api/categories/{self.cat.pk}/").status_code, 403)
        a = self.c(self.admin)
        self.assertEqual(a.get("/api/categories/").status_code, 200)
        self.assertEqual(a.post("/api/categories/", {"name": "New Cat"}).status_code, 201)

    def test_staff_admin_only_and_permanent_delete_gate(self):
        s = self.c(self.staff)
        pk = self.person.pk
        for call in (
            lambda: s.get("/api/staff/"),
            lambda: s.post("/api/staff/", {"first_name": "B", "last_name": "C"}),
            lambda: s.get(f"/api/staff/{pk}/"),
            lambda: s.patch(f"/api/staff/{pk}/", {"position": "x"}),
            lambda: s.delete(f"/api/staff/{pk}/"),
            lambda: s.get("/api/staff/archived/"),
            lambda: s.post(f"/api/staff/{pk}/restore/"),
            lambda: s.delete(f"/api/staff/{pk}/permanent-delete/"),
        ):
            self.assertEqual(call().status_code, 403)
        a = self.c(self.admin)
        self.assertEqual(a.get("/api/staff/").status_code, 200)
        arch = Staff.objects.create(first_name="T", last_name="T", is_archived=True)
        self.assertEqual(a.delete(f"/api/staff/{arch.pk}/permanent-delete/").status_code, 403)
        self.assertEqual(
            self.c(self.admin_del).delete(f"/api/staff/{arch.pk}/permanent-delete/").status_code, 204
        )

    def test_items_staff_can_read_active_only(self):
        s = self.c(self.staff)
        self.assertEqual(s.get("/api/items/").status_code, 200)
        self.assertEqual(s.get(f"/api/items/{self.item.pk}/").status_code, 200)
        self.assertEqual(s.post("/api/items/", {"category": self.cat.pk, "name": "z"}).status_code, 403)
        self.assertEqual(s.patch(f"/api/items/{self.item.pk}/", {"name": "z"}).status_code, 403)
        self.assertEqual(s.delete(f"/api/items/{self.item.pk}/").status_code, 403)
        self.assertEqual(s.get("/api/items/archived/").status_code, 403)
        self.assertEqual(s.get(f"/api/items/{self.item.pk}/holder-history/").status_code, 403)
        InventoryItem.objects.create(category=self.cat, name="hidden", is_archived=True)
        names = {r["name"] for r in s.get("/api/items/").json()}
        self.assertEqual(names, {"VHF"})

    def test_items_permanent_delete_gate(self):
        arch = InventoryItem.objects.create(category=self.cat, name="old", is_archived=True)
        self.assertEqual(
            self.c(self.admin).delete(f"/api/items/{arch.pk}/permanent-delete/").status_code, 403
        )
        self.assertEqual(
            self.c(self.admin_del).delete(f"/api/items/{arch.pk}/permanent-delete/").status_code, 204
        )

    def test_unauthenticated_blocked_everywhere(self):
        anon = APIClient()
        self.assertEqual(anon.get("/api/categories/").status_code, 403)
        self.assertEqual(anon.get("/api/staff/").status_code, 403)
        self.assertEqual(anon.get("/api/items/").status_code, 403)


class Step6aArchiveLifecycleTests(TestCase):
    def setUp(self):
        self.admin = make_user("a", role=Role.ADMIN)
        self.admin_del = make_user("ad", role=Role.ADMIN, can_delete=True)
        self.c = APIClient()
        self.c.force_authenticate(user=self.admin)
        self.cat = Category.objects.create(name="Tools")
        self.item = InventoryItem.objects.create(category=self.cat, name="Spreader", quantity=2)
        self.staff = Staff.objects.create(first_name="Ben", last_name="Uy")

    def test_staff_archive_restore_permanent_delete(self):
        pk = self.staff.pk
        r = self.c.delete(f"/api/staff/{pk}/")
        self.assertEqual(r.status_code, 200)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_archived)
        self.assertIsNotNone(self.staff.archived_at)
        self.assertEqual(self.staff.archived_by, self.admin)
        self.assertEqual(r.json()["archived_by"], "a")
        self.assertNotIn(pk, [x["id"] for x in self.c.get("/api/staff/").json()])
        self.assertIn(pk, [x["id"] for x in self.c.get("/api/staff/archived/").json()])
        self.assertEqual(self.c.patch(f"/api/staff/{pk}/", {"position": "x"}).status_code, 409)
        self.assertEqual(self.c.delete(f"/api/staff/{pk}/").status_code, 200)  # idempotent
        self.assertEqual(self.c.delete(f"/api/staff/{pk}/permanent-delete/").status_code, 403)
        cd = APIClient()
        cd.force_authenticate(user=self.admin_del)
        self.assertEqual(cd.delete(f"/api/staff/{pk}/permanent-delete/").status_code, 204)
        self.assertFalse(Staff.objects.filter(pk=pk).exists())

    def test_staff_restore_clears_state(self):
        pk = self.staff.pk
        self.c.delete(f"/api/staff/{pk}/")
        r = self.c.post(f"/api/staff/{pk}/restore/")
        self.assertEqual(r.status_code, 200)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_archived)
        self.assertIsNone(self.staff.archived_at)
        self.assertIsNone(self.staff.archived_by)
        self.assertEqual(self.c.post(f"/api/staff/{pk}/restore/").status_code, 200)

    def test_item_archive_lifecycle_and_permanent_delete_precondition(self):
        pk = self.item.pk
        cd = APIClient()
        cd.force_authenticate(user=self.admin_del)
        # elevated user, but item not archived -> 409 precondition
        self.assertEqual(cd.delete(f"/api/items/{pk}/permanent-delete/").status_code, 409)
        self.assertEqual(self.c.delete(f"/api/items/{pk}/").status_code, 200)
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_archived)
        self.assertEqual(self.c.patch(f"/api/items/{pk}/", {"name": "z"}).status_code, 409)
        self.assertIn(pk, [x["id"] for x in self.c.get("/api/items/archived/").json()])
        self.assertEqual(self.c.post(f"/api/items/{pk}/restore/").status_code, 200)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_archived)
        # now archived + elevated -> 204
        self.c.delete(f"/api/items/{pk}/")
        self.assertEqual(cd.delete(f"/api/items/{pk}/permanent-delete/").status_code, 204)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="core-test-media-"))
class Step6aRemovePhotoTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        from django.conf import settings

        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.c = APIClient()
        self.c.force_authenticate(user=make_user("a", role=Role.ADMIN))
        self.staff = Staff.objects.create(first_name="Ana", last_name="Cruz")
        self.staff.photo.save(
            "p.png", SimpleUploadedFile("p.png", _FAKE_IMAGE, "image/png"), save=True
        )

    def test_remove_photo_clears_the_field(self):
        self.assertTrue(self.staff.photo)
        r = self.c.patch(f"/api/staff/{self.staff.pk}/", {"remove_photo": "true"})
        self.assertEqual(r.status_code, 200)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.photo)
        self.assertIsNone(r.json()["photo"])

    def test_patch_without_remove_photo_keeps_it(self):
        r = self.c.patch(f"/api/staff/{self.staff.pk}/", {"position": "Head"})
        self.assertEqual(r.status_code, 200)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.photo)
        self.assertEqual(self.staff.position, "Head")

    def test_remove_photo_falsy_value_is_ignored(self):
        r = self.c.patch(f"/api/staff/{self.staff.pk}/", {"remove_photo": "false"})
        self.assertEqual(r.status_code, 200)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.photo)


class Step6aHolderLogTests(TestCase):
    def setUp(self):
        self.admin = make_user("a", role=Role.ADMIN)
        self.c = APIClient()
        self.c.force_authenticate(user=self.admin)
        self.cat = Category.objects.create(name="Gear")
        self.a = Staff.objects.create(first_name="Aa", last_name="Aa")
        self.b = Staff.objects.create(first_name="Bb", last_name="Bb")

    def test_create_with_holder_writes_assigned_log(self):
        r = self.c.post(
            "/api/items/",
            {"category": self.cat.pk, "name": "Radio", "memorandum_receipt": self.a.pk},
        )
        self.assertEqual(r.status_code, 201)
        item = InventoryItem.objects.get(pk=r.json()["id"])
        logs = list(item.holder_logs.all())
        self.assertEqual(len(logs), 1)
        self.assertEqual(
            (logs[0].action, logs[0].staff_id, logs[0].performed_by),
            (ItemHolderLog.Action.ASSIGNED, self.a.pk, self.admin),
        )

    def test_create_without_holder_writes_no_log(self):
        r = self.c.post("/api/items/", {"category": self.cat.pk, "name": "Rope"})
        item = InventoryItem.objects.get(pk=r.json()["id"])
        self.assertEqual(item.holder_logs.count(), 0)

    def test_patch_changing_holder_writes_removed_then_assigned(self):
        item = InventoryItem.objects.create(
            category=self.cat, name="Drone", memorandum_receipt=self.a
        )
        ItemHolderLog.objects.create(item=item, staff=self.a, action=ItemHolderLog.Action.ASSIGNED)
        r = self.c.patch(
            f"/api/items/{item.pk}/",
            {"memorandum_receipt": self.b.pk, "holder_note": "reassigned"},
        )
        self.assertEqual(r.status_code, 200)
        new_logs = list(item.holder_logs.order_by("id"))[1:]
        self.assertEqual(
            [(x.action, x.staff_id, x.note) for x in new_logs],
            [
                (ItemHolderLog.Action.REMOVED, self.a.pk, "reassigned"),
                (ItemHolderLog.Action.ASSIGNED, self.b.pk, "reassigned"),
            ],
        )

    def test_patch_clearing_holder_writes_removed_only(self):
        item = InventoryItem.objects.create(
            category=self.cat, name="Kit", memorandum_receipt=self.a
        )
        r = self.c.patch(
            f"/api/items/{item.pk}/", {"memorandum_receipt": None}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        logs = list(item.holder_logs.all())
        self.assertEqual(len(logs), 1)
        self.assertEqual(
            (logs[0].action, logs[0].staff_id), (ItemHolderLog.Action.REMOVED, self.a.pk)
        )

    def test_patch_no_holder_change_writes_no_log(self):
        item = InventoryItem.objects.create(
            category=self.cat, name="Case", memorandum_receipt=self.a
        )
        self.c.patch(f"/api/items/{item.pk}/", {"remarks": "scuffed"})
        self.assertEqual(item.holder_logs.count(), 0)

    def test_holder_history_endpoint_returns_logs_newest_first(self):
        item = InventoryItem.objects.create(category=self.cat, name="Bag")
        self.c.patch(f"/api/items/{item.pk}/", {"memorandum_receipt": self.a.pk})
        self.c.patch(f"/api/items/{item.pk}/", {"memorandum_receipt": self.b.pk})
        r = self.c.get(f"/api/items/{item.pk}/holder-history/")
        self.assertEqual(r.status_code, 200)
        rows = r.json()
        self.assertEqual(len(rows), 3)  # assign a, remove a, assign b
        self.assertEqual((rows[0]["action"], rows[0]["staff"]), ("ASSIGNED", self.b.pk))


class Step6aCategoryAndQuantityTests(TestCase):
    def setUp(self):
        self.c = APIClient()
        self.c.force_authenticate(user=make_user("a", role=Role.ADMIN))
        self.cat = Category.objects.create(name="Comms")

    def test_category_delete_blocked_while_it_has_items(self):
        InventoryItem.objects.create(category=self.cat, name="Radio")
        r = self.c.delete(f"/api/categories/{self.cat.pk}/")
        self.assertEqual(r.status_code, 409)
        self.assertTrue(Category.objects.filter(pk=self.cat.pk).exists())

    def test_empty_category_deletes(self):
        empty = Category.objects.create(name="Empty")
        self.assertEqual(self.c.delete(f"/api/categories/{empty.pk}/").status_code, 204)

    def test_category_item_count_field(self):
        InventoryItem.objects.create(category=self.cat, name="A")
        InventoryItem.objects.create(category=self.cat, name="B")
        row = next(x for x in self.c.get("/api/categories/").json() if x["id"] == self.cat.pk)
        self.assertEqual(row["item_count"], 2)

    def test_item_quantity_writable_on_create_readonly_on_patch(self):
        r = self.c.post("/api/items/", {"category": self.cat.pk, "name": "Batt", "quantity": 5})
        self.assertEqual(r.status_code, 201)
        pk = r.json()["id"]
        self.assertEqual(r.json()["quantity"], 5)
        r2 = self.c.patch(f"/api/items/{pk}/", {"quantity": 99, "remarks": "note"})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["quantity"], 5)
        self.assertEqual(r2.json()["remarks"], "note")
