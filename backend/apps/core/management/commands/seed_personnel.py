"""Seed demo Personnel / TrainingRecord data + an admin/admin login.

Dev/test aid only — never run in production. Idempotent: personnel are keyed
on (name, municipality); re-running skips rows that already exist. Pass
``--flush`` to delete all Personnel first.

    python manage.py seed_personnel [--flush]
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.choices import OrgAffiliation, Role
from apps.core.models import Personnel, TrainingRecord, profile_for

EMP, VOL = OrgAffiliation.EMPLOYEE, OrgAffiliation.VOLUNTEER

# name, designation, municipality, employment_status, org_affiliation,
# archived, other_drr_training, {training_key: year}
SEED = [
    # --- First District: Tayabas City ---
    ("Maria Santos", "MDRRMO Officer", "Tayabas City", "Permanent", EMP, False, "",
        {"ICS_L1": 2018, "ICS_L2": 2019, "RDANA": 2020, "BLS": 2021, "SFA": 2021, "WASAR": 2022}),
    ("Juan dela Cruz", "Rescue Team Leader", "Tayabas City", "Casual", EMP, False, "Fire safety inspection",
        {"ICS_L1": 2017, "BLS": 2016, "SWAR": 2019, "BRRT": 2020, "CSSR": 2021}),
    ("Angelo Ramos", "Operations Staff", "Tayabas City", "Job Order", EMP, False, "",
        {"ICS_L1": 2019, "EOC": 2021, "BLS": 2020}),
    ("Liza Mercado", "Community Volunteer", "Tayabas City", "", VOL, False, "",
        {"BLS": 2022, "SFA": 2022}),
    # --- First District: Lucban ---
    ("Rogelio Bautista", "MDRRMO Head", "Lucban", "Permanent", EMP, False, "",
        {"ICS_L1": 2016, "ICS_L2": 2017, "ICS_L3": 2019, "EOC": 2020, "EOC_EXEC": 2022, "LDRRMP": 2021}),
    ("Cristina Flores", "Admin Assistant", "Lucban", "Contractual", EMP, False, "",
        {"ICS_L1": 2020, "CBDRRM": 2021}),
    ("Mark Villanueva", "SAR Volunteer", "Lucban", "", VOL, False, "Chainsaw operation",
        {"BLS": 2018, "SWAR": 2019, "WASAR": 2019, "BRRT": 2021, "MOSART": 2022}),
    # --- Second District: Lucena City ---
    ("Grace Aquino", "CDRRMO Officer III", "Lucena City", "Permanent", EMP, False, "",
        {"ICS_L1": 2015, "ICS_L2": 2016, "ICS_L3": 2018, "ICS_L4": 2021, "RDANA": 2019, "CP": 2020, "PSCP": 2022}),
    ("Dennis Cruz", "EOC Duty Officer", "Lucena City", "Permanent", EMP, False, "",
        {"EOC": 2018, "EOC_EXEC": 2020, "ICS_L1": 2017}),
    ("Patricia Lim", "Health Response Staff", "Lucena City", "Job Order", EMP, False, "",
        {"BLS": 2021, "SFA": 2021, "BLS_TOF": 2023}),
    ("Ramon Estrada", "Retired Coordinator", "Lucena City", "Permanent", EMP, True, "",
        {"ICS_L1": 2012, "RDANA": 2014}),
    # --- Second District: Sariaya ---
    ("Elena Torres", "MDRRMO Officer", "Sariaya", "Permanent", EMP, False, "",
        {"ICS_L1": 2019, "CBDRRM": 2020, "CBDRRM_TOT": 2022, "ECCDIE": 2023}),
    ("Noel Padilla", "Rescue Volunteer", "Sariaya", "", VOL, False, "",
        {"BLS": 2020, "CVERT": 2021, "CSSR": 2022}),
    ("Cynthia Rosales", "Planning Staff", "Sariaya", "Contractual", EMP, True, "Left the office in 2023",
        {"ICS_L1": 2018, "CP": 2019}),
    # --- Third District: Catanauan ---
    ("Ferdinand Aguilar", "MDRRMO Head", "Catanauan", "Permanent", EMP, False, "",
        {"ICS_L1": 2017, "ICS_L2": 2018, "ICS_TFI": 2021, "ICS_EXEC": 2023, "LDRRMP": 2020}),
    ("Josie Navarro", "Admin Officer", "Catanauan", "Casual", EMP, False, "",
        {"ICS_L1": 2020, "EOC": 2022}),
    ("Allan Rivera", "Coastal SAR Volunteer", "Catanauan", "", VOL, False, "Boat handling",
        {"BLS": 2019, "WASAR": 2020, "SWAR": 2021, "MOSAR_TOT": 2023}),
    # --- Third District: Mulanay ---
    ("Teresita Gomez", "MDRRMO Officer", "Mulanay", "Permanent", EMP, False, "",
        {"ICS_L1": 2018, "RDANA": 2019, "HAZMAT_AWARENESS": 2021, "HAZMAT_OPERATIONS": 2022}),
    ("Benjie Salazar", "Operations Staff", "Mulanay", "Job Order", EMP, False, "",
        {"ICS_L1": 2021, "BLS": 2020}),
    ("Marilou Castro", "Barangay Volunteer", "Mulanay", "", VOL, False, "",
        {"BLS": 2022, "SFA": 2022, "CBDRRM": 2023}),
]


class Command(BaseCommand):
    help = "Seed demo Personnel / TrainingRecord data and an admin/admin user."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush", action="store_true",
            help="Delete all existing Personnel before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        User = get_user_model()
        admin, created = User.objects.get_or_create(username="admin")
        if created:
            admin.set_password("admin")
        # Superuser so /admin/ is actually usable by the dev login (and so the
        # API's "superusers satisfy every check" path is exercised too).
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()
        prof = profile_for(admin)
        prof.role = Role.ADMIN
        prof.can_permanently_delete = True
        prof.save()
        self.stdout.write(
            "admin user %s (login admin/admin), superuser, role=ADMIN, can_permanently_delete=True"
            % ("created" if created else "exists")
        )

        if opts["flush"]:
            n = Personnel.objects.count()
            Personnel.objects.all().delete()
            self.stdout.write("flushed %d existing personnel" % n)

        made = skipped = cells = 0
        for name, desig, muni, emp, aff, archived, other, records in SEED:
            person, was_created = Personnel.objects.get_or_create(
                name=name,
                municipality=muni,
                defaults=dict(
                    designation=desig,
                    employment_status=emp,
                    org_affiliation=aff,
                    other_drr_training=other,
                    is_archived=archived,
                    archived_at=timezone.now() if archived else None,
                    archived_by=admin if archived else None,
                ),
            )
            if not was_created:
                skipped += 1
                continue
            made += 1
            for key, year in records.items():
                _, c = TrainingRecord.objects.update_or_create(
                    personnel=person, training_key=key,
                    defaults={"year_attained": year},
                )
                cells += 1

        self.stdout.write(self.style.SUCCESS(
            "seeded %d personnel (%d skipped), %d training cells"
            % (made, skipped, cells)
        ))
        self.stdout.write(
            "archived rows: %d"
            % Personnel.objects.filter(is_archived=True).count()
        )
