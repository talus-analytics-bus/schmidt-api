#!/bin/bash
# Restart preview API server on Elastic Beanstalk
echo Restarting preview API server...;
aws elasticbeanstalk restart-app-server \
--environment-name schmidt-api-preview \
--region us-east-1 && \
echo Restarted.