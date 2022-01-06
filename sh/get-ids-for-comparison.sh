BASEDIR=$(dirname $0)
ORIGDIR=${PWD}
cd $BASEDIR;

psql schmidt -c "select id from item order by 1;" > ./tmp/new_ids.txt && \
psql schmidt -c "select id from item order by 1;" --host schmidt.cc0kbkym7bvk.us-east-1.rds.amazonaws.com -U talus  > ./tmp/old_ids.txt;
comm -23 new_ids.txt old_ids.txt > ./tmp/ids_in_new_not_old.txt && \
comm -23 old_ids.txt new_ids.txt > ./tmp/ids_in_old_not_new.txt;

cd $ORIGDIR;