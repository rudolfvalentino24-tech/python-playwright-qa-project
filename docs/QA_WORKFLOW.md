# QA Workflow Guide

[Project README](../README.md) | [Test Hub Guide](TEST_HUB_GUIDE.md)

This guide explains the wider QA process around Test Hub: how Jira, Test Hub, GitHub, Jenkins, Python, pytest-bdd, and Playwright work together from requirement definition to release.

For instructions focused only on using the Test Hub application, see the [Test Hub Guide](TEST_HUB_GUIDE.md).

---

## 1. Purpose of the QA workflow

The goal is to make QA part of the delivery process from the beginning instead of waiting until development is finished.

A healthy workflow connects:

```text
Jira requirement
      ↓
Refinement
      ↓
Test planning
      ↓
Development and code review
      ↓
Manual / automated execution
      ↓
Defects and retest
      ↓
Release readiness
```

The complete tool chain in this project is:

```text
Jira
  ↓
Test Hub
  ↓
GitHub
  ↓
Jenkins
  ↓
Python / pytest-bdd / Playwright
  ↓
Test Hub Results
  ↓
Jira Defect / Retest
  ↓
QA Sign-off
  ↓
Release
```

---

## 2. Roles and responsibilities

### Product Owner

The Product Owner defines expected product behavior and business value.

Typical responsibilities:

- describe the user problem
- write or refine Acceptance Criteria
- define important Out of Scope items
- answer open product questions
- prioritize work
- decide product tradeoffs

The PO should not need to write every test scenario.

### Developer

The Developer determines implementation and contributes technical context.

Typical responsibilities:

- identify technical dependencies
- discuss feasibility and edge cases
- implement the agreed behavior
- write appropriate lower-level automated tests
- participate in code review
- fix defects

### QA

QA converts requirements and risk into a test strategy.

Typical responsibilities:

- review requirements early
- identify ambiguity
- ask refinement questions
- assess risk
- create Test Plans and Test Cases
- choose manual vs automated coverage
- execute tests
- report defects
- retest fixes
- assess release readiness

QA should not silently invent missing product behavior.

---

## 3. End-to-end delivery workflow

The wider process should look like this:

```text
Release Planning
        ↓
Jira Story
        ↓
Refinement
        ↓
Definition of Ready
        ↓
Ready for Development
        ↓
Test Plan
        ↓
Planned Coverage
        ↓
Test Cases
        ↓
Development
        ↓
Ready for QA
        ↓
Test Run
        ↓
Results
        ↓
Defect / Retest
        ↓
QA Sign-off
        ↓
Release
```

The important detail is that the **Release exists near the beginning as a delivery target**, while the final **Release decision happens at the end**.

---

## 4. Jira Story standard

Stories should use a consistent template so Development and QA can understand the requirement quickly.

Recommended Story template:

```text
User Story

As a...
I want...
So that...


Acceptance Criteria

AC1. ...
AC2. ...
AC3. ...


Out of Scope

- ...


QA Notes / Risks

- ...
```

### User Story

Explain the user or business value.

Example:

```text
As a customer
I want to create an account
So that I can access features that require authentication.
```

### Acceptance Criteria

Describe observable expected behavior.

Acceptance Criteria should answer:

> When is this Story considered functionally correct?

They should not describe implementation details unless the implementation itself is a requirement.

### Out of Scope

Record behavior deliberately excluded from the Story.

Example:

```text
- Password reset
- Social login
- Email verification
```

### QA Notes / Risks

Use this section for testing considerations, risks, dependencies, and open questions.

Do not use it as a hidden second Acceptance Criteria section.

---

## 5. Definition of Ready

A Story should normally be Ready for Development only when the team understands it well enough to build and test.

Recommended Definition of Ready:

```text
☑ User/business value is clear
☑ Acceptance Criteria are testable
☑ Major Out of Scope items are identified
☑ Dependencies are known
☑ Critical open questions are resolved
☑ QA understands the expected behavior
```

