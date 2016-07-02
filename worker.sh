#!/bin/sh

set -e
set -x

while true; do
  ./osmtracker.py csets-check-bounds
  ./osmtracker.py csets-analyze
#  ./osmtracker.py -lDEBUG csets-check-bounds
#  ./osmtracker.py -lDEBUG csets-analyze
  sleep 15
done
