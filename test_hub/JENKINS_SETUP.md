# Test Hub -> Jenkins -> Playwright setup

This integration lets an Automated Test Run in Test Hub start Jenkins, execute only the selected pytest-bdd / Playwright cases, and report the results back into Test Hub.

## 1. Jenkins job parameters

Open the existing Playwright Jenkins job and choose **Configure**.

Enable **This project is parameterized** and add these String parameters:

- `TEST_RUN_ID`
- `TEST_CASE_IDS`
- `TEST_HUB_URL`

Test Hub supplies these values automatically when **Run with Playwright** is clicked.

The job must execute:

```bat
jenkins-build.bat
```

While testing this feature branch, make sure the Jenkins SCM branch is:

```text
*/feature/test-case-management
```

## 2. Shared Test Hub API key

Generate a secret locally:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Use the same value in both places.

### Test Hub PowerShell

```powershell
$env:TEST_HUB_API_KEY="YOUR_SECRET"
```

### Jenkins

Store the same value as a Jenkins **Secret text** credential and expose it to the build as:

```text
TEST_HUB_API_KEY
```

Do not commit this value.

## 3. Jenkins API credentials for Test Hub

Create a Jenkins API token for the Jenkins user that may build the Playwright job.

Before starting Test Hub:

```powershell
$env:JENKINS_URL="http://127.0.0.1:8080"
$env:JENKINS_JOB_NAME="YOUR_JENKINS_JOB_NAME"
$env:JENKINS_USER="YOUR_JENKINS_USERNAME"
$env:JENKINS_API_TOKEN="YOUR_JENKINS_API_TOKEN"
$env:TEST_HUB_BASE_URL="http://127.0.0.1:3000"
$env:TEST_HUB_API_KEY="YOUR_SECRET"

python test_hub\app.py
```

Do not commit Jenkins credentials.

## 4. Refresh imported BDD definitions

The Scenario Outlines now contain stable `case_id` values so Jenkins can select an exact example.

Run:

```powershell
python test_hub\import_bdd.py --update-existing
```

## 5. Run from Test Hub

1. Open `http://127.0.0.1:3000/test-runs`.
2. Create a test run with **Execution type = Automated**.
3. Select BDD cases such as `AUTH-01`, `CART-01`, or `E2E-001`.
4. Open the run.
5. Click **Run with Playwright**.

Expected flow:

```text
Test Hub
  -> Jenkins buildWithParameters
  -> jenkins-build.bat
  -> pytest-bdd + Playwright
  -> Test Hub result API
  -> Test Run / Release Report
```

The Test Run page refreshes automatically while the run is Queued or Running.

## Callback endpoints

Jenkins / pytest reports to:

```text
POST /api/test-runs/<run_id>/results
POST /api/test-runs/<run_id>/finish
```

Both require:

```text
Authorization: Bearer <TEST_HUB_API_KEY>
```


## 6. Archive Playwright report, traces and screenshots

In the Jenkins job:

1. Open **Configure**.
2. Scroll to **Post-build Actions**.
3. Click **Add post-build action** -> **Archive the artifacts**.
4. Set **Files to archive** to:

```text
report.html,test-results/**
```

5. If Jenkins shows **Archive artifacts only if build is successful**, leave it unchecked so failed runs keep their screenshots and traces.
6. Save the job.

Test Hub stores the Jenkins build number and build URL reported by Jenkins. After the build finishes, the Test Run page exposes:

- **Open Jenkins build**
- **HTML report**
- **Artifacts**

The HTML report URL is:

```text
<JENKINS_BUILD_URL>/artifact/report.html
```

The artifacts page is:

```text
<JENKINS_BUILD_URL>/artifact/
```

The Jenkins build script clears stale artifacts before each run and generates:

- `report.html`
- Playwright traces under `test-results/`
- screenshots for failed tests under `test-results/`
