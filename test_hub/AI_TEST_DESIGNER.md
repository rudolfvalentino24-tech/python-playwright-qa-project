# AI Test Designer

The AI Test Designer turns a feature description or acceptance criteria into structured Test Hub test-case drafts.

## What it does

- Sends the feature description plus existing Test Hub coverage to OpenAI.
- Uses Structured Outputs parsed into Pydantic models.
- Suggests IDs, titles, priorities, Manual/Automated type, suite tags, preconditions, steps and expected results.
- Gives Automated cases Given / When / Then style steps and prefers existing BDD wording when possible.
- Flags duplicate IDs and duplicate titles before creation.
- Shows an editable review screen.
- Creates only the cases the user explicitly selects.
- Saves accepted cases with status `Draft`.
- Inherits optional Jira story links supplied in the designer form.

The AI never writes directly to the BDD feature files in this version. BDD synchronization is intentionally a separate next step.

## Install dependencies

From the project root:

```powershell
python -m pip install -r test_hub\requirements.txt
```

## Configure OpenAI

Set an OpenAI API key in the same PowerShell session used to start Test Hub:

```powershell
$env:OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
```

Optional model override:

```powershell
$env:OPENAI_MODEL="gpt-5.6-terra"
```

Do not commit API keys.

## Start the AI-enabled Test Hub

Use:

```powershell
python test_hub\run_ai.py
```

This launcher imports the existing Test Hub application, registers the AI routes, adds the AI Test Designer entry point to the main page and then starts the same Flask application on port 3000.

Existing Jira and Jenkins environment variables continue to work unchanged.

## Workflow

1. Open Test Hub.
2. Click **Generate with AI**.
3. Enter Feature / Module and the requirement or acceptance criteria.
4. Choose the number of suggestions and preferred test type.
5. Optionally enter Jira story keys.
6. Click **Generate test cases**.
7. Review and edit the proposed cases.
8. Leave only the wanted cases selected.
9. Click **Create selected drafts**.

Automated cases must use Gherkin-style steps beginning with `Given`, `When`, `Then`, `And` or `But`. The server validates this again before saving.
