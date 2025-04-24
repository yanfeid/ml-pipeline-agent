pipeline {
    agent none

    options {
        timeout(time: 1, unit: 'HOURS')
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '3'))
    }

    environment {
        IMAGE_NAME = 'dockerhub.paypalcorp.com/insight/rmr-agent'
    }

    stages {
        stage('Pull Code') {
            agent any
            steps {
                git branch: 'main', credentialsId: 'jenkins-pipeline-github-access', url: 'git@github.paypal.com:FOCUS-ML/rmr_agent.git'
                echo 'pull success'
            }
        }
        
        stage('Test') {
            agent {
                docker {
                    image 'python:3.12.6'
                }
            }
            steps {
                // git branch: 'main', url: 'git@github.paypal.com:FOCUS-ML/rmr_agent.git' 
                sh 'pip install -r requirements.txt'
                sh 'pytest'
            }
        }

        stage('Build Docker Image and Push') {
            agent any
            environment {
                IMAGE_TAG = readFile '.version'
            }
            steps {
                sh 'pwd'
                sh 'ls'
                sh 'docker image build -t ${IMAGE_NAME}:${IMAGE_TAG} -f Dockerfile .'
                sh 'docker push ${IMAGE_NAME}:${IMAGE_TAG}'
                echo 'image success'
            }
        }
    }

    post {
        failure {
            mail to: 'matjacobs@paypal.com',
                 subject: "RMR Agent Jenkins pipeline failed: ${currentBuild.fullDisplayName}",
                 body: "The RMR Agent Jenkins pipeline job '${currentBuild.fullDisplayName}' has failed. Please investigate and take appropriate action. \n\n" + "For more information, please see the console output: ${env.BUILD_URL}console"
        }
    }
}
