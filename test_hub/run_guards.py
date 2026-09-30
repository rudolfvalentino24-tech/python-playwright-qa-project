from datetime import datetime, timezone


def register_run_guards(hub):
    def create_test_run_guarded():
        name = hub.request.form.get("name", "").strip()
        preset = hub.request.form.get("preset", "Custom").strip()
        release_id_value = hub.request.form.get("release_id", "").strip()
        environment = hub.request.form.get("environment", "").strip()
        execution_type = hub.request.form.get("execution_type", "Manual").strip()
        case_id_values = hub.request.form.getlist("case_ids")

        if not name:
            return "Test run name is required.", 400
        if preset not in hub.RUN_PRESETS:
            return "Invalid test run preset.", 400
        if execution_type not in hub.TYPES:
            return "Invalid execution type.", 400

        release = None
        if release_id_value:
            try:
                release = hub.db.session.get(hub.Release, int(release_id_value))
            except ValueError:
                return "Invalid release.", 400
            if release is None:
                return "Release not found.", 404

        if preset == "Custom":
            if not case_id_values:
                return "Select at least one test case.", 400

            case_ids = []
            for raw_id in case_id_values:
                try:
                    case_ids.append(int(raw_id))
                except ValueError:
                    return "Invalid test case selection.", 400

            cases = hub.db.session.scalars(
                hub.db.select(hub.TestCase)
                .where(hub.TestCase.id.in_(case_ids))
                .order_by(hub.TestCase.feature, hub.TestCase.case_key)
            ).all()
            if len(cases) != len(set(case_ids)):
                return "One or more selected test cases no longer exist.", 400
        else:
            preset_tag = {
                "Smoke": "smoke",
                "Regression": "regression",
                "Full Release": "release",
            }[preset]
            all_cases = hub.db.session.scalars(
                hub.db.select(hub.TestCase).order_by(hub.TestCase.feature, hub.TestCase.case_key)
            ).all()
            cases = [
                case for case in all_cases
                if case.type == "Automated"
                and case.status == "Ready"
                and preset_tag in case.suite_tag_list
            ]
            execution_type = "Automated"
            if not cases:
                return (
                    f"No Ready Automated test cases are tagged for the {preset} preset. "
                    "Complete the automation and mark cases Ready first."
                ), 400

        run = hub.TestRun(
            release=release,
            name=name,
            preset=preset,
            execution_type=execution_type,
            environment=environment or (release.environment if release else ""),
            started_at=datetime.now(timezone.utc),
        )
        run.items = [
            hub.TestRunItem(
                test_case=case,
                position=index,
                case_key_snapshot=case.case_key,
                case_title_snapshot=case.title,
                feature_snapshot=case.feature_name,
            )
            for index, case in enumerate(cases, start=1)
        ]
        hub.db.session.add(run)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_run_details", run_id=run.id))

    hub.app.view_functions["create_test_run"] = create_test_run_guarded
