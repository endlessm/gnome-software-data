// -*- mode: Groovy; -*-
// vim: filetype=groovy

// Build and publish AppStream data.

pipeline {
    agent {
        dockerfile {
            filename 'Dockerfile'
        }
    }

    options {
        ansiColor('xterm')
    }

    stages {
        stage('Build') {
            steps {
                sh 'make'
            }
        }

        stage('Validate') {
            steps {
                sh 'make check'
            }
        }

        stage('Publish') {
            steps {
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding',
                                  credentialsId: 'iam-user-jenkins-jobs',
                                  accessKeyVariable: 'AWS_ACCESS_KEY_ID',
                                  secretKeyVariable: 'AWS_SECRET_ACCESS_KEY']]) {
                    sh "./sync-s3.sh ${params.DRY_RUN == "true" ? "--dry-run" : ""}"
                }
            }
        }
    }

    post {
        always {
            buildDescription("DRY_RUN=${params.DRY_RUN}")
        }

        failure {
            sendEmail(
                recipients: 'os@endlessos.org,$DEFAULT_RECIPIENTS',
                replyTo: 'os@endlessos.org',
            )
        }
    }
}
