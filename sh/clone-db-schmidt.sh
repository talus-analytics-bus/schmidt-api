#!/bin/bash
##
# Clone a AWS RDS database locally for the Health Security Net (aka. 
# Schmidt) project
#
# Arguments: [username] [aws_db_name] [local_db_name]
##

bold=$(tput bold)
normal=$(tput sgr0)
username=${1?Please provide your local pgsql server username as first argument};
dblive=${2?Please provide the name of the AWS RDS Schmidt database you are cloning as second argument};
dblocal=${3?Please provide the name of the local pgsql server database you are cloning to as third argument};

printf "\n\n${bold}Cloning AWS RDS database locally...${normal}";
now=$(date) && \
printf "\nCurrent date: $now\n" &&

# create local
printf "\n\n${bold}Creating local database, if does not exist...\n${normal}";
createdb $3;

# backup local
mkdir sh; cd sh && mkdir backup-local; cd backup-local && \
pg_dump \
--no-acl \
--no-owner \
--host "localhost" \
--port "5432" \
--username $username \
--dbname $dblocal \
-F d -f "$dblocal-local-$now" --verbose && \
cd ../.. && \

# backup aws
printf "${bold}\n\nDumping AWS database...\n${normal}" && \
mkdir sh; cd sh && mkdir backup-dev; cd backup-dev && \
pg_dump \
--no-acl \
--no-owner \
--host "schmidt.cc0kbkym7bvk.us-east-1.rds.amazonaws.com" \
--port "5432" \
--username "talus" \
--dbname $dblive \
-F d -f "$dblive-dev-$now" --verbose;
cd ../.. && \

# drop local
printf "${bold}\n\nDropping local database data...\n${normal}" && \
psql \
--host "localhost" \
--port "5432" \
--username $username \
--dbname $dblocal \
-c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" \

# restore local from dev dump
printf "${bold}\n\nRestoring AWS database to local database...\n${normal}" && \
cd sh/backup-dev && \
pg_restore --host "localhost" \
--port "5432" \
--username $username \
--dbname $dblocal \
--format=d \
--verbose \
"$dblive-dev-$now";

# announce done
printf "${bold}\n\nOperation completed successfully.\n\n${normal}";
