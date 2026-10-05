from datetime import datetime, timezone

from sqlalchemy import text


MIGRATION_KEY = "scrum5-password-visibility-case-steps-v1"

CASE_STEPS = {
    "AUTH-PASSWORD-VIS-01": [
        "Given the user is on the login page",
        'When the user enters "Test123!" in the password field',
        "Then the password should be masked",
        "When the user clicks the password visibility toggle",
        "Then the password should be visible",
        'And the password value should remain "Test123!"',
        "When the user clicks the password visibility toggle",
        "Then the password should be masked",
        'And the password value should remain "Test123!"',
    ],
    "AUTH-PASSWORD-VIS-02": [
        "Given the user is on the login page",
        "And the user enters valid login credentials",
        "When the user clicks the password visibility toggle",
        "Then the login form should not be submitted",
        "And the login page should be displayed",
        "When the user submits the login form",
        "Then the Store page should be displayed",
    ],
    "AUTH-PASSWORD-VIS-03": [
        "Given the user is on the login page",
        'And the user enters "Test123!" in the password field',
        "When the user navigates to the password visibility toggle using the keyboard",
        "Then the password visibility toggle should be focused",
        "When the user activates the password visibility toggle using the keyboard",
        "Then the password should be visible",
        "And the password visibility toggle should be focused",
    ],
    "AUTH-PASSWORD-VIS-04": [
        "Given the user is on the login page",
        'And the user enters "Test123!" in the password field',
        'Then the password visibility toggle accessible label should be "Show password"',
        "When the user clicks the password visibility toggle",
        'Then the password visibility toggle accessible label should be "Hide password"',
        "When the user clicks the password visibility toggle",
        'Then the password visibility toggle accessible label should be "Show password"',
    ],
    "AUTH-PASSWORD-VIS-05": [
        "Given the user is on the login page",
        'And the user enters "Test123!" in the password field',
        "And the user clicks the password visibility toggle",
        "Then the password should be visible",
        "When the user reloads the login page",
        "Then the password should be masked",
        'When the user enters "Test123!" in the password field',
        "And the user clicks the password visibility toggle",
        "And the user leaves and returns to the login page",
        "Then the password should be masked",
    ],
}


def apply_password_visibility_case_step_migration(hub):
    """Apply the corrected SCRUM-5 case steps exactly once to Test Hub data."""
    with hub.app.app_context():
        # Keep a tiny migration ledger so future Test Hub restarts do not overwrite
        # manual edits after this one-time SCRUM-5 cleanup has been applied.
        hub.db.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_hub_data_migrations (
                    migration_key VARCHAR(120) PRIMARY KEY,
                    applied_at TIMESTAMP NOT NULL
                )
                """
            )
        )
        hub.db.session.commit()

        already_applied = hub.db.session.execute(
            text(
                "SELECT migration_key FROM test_hub_data_migrations "
                "WHERE migration_key = :migration_key"
            ),
            {"migration_key": MIGRATION_KEY},
        ).first()
        if already_applied:
            return

        cases = hub.db.session.scalars(
            hub.db.select(hub.TestCase).where(
                hub.TestCase.case_key.in_(tuple(CASE_STEPS.keys()))
            )
        ).all()
        cases_by_key = {case.case_key: case for case in cases}

        # Do not partially update the story if any of its five Test Hub cases are
        # missing. The migration will try again on the next startup instead.
        missing = sorted(set(CASE_STEPS) - set(cases_by_key))
        if missing:
            print(
                "[Test Hub] SCRUM-5 step migration skipped; missing cases: "
                + ", ".join(missing)
            )
            return

        for case_key, desired_steps in CASE_STEPS.items():
            case = cases_by_key[case_key]

            # Replace only the ordered Steps collection. Jira links, Test Plans,
            # title, feature/module, tags, status and expected result are untouched.
            case.steps.clear()
            for position, action in enumerate(desired_steps, start=1):
                case.steps.append(
                    hub.TestStep(position=position, action=action)
                )
            case.updated_at = datetime.now(timezone.utc)

        hub.db.session.execute(
            text(
                "INSERT INTO test_hub_data_migrations (migration_key, applied_at) "
                "VALUES (:migration_key, :applied_at)"
            ),
            {
                "migration_key": MIGRATION_KEY,
                "applied_at": datetime.now(timezone.utc),
            },
        )
        hub.db.session.commit()
        print("[Test Hub] Corrected SCRUM-5 password visibility case steps.")