The Definition of Ready is a team agreement, not bureaucracy.

It does **not** mean every edge case must already be written by the PO.

For example, if the PO writes:

```text
Password must contain 5–20 characters.
```

QA can independently derive boundary scenarios:

```text
4   → invalid
5   → lower boundary
6   → normal
19  → normal
20  → upper boundary
21  → invalid
```

The PO defines behavior; QA derives coverage.

---

## 6. Refinement

Refinement is where the team turns a rough requirement into something safe enough to build.

QA should ask questions such as:

- What happens on failure?
- What happens at boundaries?
- Which fields are required?
- Are duplicates allowed?
- What happens after success?
- Are there role/permission differences?
- Is accessibility behavior expected?
- Does this change affect existing flows?
- Are there environment, data, or dependency risks?

The goal is not to make Jira enormous. The goal is to resolve product ambiguity before it becomes inconsistent code and inconsistent testing.

---

## 7. Sprint vs Release

A Sprint and a Release answer different questions.

### Sprint

A Sprint answers:

> What are we working on during this time-box?

Example:

```text
Sprint 4
- SCRUM-8
- SCRUM-10
- SCRUM-11

Sprint 5
- SCRUM-12
- SCRUM-13
- SCRUM-14
```

### Release

A Release answers:

> What are we delivering together to users?

Example:

```text
Release v1.2 - Registration

SCRUM-8
SCRUM-10
SCRUM-11
SCRUM-12
SCRUM-13
SCRUM-14
```

One Release can span multiple Sprints.

QA therefore needs both views:

```text
Sprint  = current work
Release = complete delivery scope
```

---

## 8. Test planning and shift-left QA

QA should start planning once the Story is sufficiently clear, ideally when it becomes Ready for Development.

The preferred timing is:

```text
Requirement clear
      ↓
Test Plan
      ↓
Planned Coverage
      ↓
Test Cases
      ↓
Code finished
      ↓
Execute tests
```

Avoid waiting for this:

```text
Code finished
      ↓
QA reads ticket for the first time
      ↓
QA begins test design
```

That is too late to influence requirements or design.

### When Test Cases are created

Test Cases should usually be created **before development is finished**.

They do not need to be perfect on day one. Implementation details may cause them to be refined later, but most functional, boundary, negative, accessibility, and regression scenarios can be designed early.

Use Planned Coverage before detailed Test Cases when QA knows what must be tested but the requirement still needs clarification.

