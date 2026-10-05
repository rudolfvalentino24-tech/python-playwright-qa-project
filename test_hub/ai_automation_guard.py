import ast
import re


_UNSUPPORTED_WARNING = re.compile(
    r"(?:"
    r"not\s+(?:implemented|supported|available|present)|"
    r"does\s+not\s+(?:render|exist|provide|contain|expose|include)|"
    r"defines?\s+no\b|"
    r"cannot\s+be\s+(?:implemented|tested|asserted)|"
    r"intentionally\s+omitted|"
    r"invent(?:ing)?\s+unsupported|"
    r"unsupported\s+(?:product\s+)?(?:behavior|behaviour|selector|control|feature)|"
    r"no\s+(?:matching\s+)?(?:control|button|icon|field|element|endpoint|route|selector)\b"
    r")",
    re.IGNORECASE,
)

_STEP_PATTERN = re.compile(r"^(Given|When|Then|And|But)\s+(.+)$", re.IGNORECASE)

# Deterministic product-capability checks for behaviors where a negative test
# could otherwise pass simply because the whole feature is absent.
_CAPABILITY_CHECKS = (
    {
        "scenario": re.compile(
            r"(?:reveal|show|toggle)\s+(?:the\s+)?password|password\s+(?:reveal|visibility)\s+(?:icon|button|control|toggle)?",
            re.IGNORECASE,
        ),
        "source": re.compile(
            r"reveal[-_ ]?password|show[-_ ]?password|toggle[-_ ]?password|password[-_ ]?visibility|"
            r"password[-_ ]?(?:eye|toggle)|(?:eye|visibility)[-_ ]?icon",
            re.IGNORECASE,
        ),
        "label": "password reveal control",
    },
)


def _step_body(step):
    match = _STEP_PATTERN.match(str(step or "").strip())
    return " ".join((match.group(2) if match else str(step or "")).strip().lower().split())


def _decorated_step_texts(test_code):
    code = (test_code or "").strip()
    if not code:
        return set()

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()

    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not decorator.args:
                continue
            func_name = decorator.func.id if isinstance(decorator.func, ast.Name) else ""
            if func_name not in {"given", "when", "then"}:
                continue

            arg = decorator.args[0]
            value = arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else None
            if value is None and isinstance(arg, ast.Call) and arg.args:
                first = arg.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    value = first.value
            if value:
                found.add(" ".join(value.strip().lower().split()))
    return found


def _warns_about_unsupported_behavior(proposal):
    text = "\n".join(
        [str(getattr(proposal, "summary", "") or "")]
        + [str(warning or "") for warning in getattr(proposal, "warnings", [])]
    )
    return bool(_UNSUPPORTED_WARNING.search(text))


def _proposal_covers_all_missing_steps(proposal, automation):
    missing = {
        _step_body(row.get("step", ""))
        for row in automation.get("steps", [])
        if not row.get("implemented")
    }
    if not missing:
        return True

    generated = _decorated_step_texts(getattr(proposal, "test_code", ""))
    return missing.issubset(generated)


def _application_source(bdd_sync):
    paths = (
        bdd_sync.PROJECT_ROOT / "qa_testing_playground" / "store.py",
        bdd_sync.PROJECT_ROOT / "qa_testing_playground" / "qa_playground.py",
    )
    chunks = []
    for path in paths:
        if not path.exists():
            continue
        try:
            chunks.append(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
    return "\n".join(chunks)


def _missing_product_capability(bdd_sync, case, automation):
    scenario_text = "\n".join(
        [str(getattr(case, "title", "") or "")]
        + [str(row.get("step", "") or "") for row in automation.get("steps", [])]
    )
    source = _application_source(bdd_sync)

    for check in _CAPABILITY_CHECKS:
        if check["scenario"].search(scenario_text) and not check["source"].search(source):
            return check["label"]
    return ""


def _block_proposal(proposal, reason):
    proposal.test_code = ""
    proposal.page_object_file = ""
    proposal.page_object_class = ""
    proposal.page_object_methods = ""
    proposal.summary = reason
    return proposal


def apply_ai_automation_guard(ai_automation):
    """Prevent false-green or partial automation proposals."""
    original_generate = ai_automation._generate_proposal

    def guarded_generate(bdd_sync, case, automation):
        proposal = original_generate(bdd_sync, case, automation)

        missing_capability = _missing_product_capability(
            bdd_sync,
            case,
            automation,
        )
        test_first_mode = bool(missing_capability)

        if test_first_mode:
            # Keep valid test-first automation even when development is not complete yet.
            proposal.warnings = list(
                getattr(proposal, "warnings", []) or []
            ) + [
                (
                    f"Test-first automation: application source does not yet contain "
                    f"the required {missing_capability}. The generated test is expected "
                    "to fail until the product feature is implemented."
                )
            ]

            if not (getattr(proposal, "test_code", "") or "").strip():
                return _block_proposal(
                    proposal,
                    "AI did not generate test-first automation for the missing product capability.",
                )

        elif _warns_about_unsupported_behavior(proposal):
            return _block_proposal(
                proposal,
                "Automation was not generated because the application source does not "
                "support all behavior required by this scenario.",
            )

        if not _proposal_covers_all_missing_steps(proposal, automation):
            return _block_proposal(
                proposal,
                "Automation was not generated because the AI proposal did not implement "
                "every missing BDD step. Partial automation is blocked to prevent a "
                "false-green test case.",
            )

        return proposal

    ai_automation._generate_proposal = guarded_generate
