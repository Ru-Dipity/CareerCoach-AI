# CareerCoach AI

An interactive Streamlit application that generates personalized practice quizzes (Multiple Choice or Fill-in-the-Blank) using a **pluggable multi-LLM backend** (Groq or DeepSeek) via LangChain + Pydantic. Users can either type a single study topic or paste a full job-posting description; the application extracts required skills, normalizes and categorizes them, and produces a skill-matched interview-prep quiz.

## Project Overview

CareerCoach AI was originally built as a topic-to-quiz generator. This release adds a decoupled Job Description Parser feature pipeline that reuses the existing LLM client, retry wrapper, and Pydantic parsing contracts while keeping all new logic isolated in a new `src/parser/` module. It also introduces a **provider-agnostic LLM layer**: a single `get_llm(provider)` factory dispatches to either the Groq or DeepSeek client, so every generator can be switched at runtime from the sidebar without touching business logic. All source code, comments, variables, file names, and documentation in this repository are written in English.

**Repository entry point:** [application.py](file:///root/LLM-Projects/Study-Buddy-AI/application.py)
**Quiz orchestration (state + render + grading):** [helpers.py](file:///root/LLM-Projects/Study-Buddy-AI/src/utils/helpers.py)
**Question generation with retry loop:** [question_generator.py](file:///root/LLM-Projects/Study-Buddy-AI/src/generator/question_generator.py)
**Skill extraction + skill-matched question generation (NEW):** [job_parser.py](file:///root/LLM-Projects/Study-Buddy-AI/src/parser/job_parser.py)
**LLM prompt templates (includes 3 NEW job-pipeline templates):** [templates.py](file:///root/LLM-Projects/Study-Buddy-AI/src/prompts/templates.py)
**Pydantic schemas (includes 2 NEW skill-tagged variants):** [question_schemas.py](file:///root/LLM-Projects/Study-Buddy-AI/src/models/question_schemas.py)
**Configuration constants:** [settings.py](file:///root/LLM-Projects/Study-Buddy-AI/src/config/settings.py)
**LLM provider factory (single dispatch point):** [provider_factory.py](file:///root/LLM-Projects/Study-Buddy-AI/src/llm/provider_factory.py)
**Groq LLM client factory:** [groq_client.py](file:///root/LLM-Projects/Study-Buddy-AI/src/llm/groq_client.py)
**DeepSeek LLM client factory (NEW):** [deepseek_client.py](file:///root/LLM-Projects/Study-Buddy-AI/src/llm/deepseek_client.py)
**Custom exceptions + structured logger:** [common/](file:///root/LLM-Projects/Study-Buddy-AI/src/common)
**Container + K8s manifests:** [Dockerfile](file:///root/LLM-Projects/Study-Buddy-AI/Dockerfile), [manifests/](file:///root/LLM-Projects/Study-Buddy-AI/manifests)

---

## Environment & Dependencies

### Runtime requirements
- Python 3.10+
- **At least one** LLM provider API key:
  - A valid **Groq API key** (obtain from <https://console.groq.com/keys>), and/or
  - A valid **DeepSeek API key** (obtain from <https://platform.deepseek.com/api_keys>)

### Python dependencies (declared in [requirements.txt](file:///root/LLM-Projects/Study-Buddy-AI/requirements.txt))
- `langchain` — composable LLM primitives
- `langchain-groq` — Groq provider integration
- `langchain-openai` — OpenAI-compatible client used for the DeepSeek endpoint
- `pandas` — tabular results and CSV export
- `streamlit` — interactive UI framework
- `python-dotenv` — `.env` file loader
- `plotly` — radar chart rendering for the candidate matcher
- `pypdf` — PDF résumé text extraction
- `pydantic` (transitive) — typed response validation

### Environment variables
Copy the example below into a `.env` file at the repository root. **Both providers are configured independently** — you may supply only one key if you only intend to use that provider.

```dotenv
# ---- Groq provider (independent) ----
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# Optional: override the default Groq model
# GROQ_MODEL_NAME=openai/gpt-oss-120b

# ---- DeepSeek provider (independent) ----
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# Optional: override the default DeepSeek model / endpoint
# DEEPSEEK_MODEL_NAME=deepseek-chat
# DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
```

> **Security:** `.env` is listed in both [.gitignore](file:///root/LLM-Projects/Study-Buddy-AI/.gitignore) and [.dockerignore](file:///root/LLM-Projects/Study-Buddy-AI/.dockerignore), so keys are never committed to Git nor baked into the Docker image. In Kubernetes, keys are injected at runtime from a Secret via `secretKeyRef` (see Option C below). Never hard-code a key in source files.

The following constants live in [settings.py](file:///root/LLM-Projects/Study-Buddy-AI/src/config/settings.py) and can be tuned without code changes:
| Constant | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | *(unset)* | Groq provider credential |
| `MODEL_NAME` | `openai/gpt-oss-120b` | Groq model identifier (env-overridable via `GROQ_MODEL_NAME`) |
| `DEEPSEEK_API_KEY` | *(unset)* | DeepSeek provider credential |
| `DEEPSEEK_MODEL_NAME` | `deepseek-chat` | DeepSeek model identifier |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | DeepSeek OpenAI-compatible endpoint |
| `TEMPERATURE` | `0.9` | Generation sampling temperature (shared) |
| `MAX_RETRIES` | `3` | Retry attempts per parse-sensitive LLM call |
| `MAX_JOB_TEXT_LENGTH` | `10000` | Character cap for pasted job descriptions |

---

## Local Deployment Steps

### Option A: Run on bare metal (venv)
```bash
cd /root/LLM-Projects/Study-Buddy-AI
python -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# Configure provider keys (create .env manually if no example exists)
#   GROQ_API_KEY=gsk_...
#   DEEPSEEK_API_KEY=sk-...

streamlit run application.py \
    --server.port=8501 \
    --server.address=0.0.0.0
```
Then open <http://localhost:8501> in your browser.

Verify imports compile without starting the UI:
```bash
python -m compileall -q .
python -c "from src.llm.provider_factory import get_llm; print('OK')"
python -c "from src.parser.job_parser import SkillExtractor, SkillQuestionGenerator; print('OK')"
```

### Option B: Run with Docker
The [Dockerfile](file:///root/LLM-Projects/Study-Buddy-AI/Dockerfile) uses a multi-stage build. Stage 1 (`builder`) compiles dependencies into `/opt/venv`; Stage 2 (`runner`) copies only the virtual environment and source, then runs as a non-privileged user on port 8501 with a HEALTHCHECK.

```bash
cd /root/LLM-Projects/Study-Buddy-AI
docker build -t careercoach-ai:latest .

docker run --rm -it \
    -p 8501:8501 \
    --env-file .env \
    --name careercoach-ai \
    careercoach-ai:latest
```

Health check endpoint: `http://localhost:8501/_stcore/health`.

### Option C: Kubernetes (K8s manifests)
The reference [manifests/](file:///root/LLM-Projects/Study-Buddy-AI/manifests) directory ships a Deployment (`llmops-app`, 2 replicas) + Service (`llmops-service`, NodePort, port 80 → targetPort 8501). The Deployment reads both provider keys from a single Secret named `groq-api-secret`:

| Secret key | Required | Consumed by |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq provider |
| `DEEPSEEK_API_KEY` | No (`optional: true`) | DeepSeek provider |

Create the Secret and apply the manifests:

```bash
# Create the Secret referenced by deployment.yaml (name must match exactly)
kubectl create secret generic groq-api-secret \
    --from-literal=GROQ_API_KEY=$(grep GROQ_API_KEY .env | cut -d= -f2) \
    --from-literal=DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY .env | cut -d= -f2)

kubectl apply -f manifests/deployment.yaml -f manifests/service.yaml
```

Because the Service is `NodePort`, it is reachable on `<NodeIP>:<NodePort>` once the pods are Ready. For local access without a Node IP, use port-forward against the real Service name:

```bash
kubectl port-forward svc/llmops-service 8501:80
```

> The `DEEPSEEK_API_KEY` entry is marked `optional: true` in the Deployment, so a cluster that only needs Groq can omit that key from the Secret without blocking pod startup.

---

Jenkins installation :
docker run -d \
  --name jenkins \
  --restart unless-stopped \
  -p 8080:8080 \
  -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -u root \
  jenkins/jenkins:lts-jdk21

initialAdminPassword:

docker exec -it jenkins cat /var/jenkins_home/secrets/initialAdminPassword

Jenkins Setup Steps

Paste the initial password from docker logs jenkins
Click Install Suggested Plugins
Create Admin User
Skip agent security warning (ignore for now)
Install Required Plugins

Navigate to: Manage Jenkins → Plugins
Install:
Docker
Docker Pipeline
Kubernetes


GitHub Integration with Jenkins
🔐 Generate GitHub Personal Access Token
Go to: GitHub → Settings → Developer Settings → Personal access tokens → Generate new token

Select classic token and give it the following permissions:

admin:org
admin:org_hook
admin:public_key
admin:repo_hook
repo
workflow
🔑 Add GitHub Credentials to Jenkins
Go to: Manage Jenkins → Credentials → Global → Add Credentials
Username: Your GitHub username
Password: The token you just generated
ID: github-token
Description: github-token
🚀 Create a New Pipeline Job in Jenkins
Go to Jenkins Dashboard → New Item
Enter Name: gitops
Select Pipeline
Scroll to the Pipeline section:
Select Pipeline from SCM
Choose Git
Repository URL: Your GitHub repo link
Credentials: Select the github-token credential
Branch: main


🐳 Create DockerHub Repository
Go to https://hub.docker.com
Create a new repository, e.g., lukas7/testing-9
🔐 Generate DockerHub Access Token
Go to DockerHub Account → Account Settings → Security → New Access Token
Name it appropriately and give it Read/Write permission
Copy the generated token
➕ Add DockerHub Credentials to Jenkins
Go to Jenkins → Manage Jenkins → Credentials → Global → Add Credentials
Username: DockerHub username (e.g., lukas7)
Password: The DockerHub token
ID: gitops-dockerhub
Description: DockerHub Access Token



 Step 1: Check Existing Namespaces
kubectl get namespace
🆕 Step 2: Create New Namespace for ArgoCD
kubectl create ns argocd
✅ Run the first command again to verify the namespace is created.

📦 Step 3: Install ArgoCD
Apply the ArgoCD installation manifest from GitHub:

kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
🔍 Step 4: Validate ArgoCD Components
Check all resources inside the argocd namespace:

kubectl get all -n argocd

kubectl patch svc argocd-server -n argocd -p '{"spec": {"type": "NodePort"}}'

kubectl get svc -n argocd

cat /etc/rancher/k3s/k3s.yaml

ip route show | grep docker0

cp /etc/rancher/k3s/k3s.yaml ./jenkins-k3s.yaml
打开 ./jenkins-k3s.yaml，将里面的：

server: https://127.0.0.1:6443 修改为 server: https://172.17.0.1:6443 （（以 172.17.0.1 为例）） 

Jenkins 存放 kubeconfig 最标准的凭据类型是 Secret file：

打开浏览器进入 Jenkins 面板。

依次点击：Manage Jenkins -> Credentials -> System -> Global credentials (unrestricted)。

点击右上角 Add Credentials：

Kind: 选择 Secret file。

File: 点击 Choose File 上传刚才修改好的 jenkins-k3s.yaml 文件（或者将其下载到本地电脑后上传）。

ID: 输入一个好记的名字，例如 k8s-kubeconfig（流水线脚本会根据这个 ID 调取）。

Description: 可选填写 K3s Cluster Kubeconfig。

点击 Create 保存。


在 Jenkinsfile 流水线中调用
在 Jenkinsfile 中，使用 withCredentials 注入该配置文件即可：

Connect GitHub Repository to ArgoCD
Open ArgoCD UI → Go to Settings → Repositories → Connect Repo via HTTPS.

Fill in details:

Type: git
Name: anything you want
Project: default
Repo URL: https://github.com/data-guru0/GitOPS-testing.git
Username & Password: Provide GitHub username and token (optional but recommended)
Click Connect.

You should see a success message confirming the GitHub repo is connected to ArgoCD.

kubectl create secret generic groq-api-secret \
  --from-literal=GROQ_API_KEY="" \
  -n argocd

Step 4: Create a New Application in ArgoCD
Go to Applications → Click New App.

Fill in the form:

Name: Gitops (or any name you prefer)
Project: default
Sync Policy: Automatic
Tick Sync Pipeline Resources and Self Heal.
Leave other settings as default.
Repository URL: select your connected repo.
Revision: main (branch)
Path: manifests
Cluster URL: select from dropdown.
Namespace: argocd
Click Create.

You should see the application status as Synced and Healthy.

## Feature Descriptions

### 0. LLM Provider Selection (NEW)
The sidebar exposes an **LLM Provider** radio with two options: `Groq` and `DeepSeek`.

- The selection is stored in `st.session_state.llm_provider` and is passed as the `provider` argument into every generator (`QuestionGenerator`, `SkillExtractor`, `SkillQuestionGenerator`, `ProfileJobMatcher`).
- Switching provider **automatically resets the quiz state** so no questions or results from the previous provider leak into the new session.
- A caption below the selector shows the currently active provider.
- The two providers are **fully decoupled**: each has its own client module, its own API key, and its own model/endpoint settings. Selecting DeepSeek never touches the Groq code path and vice versa.
- If the selected provider's API key is missing, a clear `ValueError` is raised explaining exactly which environment variable to set — no confusing downstream SDK error.

| Provider | Client module | SDK | Default model | Endpoint |
|---|---|---|---|---|
| Groq | [groq_client.py](file:///root/LLM-Projects/Study-Buddy-AI/src/llm/groq_client.py) | `langchain-groq` | `openai/gpt-oss-120b` | Groq default |
| DeepSeek | [deepseek_client.py](file:///root/LLM-Projects/Study-Buddy-AI/src/llm/deepseek_client.py) | `langchain-openai` | `deepseek-chat` | `https://api.deepseek.com/v1` |

### 1. Topic Quiz (original feature)
1. Open the side panel and choose your **LLM Provider** (`Groq` or `DeepSeek`).
2. Leave **Quiz Mode** on `Topic Quiz`.
3. Pick a **Question Type** (`Multiple Choice` or `Fill in the Blank`).
4. Enter a single study topic such as `Kubernetes`, `REST APIs`, or `Python asyncio`.
5. Select **Difficulty Level** (`Easy`, `Medium`, `Hard`) and **Number of Questions** (1-10).
6. Click **Generate Quiz**. Progress feedback is shown inside a spinner.
7. Answer questions then click **Submit Quiz**. A per-question breakdown with a rounded score percentage is rendered.
8. Every question — **whether answered correctly or not** — now shows a 💡 **Explanation** block describing why the correct answer is right.
9. Optional: click **Save Results** to export a timestamped CSV into the `results/` directory, then **Download Results** to fetch it. The CSV includes the new `explanation` column.
10. **Reset Quiz** clears all state so you can begin fresh.

### 2. Job Description Quiz (NEW feature)
Converts a full job posting into a categorized skill inventory, then generates N skill-matched questions. See the step-by-step walkthrough below.

### 3. Common UX features (post-audit)
- MCQ options no longer pre-select the first answer (see P0 bug fix row in the audit checklist).
- Empty/whitespace topics are blocked before LLM calls.
- Spinners wrap every long-running generation step.
- Visible strings, log messages, and the FillBlank underscore token are internally consistent.
- Score is rounded to 1 decimal place and suffixed with `%`.
- **Per-question explanations** are shown for every question, correct or incorrect (see feature 4 below).
- **Match & Skill reports are downloadable** as JSON (see feature 5 below).

### 4. Per-question explanations (NEW feature)
Every generated question now carries an `explanation` field produced by the LLM:
- Added as an optional field (`default=""`) to all four schemas in [question_schemas.py](file:///root/LLM-Projects/Study-Buddy-AI/src/models/question_schemas.py) — backward compatible with older payloads.
- Requested in all four prompt templates in [templates.py](file:///root/LLM-Projects/Study-Buddy-AI/src/prompts/templates.py).
- Propagated through both generators ([`QuizManager.generate_questions()`](file:///root/LLM-Projects/Study-Buddy-AI/src/utils/helpers.py) and [`SkillQuestionGenerator.generate_questions()`](file:///root/LLM-Projects/Study-Buddy-AI/src/parser/job_parser.py)) and carried into the result rows by [`QuizManager.evaluate_quiz()`](file:///root/LLM-Projects/Study-Buddy-AI/src/utils/helpers.py).
- Rendered with `st.info()` in the results view for **both** the correct and incorrect branches.
- Automatically included as an `explanation` column in the exported CSV (no change to `save_to_csv` was needed).

### 5. Downloadable Match & Skill report (NEW feature)
The Candidate Fit Assessment report can now be saved and downloaded:
- New helper [`save_match_report_to_json()`](file:///root/LLM-Projects/Study-Buddy-AI/src/utils/helpers.py) serializes the `MatchResult` object to a timestamped JSON file under `results/`, mirroring the existing `save_to_csv` flow.
- JSON is used (rather than CSV) because `MatchResult` contains nested structures (`radar_data`, `matched_skills`, `missing_skills`, `strengths`, `gap_analysis`, `targeted_interview_topics`) that a flat CSV would destroy.
- A **Save Match Report** button and a **Download Match Report** button were added to [`_render_candidate_matcher()`](file:///root/LLM-Projects/Study-Buddy-AI/application.py); the saved path is held in `st.session_state.saved_match_file` and cleared by **Reset Quiz**.

---

## Job Description Parser — Step-by-Step Usage

### Step 1: Switch mode
In the sidebar, set **Quiz Mode** to `Job Description Quiz`.

### Step 2: Paste the posting
Paste the raw job posting into the text area labeled **Paste Job Description**.
- Supports multi-line text, bullet lists, whitespace, and pasted content copied from rich-text editors (HTML tags and control characters are stripped by the sanitizer while newlines are preserved).
- A live character counter shows `Current / Max (percentage%)`. The limit is `MAX_JOB_TEXT_LENGTH` (default 10 000 characters); the widget itself enforces the cap and the server-side validator re-checks it independently.
- Illegal patterns (prompt-injection phrases such as "ignore previous instructions", fictitious role-assignment prefixes, and role-tag token sequences) are blocked with an inline error message and NO LLM call is made.

### Step 3: Choose remaining settings
Select **Question Type**, **Difficulty Level**, and **Number of Questions** (same controls as Topic Quiz).

### Step 4: Parse + generate
Click **Generate Quiz**. The application:
1. Runs `SkillExtractor.validate_input()`.
2. Runs `SkillExtractor.sanitize_input()` to produce a clean posting.
3. Calls the LLM with `skill_extraction_prompt_template` (retries on parse failure up to `MAX_RETRIES`).
4. Post-processes: case-insensitive deduplication, name normalization, occurrence count aggregation, category coercion into the 7 canonical buckets.
5. Renders the **Extracted Skills Preview** table (Skill / Category / Occurrences) with inferred Role and Seniority chips.
6. Invokes `SkillQuestionGenerator.generate_questions()` using the skill-aware MCQ or FillBlank prompt templates.
7. Persists the questions (each carrying a `target_skill` field) into `quiz_manager.questions`, and stores the coverage report.

### Step 5: Take the quiz
Answer questions and click **Submit Quiz**. Each question shows its matched skill tag in the result header.

### Step 6: Review the Skill Coverage Report
Below the per-question results you will see:
- **Questions aligned to extracted skills:** `X/Y (Z%)` — computed by `compute_alignment()` in [job_parser.py](file:///root/LLM-Projects/Study-Buddy-AI/src/parser/job_parser.py#L254-L280). Expected ratio ≥ 95%.
- An expandable **View N questions with unmapped target_skill** expander, listing each unmapped question index, target_skill, and a 60-char question snippet.

### Step 7: Save / download CSV
CSV export now carries an extra `target_skill` column when questions originate from the Job pipeline, plus an `explanation` column for every question.

### Step 8: Save / download the Match & Skill report
After generating the Candidate Fit Assessment, click **Save Match Report** to write a timestamped JSON file into `results/`, then **Download Match Report** to fetch it.

---

## Code Audit Checklist

Produced from a full line-by-line review of every `.py` file in the repository. Severity scale: **P0 Critical** (breaks the stated promise / legal contract / user data), **P1 High** (material UX or correctness defect), **P2 Medium** (cosmetic / consistency / missing affordance), **P3 Low** (code hygiene / polish).

| # | Issue Description | Impact Scope | Severity |
|---|---|---|---|
| 1 | `st.radio()` in `QuizManager.attempt_quiz` at [helpers.py:57](file:///root/LLM-Projects/Study-Buddy-AI/src/utils/helpers.py#L57-L62) did not pass `index=None`, causing the **first MCQ option to be pre-selected and auto-recorded as the user's answer** even on zero interaction. | Quiz correctness, fairness, scored results for every MCQ user | **P0 Critical** |
| 2 | Fill-in-the-Blank prompt at [templates.py:21-35](file:///root/LLM-Projects/Study-Buddy-AI/src/prompts/templates.py#L21-L35) required `_____` (5 underscores) but the schema validator in [question_generator.py:58](file:///root/LLM-Projects/Study-Buddy-AI/src/generator/question_generator.py#L58-L59) accepted only `___` (3 underscores). Every generated FillBlank question risked a retry-loop failure. | FillBlank generation reliability, token burn, and silent failures | **P1 High** |
| 3 | Page title `set_page_config("Studdy Buddy AI")` had a typo. | Browser tab title, bookmarks, search-engine snippets | **P2 Medium** |
| 4 | Sidebar select box label `Dificulty Level` misspelled. | All users; on-screen accessibility label used by screen readers | **P2 Medium** |
| 5 | Local variable `succces` and string literals `sucesfully`, `Sucesfully`, `Downlaod`, `avialble` scattered across application UI strings, log lines, and success toasts. | Localization consistency, screen readers, support log grepability | **P2 Medium** |
| 6 | Final score printed as a raw float e.g. `66.66666666666` with no rounding and no `%` sign. | Scored results legibility, user perception of precision | **P2 Medium** |
| 7 | Clicking **Generate Quiz** with an empty / whitespace-only topic silently sent an LLM request with a vacuous prompt, wasting tokens and producing useless output. | API cost, perceived latency, user trust | **P1 High** |
| 8 | No progress feedback wrapped the N-question sequential generation loop. App appeared frozen while the LLM looped. | Perceived responsiveness, ability to abort mid-flight | **P1 High** |
| 9 | No Reset / New Quiz affordance existed in the sidebar. Users had to reload the page to clear stale state, losing the Streamlit session. | Session ergonomics, repeated-use workflow | **P2 Medium** |
| 10 | `st.radio` inline label read "Select **and** answer for Question N" instead of "Select **an** answer". | UX polish, ESL/non-native reading friction | **P3 Low** |
| 11 | No README documentation existed; missing setup guide, no feature walkthrough, no troubleshooting section. | Onboarding friction, operator self-service | **P2 Medium** |
| 12 | No input validation or length cap existed for the planned job-text ingestion path before this release. | Robustness, abuse surface, prompt-injection risk for the new feature | **P1 High** |
| 13 | No decoupled module boundary for the planned job parser. Original code only supported single-topic generation. | Maintainability, code-review scope for the new feature, risk of regression to Topic Quiz | **P2 Medium** |
| 14 | Generated questions for the planned job parser had no explicit skill-to-question mapping, making the 95% coverage promise unverifiable at runtime. | NFR observability, QA auditability | **P1 High** |

Total: **1 P0, 5 P1, 6 P2, 2 P3** items. **14 issues were identified and planned** (items 1-11 retroactively on baseline, 12-14 forward-looking on the planned feature). All 14 are addressed in this release.

---

## Defect Repair Log (this release)

A second, deeper audit was performed against the actual repository state. The following **blocking and functional defects** were found and fixed under the **minimal-modification principle** (additive changes only; no core logic rewrite, no architecture redesign).

### P0 — Blocking defects (application could not even import)

| # | Defect | Root cause | Fix | Files touched |
|---|---|---|---|---|
| B1 | Literal `[cite: 1]` markers embedded in Python source caused `SyntaxError` on import (10 occurrences). | Copy/paste artifacts from an external editor leaked into committed source. | Removed every marker; verified `grep -rn "cite:" --include="*.py" .` returns zero matches. | [matcher.py](file:///root/LLM-Projects/Study-Buddy-AI/src/generator/matcher.py), [pdf_loader.py](file:///root/LLM-Projects/Study-Buddy-AI/src/utils/pdf_loader.py) |
| B2 | `matcher.py` imported `GroqClient` — a class that does not exist anywhere in the codebase. | Stale import from a pre-refactor design. | Switched to the provider factory `get_llm(provider)`. | [matcher.py](file:///root/LLM-Projects/Study-Buddy-AI/src/generator/matcher.py) |
| B3 | `matcher.py` imported `MATCH_ANALYSIS_PROMPT` — no such symbol exists. | Name drift vs. the real template. | Switched to `candidate_job_match_prompt_template`. | [matcher.py](file:///root/LLM-Projects/Study-Buddy-AI/src/generator/matcher.py) |
| B4 | `matcher.py` / `pdf_loader.py` imported `AppException` — the real class is `CustomException`. | Rename not propagated. | Switched to `CustomException`. | [matcher.py](file:///root/LLM-Projects/Study-Buddy-AI/src/generator/matcher.py), [pdf_loader.py](file:///root/LLM-Projects/Study-Buddy-AI/src/utils/pdf_loader.py) |
| B5 | `from src.common.logger import logging` — the module exports `get_logger`, not `logging`. | Wrong import style. | Switched to `get_logger(__name__)`. | [matcher.py](file:///root/LLM-Projects/Study-Buddy-AI/src/generator/matcher.py), [pdf_loader.py](file:///root/LLM-Projects/Study-Buddy-AI/src/utils/pdf_loader.py) |
| B6 | `matcher.py` used `Optional` without importing it. | Missing import. | Added `from typing import Optional`. | [matcher.py](file:///root/LLM-Projects/Study-Buddy-AI/src/generator/matcher.py) |
| B7 | `matcher.py` called `.generate()` — LangChain chat models expose `.invoke()`. | API misuse. | Switched to `.invoke()` and read `response.content`. | [matcher.py](file:///root/LLM-Projects/Study-Buddy-AI/src/generator/matcher.py) |
| B8 | `matcher.py` passed template variables `job_description` / `candidate_profile`, but the template expects `job_text` / `candidate_text`. | Variable-name mismatch → `KeyError` at render time. | Aligned the call site to the template's real variable names. | [matcher.py](file:///root/LLM-Projects/Study-Buddy-AI/src/generator/matcher.py) |
| B9 | `requirements.txt` was missing `langchain-openai`, `plotly`, `pypdf`. | New modules were added without declaring their dependencies. | Appended the three packages. | [requirements.txt](file:///root/LLM-Projects/Study-Buddy-AI/requirements.txt) |

### P1 — Functional defects

| # | Defect | Root cause | Fix | Files touched |
|---|---|---|---|---|
| B10 | `page_icon="🎧🎧"` duplicated the emoji in the browser tab. | Typo. | Changed to `page_icon="🎧"`. | [application.py](file:///root/LLM-Projects/Study-Buddy-AI/application.py) |
| B11 | **Save Results** produced a download button that vanished on the next Streamlit rerun. | The file path lived only in a local variable, which is discarded on rerun. | Persisted the path in `st.session_state.saved_results_file` and re-rendered the download button from session state. | [application.py](file:///root/LLM-Projects/Study-Buddy-AI/application.py) |
| B12 | **Reset Quiz** did not clear the `job_text_input` widget key, so stale job text reappeared after reset. | Incomplete state cleanup. | `_reset_quiz_state()` now also clears `job_text_input`, `cv_text_input`, `cv_pdf_uploader`, and all `mcq_*` / `fill_blank_*` widget keys. | [application.py](file:///root/LLM-Projects/Study-Buddy-AI/application.py) |
| B13 | Fill-in-the-Blank grading crashed / mis-graded when the user left the answer empty (`None`). | `None.strip()` raised `AttributeError`; the comparison path was fragile. | Added `None`-safe normalization: `(user_ans or "").strip().lower()` plus an explicit non-empty guard. | [helpers.py](file:///root/LLM-Projects/Study-Buddy-AI/src/utils/helpers.py) |
| B14 | `rerun()` contained an unreachable fallback branch. | Dead code left after a Streamlit API bump. | Simplified to a single `st.rerun()` call. | [helpers.py](file:///root/LLM-Projects/Study-Buddy-AI/src/utils/helpers.py) |
| B15 | `_render_candidate_matcher` had no guard for empty job/CV text. | Missing input validation. | Added an early-return guard with an inline warning. | [application.py](file:///root/LLM-Projects/Study-Buddy-AI/application.py) |

### P1 — PDF Resume upload defect (reported after release)

| # | Defect | Root cause | Fix | Files touched |
|---|---|---|---|---|
| B16 | **Upload PDF Resume** accepted the file but always fell through to `Please provide your profile details or resume.` — the green success message never appeared. | `_extract_pdf_text` called `page.extract_text()` **twice** inside one list comprehension (`[p.extract_text() for p in reader.pages if p.extract_text()]`). `pypdf`'s `extract_text()` is **not idempotent**; the second call can return `None`, so `"\n".join([None])` raised `TypeError`, which the bare `except` swallowed and returned `""`. | Deleted the buggy inline implementation and delegated to the single, correct `extract_text_from_pdf` helper (which calls `extract_text()` exactly once per page). | [application.py](file:///root/LLM-Projects/Study-Buddy-AI/application.py) |
| B17 | The real failure reason was invisible — a bare `except` returned `""`, and the only feedback was a generic warning. Scanned/image-only PDFs were indistinguishable from parse crashes. | Silent exception swallowing + no text-layer detection. | The PDF branch now caches the extraction result (and any error) in `st.session_state`, then shows either a green success message with the character count, a red `Failed to read PDF file: …` error, or an actionable warning telling the user to switch **Input Format** to `Plain Text / Bio` for scanned documents. | [application.py](file:///root/LLM-Projects/Study-Buddy-AI/application.py) |
| B18 | Extracted resume text was lost on the next Streamlit rerun (e.g. when clicking **Evaluate Match**). | `UploadedFile.read()` is a one-shot stream; the result was held only in a local variable that is discarded on rerun. | Cached the extracted text under `_pdf_text::{name}::{size}` in session state, and extended `_reset_quiz_state()` to purge all `_pdf_text::*` keys. | [application.py](file:///root/LLM-Projects/Study-Buddy-AI/application.py) |
| B19 | **Regression after B16–B18:** the warning persisted even for a perfectly valid, text-bearing PDF. | Two compounding issues: (1) `UploadedFile` subclasses `io.BytesIO`, so `read()` advances an internal cursor and returns `b""` once exhausted — a rerun could therefore read empty bytes; (2) the failure path cached `""` under a key derived only from `name+size`, **poisoning** the cache so every later rerun kept showing the warning even after re-uploading a good file. | Switched to the cursor-independent `getvalue()`; the cache key now includes Streamlit's per-upload `file_id`; and a failed extraction is **never** written to the cache (only the error is stored), so a subsequent re-upload recovers immediately. | [application.py](file:///root/LLM-Projects/Study-Buddy-AI/application.py) |

### Verification evidence

| Check | Command | Result |
|---|---|---|
| Syntax compile | `python3 -m compileall -q application.py src/` | `COMPILE_OK` (exit 0) |
| Marker cleanup | `grep -rn "cite:" --include="*.py" .` | 0 matches |
| Module imports | dry-import all 15 modules | `FAILURES: 0` |
| Provider dispatch | `get_llm("groq")` / `get_llm("deepseek")` / `get_llm("bogus")` | `ChatGroq` / `ChatOpenAI(base_url=…deepseek…)` / `ValueError` |
| Backward compatibility | instantiate all 4 consumers with no args | all default to Groq |
| Quiz grading edge cases | unanswered MCQ, case-insensitive FillBlank, `None` answer | `False` / `True` / `False` (no crash) |
| App smoke test | Streamlit `/_stcore/health` | HTTP 200 |
| PDF happy path | `extract_text_from_pdf(<valid PDF with text layer>)` | extracted `'DevOps Engineer Python AWS Docker'` (33 chars) |
| PDF failure paths | empty bytes / garbage bytes | both raise `CustomException` (no silent `""`) |
| PDF rerun survival | simulate two Streamlit reruns on a one-shot stream | rerun #1 = rerun #2 = 33 chars (cache hit) |
| Old buggy pattern removed | scan `application.py` for `if p.extract_text()]` | 0 matches |
| Explanation schema field | assert `explanation` in `model_fields` for all 4 schemas | `SCHEMA_OK` (default `""`) |
| Explanation in prompts | assert `'explanation' in tpl.template` for all 4 templates | `PROMPT_OK` |
| Explanation end-to-end | `set_questions` → `evaluate_quiz` → DataFrame | `EXPLANATION_E2E_OK` (correct + incorrect rows both carry text) |
| Explanation backward compat | evaluate a question dict with no `explanation` key | `BACKWARD_COMPAT_OK` (defaults to `""`, no crash) |
| Explanation in CSV | `save_to_csv` then re-read | `CSV_EXPLANATION_OK` (column present) |
| Match report JSON round-trip | `save_match_report_to_json` → `json.load` → `MatchResult(**data)` | `MATCH_JSON_ROUNDTRIP_OK` (all fields preserved) |
| Match report None guard | `save_match_report_to_json(None)` | returns `None` (`MATCH_NONE_GUARD_OK`) |

---

## Phased Optimization Plan

Grouped into 3 phases. "Completion Node" refers to a deliverable boundary that can be independently smoke-tested.

### Phase 1 — P0 / P1 Correctness Fixes (Priority: Immediate)

| Item | Optimization | Priority | Completion Node | Acceptance Standard |
|---|---|---|---|---|
| O1 | Remove MCQ first-option pre-selection + guard unanswered `None` answers. | **P0 Immediate** | Merge-ready [helpers.py](file:///root/LLM-Projects/Study-Buddy-AI/src/utils/helpers.py) + passing AC-1 rule. | `st.radio` uses `index=None`; submitting unanswered MCQ returns `is_correct=False` with empty user_answer; no `TypeError` on compare. |
| O2 | Align FillBlank underscore token between prompt template and generator validator. | **P1 High** | Merge-ready [templates.py](file:///root/LLM-Projects/Study-Buddy-AI/src/prompts/templates.py) and AC-2 rule. | Case-insensitive grep for the misspelled terms returns 0 matches; prompt-generated FillBlank string passes validator on first parse. |
| O3 | Block empty / whitespace topic before LLM calls. | **P1 High** | Merge-ready [application.py](file:///root/LLM-Projects/Study-Buddy-AI/application.py#L125-L137) | `st.warning` appears; `generate_questions()` is not invoked; Groq request count in logs stays 0 for the click. |
| O4 | Wrap the N-question generation loop inside a Streamlit progress spinner. | **P1 High** | Merge-ready [application.py](file:///root/LLM-Projects/Study-Buddy-AI/application.py#L130-L134) | Spinner widget visible throughout the loop; UI never "goes blank" for N=10. |
| O5 | Add server-side validator + length cap + injection-rejection + sanitizer for the job-text ingestion path. | **P1 High** | `SkillExtractor.validate_input` + `sanitize_input` in [job_parser.py](file:///root/LLM-Projects/Study-Buddy-AI/src/parser/job_parser.py#L68-L115) | Unit-style manual run on 4 cases (empty, >MAX, injection, valid) each returns correct (ok, reason); `sanitize_input` idempotent on already-clean input. |

### Phase 2 — UX / Consistency / Observability (Priority: Same Release)

| Item | Optimization | Priority | Completion Node | Acceptance Standard |
|---|---|---|---|---|
| O6 | Correct all visible spelling defects in UI strings and log messages. | **P2 Medium** | Merge-ready [application.py](file:///root/LLM-Projects/Study-Buddy-AI/application.py), [helpers.py](file:///root/LLM-Projects/Study-Buddy-AI/src/utils/helpers.py), [question_generator.py](file:///root/LLM-Projects/Study-Buddy-AI/src/generator/question_generator.py) | grep -inE over the repo excluding .trae returns zero hits for each listed misspelling. |
| O7 | Format score with rounding to 1 decimal and the `%` sign. | **P2 Medium** | Merge-ready [application.py](file:///root/LLM-Projects/Study-Buddy-AI/application.py#L199-L202) | Displayed string matches regex `^Score : \d+(\.\d)?%$`. |
| O8 | Add a sidebar **Reset Quiz** affordance that clears quiz_manager, generated/submitted flags, extracted_skills, and alignment report. | **P2 Medium** | Merge-ready [application.py](file:///root/LLM-Projects/Study-Buddy-AI/application.py#L11-L16) + AC-3 rule | After Reset, UI returns to the landing state with no rendered quiz or results table. |
| O9 | Decouple the job-skill pipeline into an isolated `src/parser/` module with additive-only changes to prompts, schemas, and settings. | **P2 Medium** | New files + module graph review | Existing `QuizManager.generate_questions()` and `QuestionGenerator` public methods untouched; net additions in non-parser core files each ≤ 40 lines. |
| O10 | Make skill-to-question alignment observable via the `target_skill` field plus a runtime report and CSV column. | **P1 High** | End-to-end in [job_parser.py](file:///root/LLM-Projects/Study-Buddy-AI/src/parser/job_parser.py#L254-L280) + [application.py](file:///root/LLM-Projects/Study-Buddy-AI/application.py#L38-L49) | Every job-mode result row carries non-empty target_skill; coverage ratio is printed; CSV carries the column; unmapped items enumerated in expander. |

### Phase 3 — Documentation & Hardening (Priority: Same Release)

| Item | Optimization | Priority | Completion Node | Acceptance Standard |
|---|---|---|---|---|
| O11 | Produce a full English-only README covering Overview, Dependencies, 3 deployment paths, Feature list, Job Parser walkthrough, this audit checklist, the optimization plan, and a Troubleshooting section. | **P2 Medium** | `README.md` at repo root | Each of the 8 required sections present and populated; zero TODO placeholders; commands and paths match the real repository. |
| O12 | Validate the entire repository using `python -m compileall` and dry imports of every new module; run IDE diagnostics to catch lint and typing regressions. | **P1 High** | Clean terminal exit + IDE diagnostics | compileall exit code 0; all parser classes import without error in a fresh interpreter; IDE diagnostics show zero new errors vs baseline. |

All phases (O1-O12) ship as part of the current release.

---

## Troubleshooting Guide

### Application does not start: `ModuleNotFoundError: No module named '...'`
- Ensure you activated the virtual environment or ran `pip install -e .` from the repository root.
- For Docker, confirm the build finished without errors and that `requirements.txt` is present. The builder stage installs in editable mode; any missing file will fail the build stage.
- Re-run `python -m compileall -q .` from the repo root to locate syntax errors.

### Every LLM call returns a 401 / 403 Authentication error
- Verify the key for the **currently selected provider** is set inside `.env` and that `load_dotenv()` executes before the first LLM call (it is called at module import in [application.py:6](file:///root/LLM-Projects/Study-Buddy-AI/application.py#L6)).
  - Groq selected → check `GROQ_API_KEY`.
  - DeepSeek selected → check `DEEPSEEK_API_KEY`.
- In Kubernetes, verify the Secret `groq-api-secret` referenced in the Deployment actually exists and has the correct key names (`GROQ_API_KEY`, and optionally `DEEPSEEK_API_KEY`).
- On host deployments, double-check that shell environment variables (`export GROQ_API_KEY=...`) are NOT empty — the dotenv loader does not override already-set variables, so a stale export can shadow the `.env` value.

### `ValueError: DEEPSEEK_API_KEY is not configured`
- You selected **DeepSeek** in the sidebar but no key is present. Either add `DEEPSEEK_API_KEY=sk-...` to `.env` and restart the app, or switch the sidebar back to **Groq**.
- This guard exists deliberately: without it, the underlying OpenAI-compatible SDK would fall back to `OPENAI_API_KEY` and emit a confusing "Missing credentials" error instead of naming the real variable.

### Rate-limited / 429 Too Many Requests
- Reduce `Number of Questions` (max 10). Job mode performs 1 extraction call + N question calls per generation; total calls scale linearly with N.
- Consider switching to a different model by setting `GROQ_MODEL_NAME` or `DEEPSEEK_MODEL_NAME` in `.env` (both are read by [settings.py](file:///root/LLM-Projects/Study-Buddy-AI/src/config/settings.py)).
- **Switching provider is itself a mitigation:** if one provider is rate-limited, switch the sidebar to the other provider and continue — the two quotas are independent.
- The retry loop already retries parse errors up to `MAX_RETRIES=3`. If you consistently hit the rate ceiling, increase the interval on the client side by adding a small sleep between calls (future enhancement item).

### `CustomException: MCQ / FillBlank / Skill extraction failed after N attempts`
- Root cause 1: The LLM returned a JSON shape that Pydantic rejected (e.g., 5 options instead of 4, wrong underscore count). Retry loop is the first mitigation; if a single topic / posting consistently fails, simplify your topic wording or remove HTML fragments from the pasted posting.
- Root cause 2: FillBlank prompt still produces 5 underscores. The AC-2 fix guarantees the prompt now uses 3; if you see this error on an older cached call, clear browser state with **Reset Quiz** and retry.
- Root cause 3: Skill extraction returns zero items → `ValueError: No skills were extracted`. Posting is too short, too vague, or written in a language other than English (pipeline is English-only). Paste a longer posting with explicit requirements bullets.

### `Invalid job description: Input contains disallowed patterns`
- The conservative injection detector ([job_parser.py:19-27](file:///root/LLM-Projects/Study-Buddy-AI/src/parser/job_parser.py#L19-L27)) triggered. Remove any lines that resemble "ignore previous instructions", "you are a helpful <role>" role-overrides, or `<|assistant|>` / `<|system|>` tokens. If a legitimate posting triggers this, shorten the regex allow-list entries and re-test.

### Docker container exits immediately with `streamlit: command not found`
- This typically means `pip install -e .` in the builder stage failed. Re-run `docker build --no-cache` and look for red text in the builder logs; the most common cause is a corrupted entry in `requirements.txt`.

### Docker HEALTHCHECK returns unhealthy
- Streamlit's `_stcore/health` endpoint only returns 200 once the Tornado event loop is up.
- If your cluster has very slow cold-start resources, increase `--start-period` in the HEALTHCHECK stanza. The 10 s default in the Dockerfile works for hosts with <1 s CPU steal.
- Inside a running container, confirm the Streamlit process is live: `docker exec careercoach-ai curl -s http://localhost:8501/_stcore/health`. Expect `ok`.

### CSV download button does not appear after "Save Results"
- The button is rendered conditionally inside `if saved_file:` where `save_to_csv()` returns the absolute path. If the write fails, an `st.error` is shown instead.
- Ensure the user running the app (UID 1000 inside the container) has write permission on `results/` in the container filesystem. The default container image already `chown`s `/app` to `appuser`.

### After switching modes (Topic → Job or vice versa) the UI still shows old content
- Always click **Reset Quiz** when switching modes. The mode toggle is intentionally stateless so you can compare extraction results with a topic quiz on the same page. Resetting clears the 5 keys used by the job-mode pipeline and the 3 keys used by the generic quiz.
- Switching the **LLM Provider** performs the same reset automatically, so you never carry Groq-generated questions into a DeepSeek session (or vice versa).

---

*Repository structure documentation ends here. For the detailed implementation specification and task queue artifacts used during this release, see `.trae/specs/` (internal to this workspace).*