For application instructions, see [Test Hub Guide — Test Plans](TEST_HUB_GUIDE.md#5-test-plans) and [Planned Coverage](TEST_HUB_GUIDE.md#6-planned-coverage).

---

## 9. Test Case design

QA should choose coverage based on behavior and risk, not simply produce one Test Case per Acceptance Criterion.

Useful categories include:

### Positive

Verify expected successful behavior.

### Negative

Verify invalid input and failure paths.

### Boundary

Verify values around limits.

### Regression

Protect existing behavior affected by the change.

### Accessibility

Check keyboard access, accessible labels, focus, and other relevant usability requirements.

### Security

Check authentication, authorization, exposure of sensitive data, and role boundaries where relevant.

### Exploratory

Investigate risks that are difficult to fully script in advance.

---

## 10. GitHub workflow

GitHub contains the application code, tests, and Test Hub source.

A typical development flow is:

```text
Jira Story
    ↓
Feature branch
    ↓
Implementation + tests
    ↓
Pull Request
    ↓
Review
    ↓
Merge
```

QA should use GitHub context to understand what changed when that information improves test selection.

Examples:

- changed authentication code may require login and registration regression
- changed shared component may affect multiple pages
- changed API contract may affect UI and API tests

### Safe local branch update

When working on the Test Hub project branch, prefer:

```powershell
git status
git fetch origin
git pull --ff-only origin feature/test-case-management
```

If Git reports that local changes would be overwritten, stop and inspect the exact message before using stash, reset, restore, or any destructive command.

---

## 11. Python, pytest-bdd, and Playwright

The automation layer uses Python-based tests, including pytest-bdd and Playwright.

A typical BDD structure is:

```text
Feature / Scenario
      ↓
pytest-bdd step definitions
      ↓
Page Objects / helper code
      ↓
Playwright browser actions and assertions
```

### Why BDD is useful here

BDD scenarios can connect readable business behavior to executable automation.

Example concept:

```gherkin
Scenario: User can open Terms and Conditions from Login
  Given the Login page is open
  When the user opens Terms and Conditions
  Then the Terms and Conditions page is displayed
```

The scenario remains understandable to QA while Playwright performs the real browser interaction.

### Test data

Use stable test data and fixtures where possible. Do not hardcode real credentials, secrets, or production data.

### Page Objects

Page Objects keep selectors and page behavior reusable so that scenarios focus on intent rather than low-level browser details.

---

## 12. Jenkins and automated execution

The current automated flow is:

```text
Test Hub selects Test Cases
        ↓
Jenkins job: PythonPlaywrightTest
        ↓
pytest-bdd collection
        ↓
selected BDD cases only
        ↓
Playwright execution
        ↓
results / screenshots / traces
        ↓
Test Hub
```

Test Hub BDD selection filters pytest collection so that selected cases are the ones executed.

The Jenkins execution is configured to preserve useful failure evidence such as:

- Playwright traces
- screenshots on failure
- test output
- Jenkins build information

Typical Playwright flags include:

```text
--tracing on
--screenshot only-on-failure
--output=test-results
```

Jenkins archives the relevant report and test-result artifacts.

For the Test Hub side of this flow, see [Test Hub Guide — Manual and automated execution](TEST_HUB_GUIDE.md#11-manual-and-automated-execution).

---

## 13. Test execution

Execution should be driven by the Test Plan and risk.

A useful sequence is:

```text
Smoke / environment confidence
        ↓
Critical and High-risk coverage
        ↓
Feature functional testing
        ↓
Negative / boundary testing
        ↓
Regression
        ↓
Exploratory testing
```

Not every project needs this exact order, but high-impact risk should normally be tested earlier than low-impact cosmetic behavior.

### Results

Use clear outcomes:

- Passed
- Failed
- Blocked
- Skipped
- Not Run

A Blocked result should include the reason. Do not mark a test Failed simply because the environment or test data made execution impossible.

---

## 14. Defect and retest workflow

A failure should lead to a reproducible defect when the observed behavior is genuinely incorrect.

Recommended flow:

```text
Failed Test
    ↓
Investigate
    ↓
Jira Defect
    ↓
Developer Fix
    ↓
Ready for Retest
    ↓
Retest Run
    ↓
Verified / Retest Failed / Retest Blocked
```

A useful defect should include enough evidence to reproduce and understand the problem, such as:

- affected environment
- preconditions
- steps
- expected result
- actual result
- screenshots or logs when useful
- related Story / Test Case

A failed retest should not be silently changed to Passed; it should preserve the history of the failed fix attempt.

For Test Hub retest behavior, see [Test Hub Guide — Defects and retesting](TEST_HUB_GUIDE.md#13-defects-and-retesting).

---

## 15. Release Readiness

Release readiness is not just a percentage.

QA should consider:

- requirement coverage
- Test Case coverage
- execution completeness
- Critical / High failures
- blockers
- high-risk test execution
- smoke status
- known defects
- accepted risks
- unresolved requirement ambiguity

A release decision can be:

- Ready
- Ready with known risks
- Not Ready
- Not Assessed

The final decision should remain human-owned.

For the in-app view, see [Test Hub Guide — Release Readiness](TEST_HUB_GUIDE.md#14-release-readiness).

---

## 16. Example: Registration feature

Assume the team has this Jira structure:

```text
SCRUM-7   Create a new Registration page        [Epic]

SCRUM-8   Registration page links               [Story]
SCRUM-10  Registration page design              [Story]
SCRUM-11  Password visibility on Registration   [Story]
SCRUM-12  Terms & Conditions                    [Story]
SCRUM-13  Registration fields and buttons       [Story]
SCRUM-14  Username and password complexity      [Story]
```

### Step 1 — Release planning

Create or identify:

```text
Release v1.2 - Registration
```

The Release is the delivery target for the full Registration feature.

### Step 2 — Refinement

QA reviews the Stories.

For SCRUM-13, QA may identify questions such as:

```text
Which fields are mandatory?
Can the same username be reused?
Can the same email be reused?
What happens after successful registration?
What validation messages are expected?
```

These questions are resolved with the PO instead of being silently invented by QA.

### Step 3 — Definition of Ready

Once the critical questions are resolved, the Story can move to Ready for Development.

### Step 4 — Test Plan

Create:

```text
Registration Feature Test Plan
```

Link the Jira scope and target Release.

### Step 5 — Planned Coverage

Examples:

```text
Registration navigation
Direct Registration URL
Password visibility
Terms required before registration
Required field validation
Email validation
Duplicate username
Password minimum boundary
Password maximum boundary
Username boundaries
```

### Step 6 — Test Cases

Create detailed Test Cases before development is finished where possible.

For SCRUM-14, examples include:

```text
Password with 4 characters → rejected
Password with 5 characters → accepted if all other rules pass
Password with 20 characters → accepted if all other rules pass
Password with 21 characters → rejected
Password without uppercase → rejected
Password without number → rejected
Password without special character → rejected
Email-shaped password → rejected
Username with 4 characters → rejected
Username with 5 characters → accepted if otherwise valid
Username with 21 characters → rejected
Email-shaped username → rejected
```

### Step 7 — Development and GitHub

Developers implement the Stories on branches and submit Pull Requests.

QA can use the changed-code context to decide whether additional regression is needed.

### Step 8 — Ready for QA

Once the feature is deployed to the test environment and entry criteria are satisfied, QA creates or continues the relevant Test Run.

### Step 9 — Jenkins / Playwright

Automated cases are triggered through the Test Hub → Jenkins → pytest-bdd → Playwright path.

Manual cases are executed directly by QA.

### Step 10 — Results and defects

Failures create defect/retest work where necessary.

### Step 11 — Release readiness

QA reviews:

```text
Stories covered
Test Cases created
Tests executed
Passed
Failed
Blocked
Not Run
High-risk status
Smoke status
Known defects
```

Then QA records the readiness decision for v1.2.

---

## 17. Recommended working agreement

A compact team agreement for this project is:

```text
PO
Defines expected behavior and business value.

Developer
Defines and implements the technical solution.

QA
Challenges ambiguity, assesses risk, designs coverage, and validates quality.
```

And:

```text
No Story should normally start development while critical product questions remain unresolved.

QA starts test planning before development finishes.

A Release is planned early and assessed continuously.

Failed, Blocked, and Not Run are different states and should remain distinct.

AI can assist QA analysis but must not silently invent product requirements.
```

---

## 18. Glossary

**Acceptance Criteria** — observable behavior that defines when a Story is functionally correct.

**Definition of Ready** — team checklist confirming a Story is understood enough to start development.

**Definition of Done** — agreed conditions required before work is considered complete.

**Sprint** — time-boxed set of current development work.

**Release** — set of work intended to be delivered together.

**Test Plan** — QA strategy and intended coverage for a feature, release, regression effort, or other scope.

**Planned Coverage** — scenario QA intends to test even if no detailed Test Case exists yet.

**Test Case** — reusable definition of a test scenario.

**Test Run** — one execution of selected Test Cases.

**Regression** — testing intended to detect unintended impact to existing behavior.

**Smoke** — small set of critical checks used to establish basic build confidence.

**Retest** — verification that a specific defect fix now behaves correctly.

**Shift-left QA** — involving QA earlier in refinement, planning, and development rather than only after implementation.

---

## Related documentation

- [Project README](../README.md)
- [Test Hub Guide](TEST_HUB_GUIDE.md)
