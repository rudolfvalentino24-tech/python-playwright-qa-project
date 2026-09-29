from argparse import ArgumentParser
from pathlib import Path
import re

from app import app, db, TestCase, TestStep


FEATURES_DIR = Path(__file__).resolve().parent.parent / "playwright" / "e2e_bdd" / "features"
STEP_PATTERN = re.compile(r"^(Given|When|Then|And|But)\s+(.+)$")
CASE_ID_PATTERN = re.compile(r"^([A-Z0-9]+(?:-[A-Z0-9]+)+)\s+(.+)$")


def substitute(value, example):
    result = value
    for key, replacement in example.items():
        result = result.replace(f"<{key}>", replacement)
    return result


def slug(value):
    value = re.sub(r"[^A-Z0-9]+", "-", value.upper()).strip("-")
    return value or "CASE"


def split_case_id(title):
    match = CASE_ID_PATTERN.match(title)
    if not match:
        return None, title
    return match.group(1), match.group(2)


def expected_result(steps):
    assertions = []
    assertion_mode = False

    for keyword, text in steps:
        if keyword == "Then":
            assertion_mode = True
            assertions.append(f"Then {text}")
        elif keyword in {"And", "But"} and assertion_mode:
            assertions.append(f"{keyword} {text}")
        elif keyword in {"Given", "When"}:
            assertion_mode = False

    if assertions:
        return "\n".join(assertions)

    if steps:
        keyword, text = steps[-1]
        return f"{keyword} {text}"

    return "BDD scenario completed successfully."


def parse_feature(path):
    feature_name = path.stem.replace("_", " ").title()
    background_steps = []
    scenarios = []
    current = None
    current_background = False
    in_examples = False
    example_headers = None
    pending_tags = []

    def finish_current():
        nonlocal current
        if current is not None:
            scenarios.append(current)
            current = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if line.startswith("Feature:"):
            feature_name = line.split(":", 1)[1].strip()
            continue

        if line.startswith("@"):
            pending_tags.extend(part for part in line.split() if part.startswith("@"))
            continue

        if line.startswith("Background:"):
            finish_current()
            current_background = True
            in_examples = False
            example_headers = None
            continue

        if line.startswith("Scenario Outline:") or line.startswith("Scenario:"):
            finish_current()
            outline = line.startswith("Scenario Outline:")
            current = {
                "name": line.split(":", 1)[1].strip(),
                "outline": outline,
                "steps": [],
                "examples": [],
                "tags": pending_tags,
            }
            pending_tags = []
            current_background = False
            in_examples = False
            example_headers = None
            continue

        if line.startswith("Examples:"):
            in_examples = True
            example_headers = None
            continue

        if in_examples and line.startswith("|") and current is not None:
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if example_headers is None:
                example_headers = cells
            else:
                current["examples"].append(dict(zip(example_headers, cells)))
            continue

        step_match = STEP_PATTERN.match(line)
        if step_match:
            step = (step_match.group(1), step_match.group(2))
            if current_background:
                background_steps.append(step)
            elif current is not None:
                current["steps"].append(step)

    finish_current()

    return {
        "feature": feature_name,
        "background": background_steps,
        "scenarios": scenarios,
    }


def build_case(feature_name, background, scenario, example=None, example_index=None):
    example = example or {}
    rendered_name = substitute(scenario["name"], example)
    rendered_steps = [
        (keyword, substitute(text, example))
        for keyword, text in scenario["steps"]
    ]

    explicit_case_id = example.get("case_id", "").strip().upper()
    base_case_id, title = split_case_id(rendered_name)

    if explicit_case_id:
        case_key = explicit_case_id
        _, title = split_case_id(rendered_name)
    elif scenario["outline"]:
        base_case_id = base_case_id or slug(feature_name)
        suffix_values = [
            value
            for key, value in example.items()
            if key != "case_id" and value.strip()
        ]
        suffix = "-".join(slug(value) for value in suffix_values)
        case_key = f"{base_case_id}-{suffix}" if suffix else f"{base_case_id}-{example_index:02d}"

        original_title = scenario["name"]
        if "<" not in original_title and suffix_values:
            title = f"{title} — {' / '.join(suffix_values)}"
    else:
        case_key = base_case_id or f"BDD-{slug(feature_name)}-{slug(rendered_name)[:30]}"

    preconditions = "\n".join(
        f"{keyword} {text}"
        for keyword, text in background
    )

    return {
        "case_key": case_key[:64],
        "title": title[:250],
        "feature": feature_name,
        "priority": "Medium",
        "type": "Automated",
        "status": "Ready",
        "suite_tags": ",".join(sorted({
            "regression",
            "release",
            *[
                tag.removeprefix("@").lower()
                for tag in scenario.get("tags", [])
            ],
        })),
        "preconditions": preconditions,
        "steps": [f"{keyword} {text}" for keyword, text in rendered_steps],
        "expected_result": expected_result(rendered_steps),
    }


