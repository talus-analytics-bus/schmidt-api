#!/bin/bash
##
# Create backup of all files in Health Security Net S3 storage bucket.
##
now=$(date)
cd sh; 
mkdir backup-s3-storage; 
cd backup-s3-storage;
mkdir "$now";
cd "$now";
echo Backing up Health Security Net S3 storage...;
aws s3 sync s3://schmidt-storage . && \
echo Backup completed.