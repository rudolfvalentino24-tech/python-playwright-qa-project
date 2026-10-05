# Test Hub Guide

[Project README](../README.md) | [QA Workflow Guide](QA_WORKFLOW.md)

Test Hub is the QA management application in this repository. It brings Test Plans, Test Cases, Test Runs, execution results, defects, retesting, risk, release readiness, exploratory testing, and QA intelligence into one place.

This guide explains how to use the **Test Hub application itself**. For the wider process across Jira, GitHub, Jenkins, Python, pytest-bdd, and Playwright, see the [QA Workflow Guide](QA_WORKFLOW.md).

---

## 1. Start Test Hub

From the repository root:

```powershell
python test_hub\run_ai.py
```

Then open:

```text
http://127.0.0.1:3000
```

The first page is the **QA Workplace** dashboard.

---

## 2. Main areas

The main Test Hub areas are:

- **Dashboard / QA Workplace** — daily priorities, sprint-level QA progress, and Test Plan stage tracking.
- **Test Cases** — reusable manual or automated test cases.
- **Test Plans** — planned QA scope, coverage, strategy, Jira references, releases, and execution links.
- **Test Runs** — a concrete execution of selected Test Cases.
- **Releases** — delivery targets that can be linked to Test Plans and Test Runs.
- **Results** — execution outcomes and failure evidence.
- **QA intelligence** — risk, smart scope, exploratory sessions, automation health, and failure analysis.

---

## 3. QA Workplace / Dashboard

The root route `/` opens the QA Workplace. `/qa-workspace` remains available as a compatibility route.

The Dashboard is designed around the question: **What should QA work on next?**

### Today

The Today section prioritizes work in this order:

1. Blockers
2. Retests
3. Failed automation
4. Active Test Run execution
5. Missing Test Plan coverage
6. Ready Test Cases that have never been executed
7. QA sign-off

The **Recommended next action** card highlights the highest-priority item.

### Current QA Sprint

The current QA sprint summary is currently derived from Test Plans whose status is `Active`.

> Important: this is not yet a live Jira Sprint synchronization. It is an internal Test Hub view of active QA work.

It aggregates:

- Active Test Plans
- Planned scenarios
- Covered Test Cases
- Executed Test Cases
- Passed
- Failed
- Blocked
- Coverage percentage
- Execution percentage

### Test Plan progress

Each active plan can move through these stages:

```text
Scope & Strategy
      ↓
Coverage
      ↓
Test Cases Ready
      ↓
Execution
      ↓
Defects & Retest
      ↓
QA Sign-off
      ↓
Complete
```

If a plan has failed or blocked results, it moves to **Defects & Retest** even if other Test Cases are still not run.

---

## 4. Test Cases

A Test Case represents reusable QA coverage for one behavior or scenario.

Typical Test Cases include:

- positive functional scenarios
- negative scenarios
- boundary-value checks
- regression coverage
- accessibility checks
- security-related checks
- manual checks
- automated BDD coverage

A Test Case can be linked to one or more Test Plans.

When a Test Case is removed from a Test Plan, the planned coverage item can remain as **Pending**. This is intentional: deleting or detaching a Test Case should not erase the fact that the coverage was planned.

### Suite tags

Test Cases can use suite tags such as:

- Smoke
- Regression
- Release

These tags help with scope selection and release-readiness analysis.

---

## 5. Test Plans

A Test Plan answers:

> What does QA intend to validate, why, and against which requirements and release?

Test Plan statuses are:

- `Draft`
- `Active`
- `Completed`

A plan can include a structured strategy with:

- Plan Type
- Application / Product
- Feature / Module
- Objective
- In Scope
- Out of Scope
- Risks / Edge Cases
- Entry Criteria
- Exit Criteria
- Environment
- Jira scope
- Target Release

Common plan types include:

- Feature
- Regression
- Release
- Smoke
- Exploratory
- End-to-End
- Integration

### When to create a Test Plan

A Test Plan should normally be created when the requirement is sufficiently clear to plan QA coverage, not after development is finished.

