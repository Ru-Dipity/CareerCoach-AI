# CareerCoach AI

A lightweight Streamlit app that turns topics or job descriptions into short practice quizzes and a skill-match report.

This README is a concise guide for junior–mid engineers: quick setup, how it works, and next steps.

---

**Quick highlights**
- Generate multiple-choice or fill-in-the-blank quizzes from a topic or a pasted job posting.
- Pluggable LLM providers: `Groq` or `DeepSeek` (selectable in the sidebar).
- Candidate match report with extracted skills, gap analysis, and downloadable JSON/CSV.

**Screenshots**
- Quiz UI: public/images/quiz_ui.png
- Quiz results: public/images/quiz_results.png
- Candidate match report: public/images/candidate_match.png
- Skill analytics: public/images/skill_analytics.png

---

## Quick Start (local)

Prerequisites: Python 3.10+, Git.

1) Create a virtual environment and install:

```bash
cd CareerCoach-AI
python -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

2) Add provider keys to `.env` (do NOT commit this file):

```dotenv
# Groq (optional)
GROQ_API_KEY=gsk_...

## CareerCoach AI — Platform / DevOps Overview

![CI status](https://img.shields.io/badge/CI-Jenkins-blue) ![CD status](https://img.shields.io/badge/CD-ArgoCD-red) ![Docker](https://img.shields.io/badge/image-ruhuang1107%2Fcareercoach--ai-lightgrey)

This project is a Streamlit application used here as a demo workload to showcase a production-like CI/CD pipeline for DevOps / Platform Engineering interviews. The repo contains:

- the application code (`application.py`, `src/`)
- a Dockerfile for multi-stage builds
- Kubernetes manifests in `manifests/` (Deployment, Service)
- a `Jenkinsfile` that builds the image, pushes to Docker Hub and commits updated manifests back to the repo (write-back)
- an example Argo CD setup to continuously deploy the manifests using GitOps

Goals for this README:

- Present a clean CI/CD architecture (Jenkins CI -> Docker Registry -> Git manifest update -> Argo CD GitOps CD)
- Provide reproducible, production-minded setup steps for Jenkins and Argo CD
- Call out platform engineering best practices (least privilege, immutable tags, secrets management, self-heal)

---

### Architecture (CI/CD workflow)

```mermaid
flowchart LR
  subgraph CI
    J[Jenkins CI]
  end
  subgraph Registry
    D[Docker Hub: ruhuang1107/careercoach-ai]
  end
  subgraph Git
    R[Git (manifests/)]
  end
  subgraph CD
    A[Argo CD (GitOps)]
  end

  J -->|build image:ruhuang1107/careercoach-ai:v{BUILD}| D
  J -->|update manifests/deployment.yaml (image tag)| R
  R -->|push commit| gitPush[Git Push]
  A -->|poll / webhook| R
  A -->|sync| K[Kubernetes Cluster]

  click J "Jenkinsfile" "Jenkins pipeline (build, push, commit)"
  click R "manifests/deployment.yaml" "K8s manifests stored in repo"
```

Key points:
- Jenkins performs the build and pushes an immutable tag (e.g. `v9`), then commits the updated manifest back to the Git repository. The commit includes `[skip ci]` in its message to avoid loop triggers.
- Argo CD watches the Git repo and performs declarative syncs to the cluster — this is the single source of truth.
- CI and CD are intentionally decoupled: CI produces artifacts and updates Git; CD pulls from Git and deploys.

---

## Production-like setup: Jenkins (CI)

Overview: Jenkins builds a multi-stage Docker image, tags it immutably (use build number or short SHA), pushes to Docker Hub (`ruhuang1107/careercoach-ai`), updates `manifests/deployment.yaml` with the new tag, and commits the change back to Git.

Recommended Jenkins configuration (high level):

- Use a dedicated service account and credentials for Git and Docker Hub (do not store raw kubeconfigs in CI).
- Store credentials in Jenkins Credentials store with clearly scoped IDs (e.g. `github-token`, `dockerhub-token`).
- Use pipeline-as-code: `Jenkinsfile` lives next to `manifests/` and `application.py`.

Example pipeline steps (conceptual):

```groovy
// checkout
checkout scm

// build
dockerImage = docker.build("ruhuang1107/careercoach-ai:${IMAGE_TAG}")

// push
docker.withRegistry('https://registry.hub.docker.com', 'dockerhub-credentials') {
  dockerImage.push()
}

// update manifest, commit with [skip ci]
sh "sed -i 's|image: .*|image: ruhuang1107/careercoach-ai:${IMAGE_TAG}|' manifests/deployment.yaml"
withCredentials([usernamePassword(credentialsId: 'github-token', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_PASS')]) {
  sh '''
  git config user.email "ci-bot@example.com"
  git config user.name "ci-bot"
  git add manifests/deployment.yaml
  git commit -m "chore(ci): update image tag to ${IMAGE_TAG} [skip ci]" || echo "no changes"
  git push https://${GIT_USER}:${GIT_PASS}@github.com/your-org/your-repo.git HEAD:main
'''
}
```

Best-practice notes for Jenkins:

- Use immutable tags (do not deploy `latest` to production).
- Avoid giving CI cluster-admin rights—CI should not directly apply manifests to the cluster. Instead, update Git and let Argo CD reconcile.
- Sign or verify images where possible, and enable image scanning in your registry.

---

## Production-like setup: Argo CD (GitOps CD)

Overview: Argo CD is the continuous delivery agent. It watches the manifests repository and performs declarative syncs to the target Kubernetes cluster.

Install (example):

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
# Optionally expose argocd-server via ingress or NodePort for UI access
```

Connect Argo CD to the repo (UI or CLI):

```bash
argocd repo add https://github.com/your-org/your-repo.git --username <git-user> --password <git-token>
argocd app create careercoach-app \ 
  --repo https://github.com/your-org/your-repo.git \ 
  --path manifests \ 
  --dest-server https://kubernetes.default.svc \ 
  --dest-namespace default \ 
  --sync-policy automated --self-heal
```

Best-practice notes for Argo CD:

- Use a minimal service account with only `get/list/watch/patch` on the namespaces and resources Argo CD needs.
- Enable `selfHeal` / `automated` sync to allow GitOps automatic reconciliation.
- Do not store static kubeconfigs inside Jenkins; Argo CD should manage cluster access via its own controlled credentials.

---

## Security & Platform Engineering Highlights

- Least Privilege: CI (Jenkins) holds only Git and Registry credentials. CD (Argo CD) holds cluster credentials with minimal RBAC, not the CI system.
- No kubeconfig in CI: Do not check kubeconfig into Git or pass it around in plaintext. If CI needs to talk to Kubernetes, prefer short-lived service accounts or use the GitOps pattern instead.
- Immutable Image Tags: Use build numbers, semver, or commit SHAs as image tags. Avoid `latest` for production deployments.
- Manifest Write-back with Safety: If CI updates manifests, include `[skip ci]` in commit messages and implement intercept checks in the pipeline to prevent infinite loops.
- Secrets: Use a secret manager (HashiCorp Vault, SealedSecrets, ExternalSecrets) — avoid plaintext secrets in Git.
- Observability: Add readiness/liveness probes, resource limits, Prometheus metrics instrumentation, and dashboards (Grafana) for platform visibility.

---

## Quick commands and examples

Build and push an immutable tag:

```bash
IMAGE_TAG=v$(date +%Y%m%d%H%M)-${BUILD_NUMBER:-local}
docker build -t ruhuang1107/careercoach-ai:${IMAGE_TAG} .
docker push ruhuang1107/careercoach-ai:${IMAGE_TAG}
```

Update manifests and push (CI step):

```bash
sed -i 's|image: .*|image: ruhuang1107/careercoach-ai:'"${IMAGE_TAG}"'|' manifests/deployment.yaml
git add manifests/deployment.yaml
git commit -m "chore(ci): update image ${IMAGE_TAG} [skip ci]"
git push
```

Deploy (Argo CD will pick up the change automatically if configured):

```bash
argocd app sync careercoach-app
argocd app get careercoach-app
```

---

## Appendix: Checklist for interview demos

- [ ] CI builds image and pushes immutable tag
- [ ] CI commits manifest update and includes `[skip ci]`
- [ ] Argo CD watches Git and syncs automatically (self-heal)
- [ ] Secrets stored outside Git (Vault/ExternalSecrets/SealedSecrets)
- [ ] Minimal RBAC for Argo CD and CI service accounts
- [ ] Readiness/liveness probes and health checks defined in manifests
- [ ] Monitoring + dashboards (Prometheus + Grafana) hooked to cluster

---

If you'd like, I can:

- convert the architecture diagram into a larger PNG and embed the screenshots inline;
- update `manifests/deployment.yaml` to use a templated image tag and add health probes;
- scaffold a `terraform/` starter that provisions a cluster, registry, and Argo CD installation.

Navigate to: Manage Jenkins → Plugins
Install:
Docker
Docker Pipeline
Kubernetes

Restart Jenkins

Install  Pip inside Jenkins Container


5. GitHub Integration with Jenkins
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


 Create a New Pipeline Job in Jenkins
Go to Jenkins Dashboard → New Item
Enter Name: gitops
Select Pipeline
Scroll to the Pipeline section:
Select Pipeline from SCM
Choose Git
Repository URL: Your GitHub repo link
Credentials: Select the github-token credential
Branch: main

 Create DockerHub Repository
 Go to https://hub.docker.com
Create a new repository, 
 Generate DockerHub Access Token
Go to DockerHub Account → Account Settings → Security → New Access Token
Name it appropriately and give it Read/Write permission
Copy the generated token

 Add DockerHub Credentials to Jenkins
Go to Jenkins → Manage Jenkins → Credentials → Global → Add Credentials
Username: DockerHub username 
Password: The DockerHub token
ID: gitops-dockerhub
Description: DockerHub Access Token

Install and Configure ArgoCD
kubectl create ns argocd

Install ArgoCD
Apply the ArgoCD installation manifest from GitHub:

kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

Validate ArgoCD Components
Check all resources inside the argocd namespace:

kubectl get all -n argocd

Step 5: Check ArgoCD Service Type
kubectl get svc -n argocd
You’ll notice that argocd-server is of type ClusterIP, which is only accessible within the cluster.

We need to change it to NodePort to access the UI externally.

🔧 Step 6: Change ClusterIP to NodePort

Step 8: Get ArgoCD Admin Password
Open another terminal and run:

kubectl get secret -n argocd argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
Username: admin
Password: (copy from above)

Connect GitHub Repository to ArgoCD
Open ArgoCD UI → Go to Settings → Repositories → Connect Repo via HTTPS.

Fill in details:

Type: git
Name: anything you want
Project: default
Repo URL: https://github.com/。。。
Username & Password: Provide GitHub username and token (optional but recommended)
Click Connect.

You should see a success message confirming the GitHub repo is connected to ArgoCD.

kubectl create secret generic groq-api-secret \
  --from-literal=GROQ_API_KEY="" \
  -n argocd


  Create a New Application in ArgoCD
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

Add Webhook in GitHub Repository

Go to your GitHub repo → Settings → Webhooks → Add webhook.
Fill in the details:
Payload URL:
http://34.72.5.170:8080/github-webhook/
(Replace with your Jenkins URL)
Content type: application/json
Secret: (Not necessary, leave blank)
Enable SSL verification: Enable if using HTTPS
Under Which events would you like to trigger this webhook?
Tick Just the push event
(This means the pipeline triggers on every push)
Click Add webhook.


Configure Jenkins to Receive Webhook
Open Jenkins → Go to your Pipeline job → Click Configure.
Scroll down to Build Triggers.
Tick GitHub hook trigger for GITScm polling.
Click Apply and Save.
Your webhook trigger is now configured.



est the Webhook Trigger
Open VS Code.
Make a slight change in the Jenkinsfile (e.g., add or modify an echo statement for demonstration).
Commit and push the code to GitHub.
Go to Jenkins Dashboard.
You should see your Jenkins pipeline automatically triggered and start running.