def collect_bdd_cases():
    cases = []
    seen_keys = set()

    for path in sorted(FEATURES_DIR.glob("*.feature")):
        parsed = parse_feature(path)

        for scenario in parsed["scenarios"]:
            if scenario["outline"]:
                if not scenario["examples"]:
                    raise RuntimeError(f"{path.name}: Scenario Outline has no Examples: {scenario['name']}")

                for index, example in enumerate(scenario["examples"], start=1):
                    case = build_case(
                        parsed["feature"],
                        parsed["background"],
                        scenario,
                        example=example,
                        example_index=index,
                    )
                    if case["case_key"] in seen_keys:
                        raise RuntimeError(f"Duplicate generated test case ID: {case['case_key']}")
                    seen_keys.add(case["case_key"])
                    cases.append(case)
            else:
                case = build_case(
                    parsed["feature"],
                    parsed["background"],
                    scenario,
                )
                if case["case_key"] in seen_keys:
                    raise RuntimeError(f"Duplicate generated test case ID: {case['case_key']}")
                seen_keys.add(case["case_key"])
                cases.append(case)

    return cases


def apply_case(existing, source):
    existing.title = source["title"]
    existing.feature = source["feature"]
    existing.priority = source["priority"]
    existing.type = source["type"]
    existing.status = source["status"]
    existing.suite_tags = source["suite_tags"]
    existing.preconditions = source["preconditions"]
    existing.expected_result = source["expected_result"]
    existing.steps = [
        TestStep(position=index, action=action)
        for index, action in enumerate(source["steps"], start=1)
    ]


def import_bdd_cases(update_existing=False, dry_run=False):
    cases = collect_bdd_cases()
    imported = 0
    updated = 0
    skipped = 0

    print(f"BDD source: {FEATURES_DIR}")
    print(f"Discovered: {len(cases)} test cases")

    for source in cases:
        existing = db.session.scalar(
            db.select(TestCase).where(TestCase.case_key == source["case_key"])
        )

        if existing is not None:
            if update_existing:
                print(f"UPDATE  {source['case_key']}  {source['title']}")
                if not dry_run:
                    apply_case(existing, source)
                updated += 1
            else:
                print(f"SKIP    {source['case_key']}  already exists")
                skipped += 1
            continue

        print(f"IMPORT  {source['case_key']}  {source['title']}")
        if not dry_run:
            case = TestCase(
                case_key=source["case_key"],
                title=source["title"],
                feature=source["feature"],
                priority=source["priority"],
                type=source["type"],
                status=source["status"],
                suite_tags=source["suite_tags"],
                preconditions=source["preconditions"],
                expected_result=source["expected_result"],
            )
            case.steps = [
                TestStep(position=index, action=action)
                for index, action in enumerate(source["steps"], start=1)
            ]
            db.session.add(case)
        imported += 1

    if not dry_run:
        db.session.commit()

    print()
    print(f"Imported: {imported}")
    print(f"Updated:  {updated}")
    print(f"Skipped:  {skipped}")
    print(f"Total:    {len(cases)}")


def main():
    parser = ArgumentParser(description="Import pytest-bdd feature scenarios into Test Hub.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the import without changing the database.",
    )
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Refresh existing matching case IDs from the BDD source files.",
    )
    args = parser.parse_args()

    if not FEATURES_DIR.exists():
        raise SystemExit(f"BDD features folder not found: {FEATURES_DIR}")

    with app.app_context():
        import_bdd_cases(
            update_existing=args.update_existing,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
