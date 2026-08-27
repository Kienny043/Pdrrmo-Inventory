"""Tests for the reference-data constants, their two read-only endpoints,
and the Step 3 Personnel / TrainingRecord models."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from . import reference
from .choices import TRAINING_YEAR_MAX, TRAINING_YEAR_MIN, OrgAffiliation
from .models import Personnel, TrainingRecord


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
