#!/bin/bash

dumpdir="/var/tmp/dumps/postgres/dumps"
statusdir="/var/tmp/dumps/postgres/status"

STATE_OK=0
STATE_WARNING=1
STATE_CRITICAL=2
STATE_UNKNOWN=3

process_state_infos()
{
    statusfile=$1
    human=$(basename "$statusfile")

    unset DUMP_SIZE SECONDS_ELAPSED DATE_FINISHED PRETTY_DATE DUMP_RCODE

    # Note how each `echo` is prefixed with the numerical status code.
    # We do this in order to be able to easily sort the output afterwards.

    if bash -n "$statusfile"
    then
        source "$statusfile"
        if \
            [[ ! -v DUMP_SIZE ]] ||
            [[ ! -v SECONDS_ELAPSED ]] ||
            [[ ! -v DATE_FINISHED ]] ||
            [[ ! -v PRETTY_DATE ]] ||
            [[ ! -v DUMP_RCODE ]]
        then
            echo "${STATE_UNKNOWN}UNKNOWN - $human: Incomplete status file"
            return $STATE_UNKNOWN
        fi

        last_backup=$(echo $(date +%s) - $DATE_FINISHED | bc)

        if (( $DUMP_RCODE != 0 ))
        then
            echo "${STATE_CRITICAL}CRITICAL - $human: pg_dump exited with non-zero return code after $SECONDS_ELAPSED seconds, finished $PRETTY_DATE"
            return $STATE_CRITICAL
        fi

        if (( $last_backup > 86400 ))
        then
            echo "${STATE_CRITICAL}CRITICAL - $human: last backup older than 24h"
            return $STATE_CRITICAL
        fi

        # DUMP_SIZE is a string...
        if [[ $DUMP_SIZE = 0 ]]
        then
            echo "${STATE_WARNING}WARNING - $human: dump is empty"
            return $STATE_WARNING
        fi

        echo "${STATE_OK}OK - $human: dumped $DUMP_SIZE (gzipped) in $SECONDS_ELAPSED seconds, finished $PRETTY_DATE"
        return $STATE_OK
    else
        echo "${STATE_UNKNOWN}UNKNOWN - $human: cannot read status file"
        return $STATE_UNKNOWN
    fi
}

# Have a look at each status file. `process_state_infos` will take care of that.
# We collect its output and return code. Finally, we exit with the maximum return
# code and print a sorted list.

max_ret=-1
collected=$(mktemp)
trap 'rm -f "$collected"' EXIT
shopt -s nullglob
for i in "$statusdir"/*
do
    process_state_infos "$i" >>"$collected"
    ret=$?
    (( ret > max_ret )) && max_ret=$ret
done
if (( max_ret == -1 ))
then
    echo "UNKNOWN - No status files found"
    exit $STATE_UNKNOWN
else
    sort -ro "$collected" "$collected"
    sed 's/^.//' "$collected"
    exit $max_ret
fi
