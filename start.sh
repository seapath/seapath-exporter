#!/bin/bash
python /app/insatomcat_exporter.py &
/app/ha_cluster_exporter &
wait -n
exit $?
