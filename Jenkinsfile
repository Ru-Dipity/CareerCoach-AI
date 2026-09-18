pipeline {
    agent any
    environment {
        DOCKER_HUB_REPO = "ruhuang1107/careercoach-ai"
        DOCKER_HUB_CREDENTIALS_ID = "CareerCoach-Dockerhub"
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
                        userRemoteConfigs: [[credentialsId: 'github-token', url: 'https://github.com/Ru-Dipity/CareerCoach-AI.git']]
                    )

                    // 1. Get the latest commit message
                    def lastCommit = sh(script: 'git log -1 --pretty=%B', returnStdout: true).trim()
                    echo "=========================================="
                    echo "Latest commit message: ${lastCommit}"
                    echo "=========================================="

                    // 2. Intercept check: prevent the pipeline from self-triggering a loop
                    if (lastCommit.contains('[skip ci]') || lastCommit.contains('chore(ci): Update image tag')) {
                        echo ">>> Intercepted automated commit. Aborting execution immediately to prevent loop! <<<"
                        currentBuild.result = 'SUCCESS'
                        return 
                    }

                    // 3. Build the Docker image
                    stage('Build Docker Image') {
                        echo "Building Docker container image: ${DOCKER_HUB_REPO}:${IMAGE_TAG}..."
                        dockerImage = docker.build("${DOCKER_HUB_REPO}:${IMAGE_TAG}")
                    }

                    // 4. Push the image to Docker Hub
                    stage('Push Image to DockerHub') {
                        echo 'Pushing Docker image to DockerHub registry...'
                        docker.withRegistry('https://registry.hub.docker.com', "${DOCKER_HUB_CREDENTIALS_ID}") {
                            dockerImage.push("${IMAGE_TAG}")
                        }
                    }

                    // 5. Update the image tag in local manifests
                    stage('Update Deployment YAML with New Tag') {
                        echo "Updating manifests/deployment.yaml with new image tag: ${IMAGE_TAG}"
                        sh """
                        sed -i 's|image: ruhuang1107/careercoach-ai:.*|image: ruhuang1107/careercoach-ai:${IMAGE_TAG}|' manifests/deployment.yaml
                        """
                    }

                    // 6. Commit updated manifests back to GitHub (triggers Argo CD auto-deploy)
                    stage('Commit Updated YAML') {
                        echo 'Committing and pushing updated deployment manifests back to repository...'
                        withCredentials([usernamePassword(credentialsId: 'github-token', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_PASS')]) {
                            sh '''
                            git config user.name "Ru-Dipity"
                            git config user.email "ruhuang1107@gmail.com"
                            git add manifests/deployment.yaml
                            git commit -m "chore(ci): Update image tag to ${IMAGE_TAG} [skip ci]" || echo "No changes to commit"
                            git pull --rebase https://${GIT_USER}:${GIT_PASS}@github.com/Ru-Dipity/CareerCoach-AI.git main
                            git push https://${GIT_USER}:${GIT_PASS}@github.com/Ru-Dipity/CareerCoach-AI.git HEAD:main
                            '''
                        }
                    }
                }
            }
        }
    }
}