For the wider timing and shift-left process, see [QA Workflow — Test Planning](QA_WORKFLOW.md#8-test-planning-and-shift-left-qa).

---

## 6. Planned Coverage

Planned Coverage is the list of scenarios QA intends to cover.

A coverage item can be:

- **Covered** — linked to an existing Test Case.
- **Pending** — planned, but no Test Case exists yet.

This separation is important because QA often knows **what must be tested** before every detailed Test Case has been written.

Example:

```text
Registration Test Plan

Covered
✓ Registration page link
✓ Password visibility

Pending
○ Duplicate username validation
○ Email validation
○ Password boundary tests
```

The coverage checklist therefore shows the difference between:

- planned scope
- actual Test Cases already created

---

## 7. Test Plan strategy

The strategy section gives context to the plan.

### Objective

Why the testing effort exists.

### In Scope

What this plan is responsible for validating.

### Out of Scope

What the team deliberately excludes from this plan.

### Risks

Known quality risks or important edge cases.

### Entry Criteria

Conditions that should be true before meaningful execution begins, for example:

- feature deployed to QA
- acceptance criteria approved
- required test data available

### Exit Criteria

Conditions required before QA considers the plan complete, for example:

- Critical and High-priority tests passed
- no open Critical or High defects
- required regression completed

---

## 8. Jira links inside Test Hub

A Test Plan can store Jira issue keys as requirement scope.

Examples:

```text
SCRUM-8
SCRUM-10
SCRUM-11
SCRUM-12
SCRUM-13
SCRUM-14
```

Test Cases, Test Plan items, Runs, Releases, and Results can participate in traceability around those Jira references.

> Current behavior: Test Hub stores and uses Jira references for scope and traceability. A full live Jira Sprint/requirement synchronization is a future enhancement rather than something to assume from the current Dashboard.

The Traceability section helps answer:

- Which Jira requirement is covered?
- Which Test Case covers it?
- Which Run executed that Test Case?
- What was the latest Result?
- Is there a linked defect?

For the team process around Jira refinement and Definition of Ready, see [QA Workflow — Jira Story standard](QA_WORKFLOW.md#4-jira-story-standard).

---

## 9. Releases inside Test Hub

A Release is the delivery target, for example:

```text
v1.2 - Registration
```

A Test Plan can be linked to a Release, and a Test Run can also be associated with a Release.

The Release exists near the beginning of planning as a target, while the final release decision happens after execution and QA sign-off.

A simplified relationship is:

```text
Release
  ├── Test Plans
  │     ├── Planned Coverage
  │     └── Test Cases
  └── Test Runs
        └── Results
```

For the wider distinction between Sprint and Release, see [QA Workflow — Sprint vs Release](QA_WORKFLOW.md#7-sprint-vs-release).

---

## 10. Creating Test Runs

A Test Run is a concrete execution event.

From a Test Plan, Test Hub can create a Run from the Test Cases already covered by that plan.

A Run can record:

- name
- execution type
- environment
- release
- selected Test Cases
- linked Test Plan

Execution types can include:

- Manual
- Automated

The relationship is:

```text
Test Plan
   ↓
Covered Test Cases
   ↓
Test Run
   ↓
Results
```

---

## 11. Manual and automated execution

### Manual

Manual runs are executed by the tester and results are recorded in Test Hub.

### Automated

Automated runs use the existing Jenkins / pytest-bdd / Playwright path.

At application level, the flow is:

```text
Test Hub selection
      ↓
Jenkins
      ↓
pytest-bdd / Playwright
      ↓
Results returned to Test Hub
```

For the technical details, see [QA Workflow — Jenkins and automated execution](QA_WORKFLOW.md#12-jenkins-and-automated-execution).

---

## 12. Results

Test Hub supports these execution statuses:

- Passed
- Failed
- Blocked
- Skipped

`Not Run` is derived when a Test Case has not yet produced an execution result in the relevant scope.

### Failed results

Failure evidence can include:

- screenshot
- Jenkins build reference
- traceback / error details
- Playwright test output

Automated execution can save failure screenshots under the test-results output used by Jenkins.

### Blocked results

Blocked tests should record why execution could not continue. Available reasons include:

- Environment unavailable
- Test data unavailable
- Dependency incomplete
- Defect prevents testing
- Requirement unclear
- Access / permission
- Other

Blocked is not the same as Failed. A Blocked result means the test could not be meaningfully completed.

---

## 13. Defects and retesting

A failed Test Result can enter the retest workflow.

Typical flow:

```text
Failed Result
     ↓
Defect linked
     ↓
Ready for Retest
     ↓
Dedicated Retest Run
     ↓
Verified / Retest Failed / Retest Blocked
```

Test Hub reuses the existing defect-link model rather than creating a separate competing defect store.

When a dedicated retest Run is created, Test Hub keeps the original Test Case and preserves relevant execution context such as environment, release, and linked Test Plan where possible.

For the wider Jira defect lifecycle, see [QA Workflow — Defect and retest workflow](QA_WORKFLOW.md#14-defect-and-retest-workflow).

---

## 14. Release Readiness

Release Readiness combines execution data and a human QA decision.

Test Hub can evaluate criteria such as:

- Execution complete
- No Critical failures
- No blocked tests
- High-risk coverage tested
- Smoke passed

The human decision can be:

- Not Assessed
- Ready
- Ready with known risks
- Not Ready

The tool should support the QA decision, not replace it.

A release may therefore have good execution statistics but still be marked **Not Ready** if known risks are unacceptable.

---

## 15. Risk assessment

Test Hub can maintain a risk profile per Test Case using four dimensions:

- Business Impact
- Change Complexity
- Regression Risk
- User Frequency

The combined score maps to:

- Low
- Medium
- High
- Critical

Risk helps QA decide:

- what to execute first
- what must be included in regression
- what deserves stronger evidence
- what can block release readiness

---

## 16. Smart Scope / AI impact analysis

Smart Scope helps select affected tests for a change.

Inputs can include:

- change description
- acceptance criteria
- Jira references
- Release context

Suggestions can be classified as:

- Required
- Regression
- Consider

The tester reviews the suggestions before creating the actual Test Run.

AI is used as decision support; it should not silently define product requirements.

---

## 17. Exploratory Sessions

Test Hub supports exploratory testing sessions with fields such as:

- title
- charter
- status
- duration
- environment
- Jira scope
- coverage notes
- session notes

Statuses are:

- Planned
- In Progress
- Completed

Exploratory testing complements scripted Test Cases. It is especially useful for unclear risks, new workflows, usability, and areas where predefined checks are not enough.

---

## 18. Automation Health

Automation Health analyzes recent automated results and can identify signals such as:

- Stable
- Potentially Flaky
- Consistently Failing
- Never Executed

`Potentially Flaky` is a signal, not proof. A tester should investigate the pattern before deciding that a test is truly flaky.

---

## 19. Failure clustering

Failure analysis can group similar errors into clusters such as:

- timeout
- locator
- assertion
- network / service
- authentication

This helps distinguish a broad product failure from many tests failing for the same technical reason.

---

## 20. End-to-End Test Plan workspace

End-to-End plans can capture additional structured information such as:

- journey
- coverage design
- roles
- test data
- automation approach
- implementation phases
- Definition of Done

A PDF Test Plan can be imported to populate structured strategy information and E2E metadata.

Refreshing from the source document is designed to preserve existing execution-related data such as:

- coverage rows
- Test Cases
- Jira / Release links
- Runs
- roles
- Definition of Done items

---

## 21. Test Plan reports and PDF export

Test Plans can produce a final report and can be exported to PDF.

The exported report can include:

- strategy
- coverage
- linked Runs
- QA assessment
- E2E profile
- roles
- phases
- Definition of Done

This is useful for review, auditability, handover, and release evidence.

---

## 22. Typical Test Hub workflow

Inside the application, a healthy flow is:

```text
Create / identify Release
        ↓
Create Test Plan
        ↓
Define strategy and Jira scope
        ↓
Add Planned Coverage
        ↓
Create or attach Test Cases
        ↓
Activate Test Plan
        ↓
Create Test Run
        ↓
Execute Manual / Automated tests
        ↓
Review Results
        ↓
Defect / Retest if needed
        ↓
QA Sign-off
        ↓
Complete Test Plan
```

The wider team workflow begins earlier in Jira and includes GitHub, Jenkins, and Playwright. See [QA Workflow Guide](QA_WORKFLOW.md).

---

## 23. Practical example: Registration feature

Assume Jira contains an Epic for a Registration feature with Stories such as:

```text
SCRUM-8   Registration page links
SCRUM-10  Registration page design
SCRUM-11  Password visibility
SCRUM-12  Terms & Conditions
SCRUM-13  Registration fields and buttons
SCRUM-14  Username and password complexity
```

A Test Hub plan might be:

```text
Name: Registration Feature Test Plan
Type: Feature
Application: Store
Feature: Registration
Status: Active
Target Release: v1.2 - Registration
Jira Scope: SCRUM-8, SCRUM-10, SCRUM-11, SCRUM-12, SCRUM-13, SCRUM-14
```

Planned coverage can then include:

```text
Navigation to Registration
Direct Registration URL
Login link from Registration
Password masked by default
Show / hide password
Terms required before registration
Required fields
Email validation
Duplicate username
Password minimum boundary
Password maximum boundary
Username boundaries
```

Some items may already have Test Cases and others may remain Pending until the requirement is clarified.

After the Test Cases are ready, QA can create a Run from the plan, execute it, review failures, retest fixes, and make the final QA assessment for the Release.

---

## 24. Glossary

**Test Plan** — the intended QA scope and strategy.

**Planned Coverage** — a scenario QA intends to validate, whether or not a Test Case already exists.

**Test Case** — a reusable test definition.

**Test Run** — one execution of selected Test Cases.

**Result** — the outcome of executing one Test Case in a Run.

**Release** — a delivery target that groups work intended to be delivered together.

**Sprint** — a time-boxed development period. Test Hub currently approximates the QA sprint from Active Test Plans rather than live Jira Sprint data.

**Defect** — a product issue found during testing and usually tracked in Jira.

**Retest** — execution performed to verify that a reported defect has been fixed.

**QA Sign-off** — the human QA readiness decision after reviewing coverage, execution, defects, blockers, and risk.

**Smoke** — a focused set of critical checks used to confirm that a build is testable or releasable enough for deeper testing.

**Regression** — testing intended to detect unintended impact to previously working behavior.

---

## Related documentation

- [Project README](../README.md)
- [QA Workflow Guide](QA_WORKFLOW.md)
