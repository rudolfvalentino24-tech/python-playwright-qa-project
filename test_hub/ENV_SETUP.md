# Test Hub local environment

Test Hub loads `test_hub/.env` automatically before importing the Flask app or integration modules.

## Setup

1. Copy `test_hub/.env.example` to `test_hub/.env`.
2. Replace every `replace-with-...` placeholder with the real local secret.
3. Keep the Jenkins `test-hub-api-key` credential exactly equal to `TEST_HUB_API_KEY` in this file.
4. Start Test Hub normally:

```powershell
python test_hub\run_ai.py
```

The real `.env` file is ignored by Git and must never be committed.

## Precedence

Environment variables already set in PowerShell or by the operating system take precedence over values in `test_hub/.env`. This makes the local file convenient while still allowing CI/deployment environments to inject their own secrets.

## Variables

- `TEST_HUB_BASE_URL` - Test Hub base URL used by Jenkins callbacks.
- `TEST_HUB_API_KEY` - shared secret used to authenticate Jenkins result callbacks.
- `SECRET_KEY` - local Flask session secret.
- `JIRA_SITE_URL` - Jira Cloud site URL.
- `JIRA_PROJECT_KEY` - Jira project key.
- `JIRA_EMAIL` - Atlassian login email.
- `JIRA_API_TOKEN` - Atlassian API token.
- `JENKINS_URL` - Jenkins base URL.
- `JENKINS_JOB_NAME` - Jenkins job used for automated test runs.
- `JENKINS_USER` - Jenkins user used by Test Hub.
- `JENKINS_API_TOKEN` - Jenkins API token.
- `OPENAI_API_KEY` - OpenAI API key for AI Test Designer.
- `OPENAI_MODEL` - model used by AI Test Designer.
