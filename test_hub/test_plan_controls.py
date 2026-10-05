def apply_test_plan_controls(test_plans, hub):
    """Add editable planned coverage and linked Test Case controls to Test Plans."""
    if getattr(hub.app, "_test_plan_controls_applied", False):
        return

    # Use coverage language in the UI because Test Plans measure whether planned
    # coverage has a linked Test Case, not whether the Test Case was newly created.
    test_plans.TEST_PLANS_PAGE_HTML = (
        test_plans.TEST_PLANS_PAGE_HTML
        .replace("<span>Created</span>", "<span>Covered</span>")
        .replace("<span>Complete</span>", "<span>Coverage</span>")
    )

    test_plans.TEST_PLAN_PAGE_HTML = (
        test_plans.TEST_PLAN_PAGE_HTML
        .replace("<span>Created</span>", "<span>Covered</span>")
        .replace("<span>Complete</span>", "<span>Coverage</span>")
        .replace(
            "{% if is_created %}Created{% else %}Pending{% endif %}</span>",
            "{% if is_created %}Covered{% else %}Pending{% endif %}</span>",
        )
    )

    old_controls = '''              {% if not is_created and coverage_link_cases %}
                <form class="attach-inline" method="post" action="{{ url_for('attach_test_plan_item_case', plan_id=plan.id, item_id=item.id) }}">
                  <select name="case_id" required><option value="">Attach Test Case…</option>{% for case in coverage_link_cases %}<option value="{{ case.id }}">{{ case.case_key }} — {{ case.title }}</option>{% endfor %}</select>
                  <button class="secondary">Attach</button>
                </form>
              {% endif %}
              <form method="post" action="{{ url_for('remove_test_plan_item', plan_id=plan.id, item_id=item.id) }}" onsubmit="return confirm('Remove this checklist item?')"><button class="danger">Remove</button></form>'''

    new_controls = '''              {% if is_created %}
                <form method="post" action="{{ url_for('detach_test_plan_item_case', plan_id=plan.id, item_id=item.id) }}" onsubmit="return confirm('Detach the linked Test Case and return this coverage item to Pending?')">
                  <button class="secondary">Detach</button>
                </form>
              {% endif %}
              <details class="planned-edit">
                <summary class="secondary">Edit</summary>
                <form class="planned-edit-form" method="post" action="{{ url_for('edit_test_plan_item', plan_id=plan.id, item_id=item.id) }}">
                  <label>Feature / Module</label>
                  <input name="feature" required value="{{ item.feature_snapshot }}">
                  <label>Planned coverage</label>
                  <input name="title" required value="{{ item.title_snapshot }}">
                  <label>Notes</label>
                  <textarea name="notes">{{ item.notes }}</textarea>
                  {% if coverage_link_cases %}
                    <div class="planned-case-link">
                      <label>Linked Test Case</label>
                      <input class="planned-case-search" type="search" placeholder="Search Test Case ID or title…" autocomplete="off">
                      <select name="case_id" required>
                        <option value="">{% if is_created %}Change Test Case…{% else %}Attach Test Case…{% endif %}</option>
                        {% for case in coverage_link_cases %}<option value="{{ case.id }}" {% if item.test_case_id == case.id %}selected{% endif %}>{{ case.case_key }} — {{ case.title }}</option>{% endfor %}
                      </select>
                      <button class="secondary planned-case-submit" type="submit" formaction="{{ url_for('attach_test_plan_item_case', plan_id=plan.id, item_id=item.id) }}" formmethod="post">{% if is_created %}Change Test Case{% else %}Attach Test Case{% endif %}</button>
                    </div>
                  {% endif %}
                  <button class="primary" type="submit">Save coverage</button>
                </form>
              </details>
              <form method="post" action="{{ url_for('remove_test_plan_item', plan_id=plan.id, item_id=item.id) }}" onsubmit="return confirm('Remove this checklist item? This deletes the coverage requirement from the plan.')"><button class="danger">Remove</button></form>'''

    if old_controls not in test_plans.TEST_PLAN_PAGE_HTML:
        raise RuntimeError("Test Plan controls template changed; expected checklist controls were not found.")

    test_plans.TEST_PLAN_PAGE_HTML = test_plans.TEST_PLAN_PAGE_HTML.replace(
        old_controls,
        new_controls,
        1,
    )

    # Keep the editing controls compact so the checklist stays readable even when
    # several planned coverage items are being maintained on the same page.
    controls_css = '''
.planned-edit{width:100%;max-width:280px}.planned-edit>summary{list-style:none;text-align:center}.planned-edit>summary::-webkit-details-marker{display:none}.planned-edit-form{margin-top:7px;padding:9px;border:1px solid #dce6f3;border-radius:9px;background:#f9fbfe}.planned-edit-form label{display:block;margin:7px 0 4px;color:#536b87;font-size:9px;font-weight:900}.planned-edit-form input,.planned-edit-form textarea,.planned-edit-form select{width:100%;border:1px solid #ccd9eb;border-radius:7px;background:#fff;color:#183252;font:inherit;font-size:10px}.planned-edit-form input,.planned-edit-form select{height:33px;padding:0 8px}.planned-edit-form textarea{min-height:58px;padding:7px 8px;resize:vertical}.planned-edit-form button{margin-top:8px;width:100%}.planned-case-link{margin-top:12px;padding-top:10px;border-top:1px solid #dce6f3}.planned-case-search{margin-bottom:7px}.planned-case-submit{margin-bottom:2px}
'''
    test_plans.TEST_PLAN_PAGE_HTML = test_plans.TEST_PLAN_PAGE_HTML.replace(
        "</style>",
        controls_css + "</style>",
        1,
    )

    # Filter the Test Case selector inside Edit Coverage without creating another
    # modal. The listener survives when product_redesign moves the form into a modal.
    controls_js = '''
<script>
document.addEventListener('input', function(event){
  if(!event.target.classList.contains('planned-case-search')) return;
  const query=event.target.value.trim().toLowerCase();
  const select=event.target.nextElementSibling;
  if(!select || select.tagName !== 'SELECT') return;
  Array.from(select.options).forEach(function(option){
    if(!option.value) return;
    option.hidden=!!query && !option.textContent.toLowerCase().includes(query);
  });
  if(select.selectedOptions.length && select.selectedOptions[0].hidden) select.value='';
});
</script>
'''
    test_plans.TEST_PLAN_PAGE_HTML = test_plans.TEST_PLAN_PAGE_HTML.replace(
        "</body>",
        controls_js + "</body>",
        1,
    )

    @hub.app.post("/test-plans/<int:plan_id>/items/<int:item_id>/edit")
    def edit_test_plan_item(plan_id, item_id):
        plan = hub.db.session.get(hub.TestPlan, plan_id)
        item = hub.db.session.get(hub.TestPlanItem, item_id)
        if plan is None or item is None or item.test_plan_id != plan.id:
            return "Test Plan item not found.", 404

        feature = hub.request.form.get("feature", "").strip()
        title = hub.request.form.get("title", "").strip()
        notes = hub.request.form.get("notes", "").strip()
        if not feature or not title:
            return "Feature and planned coverage title are required.", 400

        # Edit only the Test Plan requirement. The linked Test Case remains unchanged.
        item.feature_snapshot = feature
        item.title_snapshot = title
        item.notes = notes
        plan.updated_at = hub.datetime.now(hub.timezone.utc) if hasattr(hub, "datetime") else plan.updated_at
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id))

    @hub.app.post("/test-plans/<int:plan_id>/items/<int:item_id>/detach")
    def detach_test_plan_item_case(plan_id, item_id):
        plan = hub.db.session.get(hub.TestPlan, plan_id)
        item = hub.db.session.get(hub.TestPlanItem, item_id)
        if plan is None or item is None or item.test_plan_id != plan.id:
            return "Test Plan item not found.", 404

        # Detach only the Test Case implementation. Keep the planned requirement
        # so it automatically returns to Pending instead of disappearing.
        item.test_case = None
        plan.updated_at = hub.datetime.now(hub.timezone.utc) if hasattr(hub, "datetime") else plan.updated_at
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id))

    hub.app._test_plan_controls_applied = True
