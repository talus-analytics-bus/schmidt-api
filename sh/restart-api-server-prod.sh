#!/bin/bash
##
# Restart production API server on Elastic Beanstalk
##

echo Restarting production API server...;
aws elasticbeanstalk restart-app-server \
--environment-name schmidt-api-prod \
--region us-east-1 && \
echo Restarted.