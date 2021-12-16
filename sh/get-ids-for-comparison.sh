BASEDIR=$(dirname $0)
ORIGDIR=${PWD}
cd $BASEDIR;

psql schmidt -c "select id from item order by 1;" > ./tmp/new_ids.txt && \
psql schmidt -c "select id from item order by 1;" --host schmidt.cc0kbkym7bvk.us-east-1.rds.amazonaws.com -U talus  > ./tmp/old_ids.txt;

cd $ORIGDIR;