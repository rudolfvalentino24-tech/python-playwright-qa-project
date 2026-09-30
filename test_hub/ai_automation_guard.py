import re


_UNSUPPORTED_WARNING = re.compile(
    r"(?:not\s+(?:implemented|supported|available)|"
    r"does\s+not\s+(?:render|exist|provide|contain|expose|include)|"
    r"no\s+(?:matching\s+)?(?:control|button|icon|field|element|endpoint|route)\b)",
    re.IGNORECASE,
)


def _warns_about_unsupported_behavior(proposal):
    return any(
        _UNSUPPORTED_WARNING.search(str(warning or ""))
        for warning in getattr(proposal, "warnings", [])
    )


def apply_ai_automation_guard(ai_automation):
    """Prevent false-green automation when the product behavior does not exist."""
    original_generate = ai_automation._generate_proposal

    def guarded_generate(bdd_sync, case, automation):
        proposal = original_generate(bdd_sync, case, automation)
        if not _warns_about_unsupported_behavior(proposal):
            return proposal

        proposal.test_code = ""
        proposal.page_object_file = ""
        proposal.page_object_class = ""
        proposal.page_object_methods = ""
        proposal.summary = (
            "Automation was not generated because the application source does not "
            "support the requested behavior yet. Implement the product feature first, "
            "then generate the automation again."
        )
        return proposal

    ai_automation._generate_proposal = guarded_generate
