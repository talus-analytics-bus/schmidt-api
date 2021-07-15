#!/bin/bash
##
# Update an RDS database using a local database.
##

programname=$0

function usage {
    echo "usage: $programname [username] [dblive] [dblocal]"
    echo "  username    your local pgsql server username"
    echo "  dblive      the name of the database on the Schmidt server you are updating"
    echo "  dblocal     the name of the database on your local server with which you are updating"
    exit 1
}

now=$(date);
username=${1?Provide your local pgsql server username in first argument};
dblive=${2?Provide the name of the database on the Schmidt server you are updating in second argument};
dblocal=${3?Provide the name of the database on your local server with which you are updating in third argument};

# dump local database
echo "Current date: $now";
mkdir sh; cd sh; mkdir backup-local; cd backup-local;
pg_dump \
--host "localhost" \
--port "5432" \
--username $1 \
--dbname $3 --verbose \
-F d -f "$now-local" && \
cd ../..;

# dump prod
cd sh; mkdir backup-preview; cd backup-preview;
pg_dump \
--host "schmidt.cc0kbkym7bvk.us-east-1.rds.amazonaws.com" \
--port "5432" \
--username "talus" \
--dbname $2 --verbose \
-F d -f "$now-preview" && \
cd ../..;

# drop prod
psql \
--host "schmidt.cc0kbkym7bvk.us-east-1.rds.amazonaws.com" \
--port "5432" \
--username "talus" \
--dbname $2 \
-c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" && \

# restore prod from local dump
cd sh/backup-local;
pg_restore \
--host "schmidt.cc0kbkym7bvk.us-east-1.rds.amazonaws.com" \
--port "5432" \
--username "talus" \
--dbname $2 --verbose \
--format=d --verbose "$now-local";
cd ../.. && \

# restart API server
aws elasticbeanstalk restart-app-server --environment-name schmidt-api-preview \
--region us-east-1 && \

# invalidate frontend caches
# prod and preview
aws cloudfront create-invalidation \
--distribution-id E3KCF50FO8RLIK \
--paths "/*" && \
aws cloudfront create-invalidation \
--distribution-id E6J9FWVEWFDBG \
--paths "/*";