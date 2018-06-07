#!/bin/bash

dumpdir="/var/tmp/dumps/postgres/dumps"
statusdir="/var/tmp/dumps/postgres/status"

write_state_info()
{
    db=$1

    SECONDS_ELAPSED=$(echo $END_TIME - $START_TIME | bc)
    PRETTY_DATE=$(date)
    DUMP_SIZE=$(du -h "$dumpdir"/"$db".sql.gz | cut -f1)

    cat >"$statusdir"/"$db" <<-EOF
    DUMP_SIZE="$DUMP_SIZE"
    SECONDS_ELAPSED="$SECONDS_ELAPSED"
    DATE_FINISHED="$END_TIME"
    PRETTY_DATE="$PRETTY_DATE"
    DUMP_RCODE="$DUMP_RCODE"
EOF
}

# Dump globals, i.e. table spaces and roles.
START_TIME=$(date "+%s")
sudo -u postgres pg_dumpall --globals-only 2>/dev/null | gzip --quiet --rsyncable >"$dumpdir/globals.sql.gz"
DUMP_RCODE=${PIPESTATUS[0]}
END_TIME=$(date "+%s")
write_state_info globals

# Dump each database, including CREATE statements. Each file will be
# prefixed with "db_" to avoid clashes with the schema dump.
sudo -u postgres psql -lqt 2>/dev/null |
awk -F'|' '{ gsub(/ /, "", $0); if ($1 != "" && $1 != "template0") { print $1 } }' |
while read db
do
    START_TIME=$(date "+%s")
    sudo -u postgres pg_dump -C "$db" 2>/dev/null | gzip --quiet --rsyncable >"$dumpdir"/db_"$db".sql.gz
    DUMP_RCODE=${PIPESTATUS[0]}
    END_TIME=$(date "+%s")
    write_state_info db_"$db"
done
