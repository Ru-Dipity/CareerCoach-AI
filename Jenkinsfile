pipeline {
    agent any
    environment {
        DOCKER_HUB_REPO = "ruhuang1107/careercoach-ai"
        DOCKER_HUB_CREDENTIALS_ID = "dockerhub-token"
        IMAGE_TAG = "v${BUILD_NUMBER}"
    }
    stages {
        stage('Pipeline Orchestrator') {
            steps {
                script {
                    echo 'Checking out source code from GitHub...'
                    checkout scmGit(
                        branches: [[name: '*/main']], 
                        extensions: [], 
                        userRemoteConfigs: [[credentialsId: 'github-token', url: 'https://github.com/Ru-Dipity/StudyBuddy.git']]
                    )

                    // 1. 获取最新提交信息
                    def lastCommit = sh(script: 'git log -1 --pretty=%B', returnStdout: true).trim()
                    echo "=========================================="
                    echo "Latest commit message: ${lastCommit}"
                    echo "=========================================="

                    // 2. 拦截检查：如果是自动回写提交，直接在这里 return 退出当前构建，后续代码全部不执行！
                    if (lastCommit.contains('[skip ci]') || lastCommit.contains('chore(ci): Update image tag')) {
                        echo ">>> Intercepted automated commit. Aborting execution immediately to prevent loop! <<<"
                        currentBuild.result = 'SUCCESS'
                        return // 直接在这里退出，后面的所有步骤统统不跑！
                    }

                    // 3. 真正的 CI/CD 流程（只有正常业务提交才会走到这里）
                    stage('Build Docker Image') {
                        echo "Building Docker container image: ${DOCKER_HUB_REPO}:${IMAGE_TAG}..."
                        dockerImage = docker.build("${DOCKER_HUB_REPO}:${IMAGE_TAG}")
                    }

                    stage('Push Image to DockerHub') {
                        echo 'Pushing Docker image to DockerHub registry...'
                        docker.withRegistry('https://registry.hub.docker.com', "${DOCKER_HUB_CREDENTIALS_ID}") {
                            dockerImage.push("${IMAGE_TAG}")
                        }
                    }

                    stage('Update Deployment YAML with New Tag') {
                        echo "Updating manifests/deployment.yaml with new image tag: ${IMAGE_TAG}"
                        sh """
                        sed -i 's|image: ruhuang1107/careercoach-ai:.*|image: ruhuang1107/careercoach-ai:${IMAGE_TAG}|' manifests/deployment.yaml
                        """
                    }

                    stage('Commit Updated YAML') {
                        echo 'Committing and pushing updated deployment manifests back to repository...'
                        withCredentials([usernamePassword(credentialsId: 'github-token', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_PASS')]) {
                            sh '''
                            git config user.name "Ru-Dipity"
                            git config user.email "ruhuang1107@gmail.com"
                            git add manifests/deployment.yaml
                            git commit -m "chore(ci): Update image tag to ${IMAGE_TAG} [skip ci]" || echo "No changes to commit"
                            git pull --rebase https://${GIT_USER}:${GIT_PASS}@github.com/Ru-Dipity/StudyBuddy.git main
                            git push https://${GIT_USER}:${GIT_PASS}@github.com/Ru-Dipity/StudyBuddy.git HEAD:main
                            '''
                        }
                    }

                    stage('Install Kubectl & ArgoCD CLI Setup') {
                        echo 'Installing Kubectl and ArgoCD CLI binaries...'
                        sh '''
                        curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
                        chmod +x kubectl
                        mv kubectl /usr/local/bin/kubectl
                        curl -sSL -o /usr/local/bin/argocd https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
                        chmod +x /usr/local/bin/argocd
                        '''
                    }

                    stage('Apply Kubernetes & Sync App with ArgoCD') {
                        echo 'Triggering ArgoCD application synchronization...'
                        kubeconfig(credentialsId: 'kubeconfig', serverUrl: 'https://192.168.49.2:8443') {
                            sh '''
                            argocd login 35.224.152.0:31429 --username admin --password $(kubectl get secret -n argocd argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d) --insecure
                            argocd app sync study
                            '''
                        }
                    }
                }
            }
        }
    }
}