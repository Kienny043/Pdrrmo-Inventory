"""Tests for the reference-data constants and their two read-only endpoints."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from . import reference


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
