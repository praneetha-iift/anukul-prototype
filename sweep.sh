#!/bin/bash
# usage: sweep.sh <scenario> <max_steps or ''> <outdir> ctl1 ctl2 ...   (runs 2 at a time)
cd /home/claude/ext/project1-boptest && . /home/claude/anukul/.venv/bin/activate
export LD_LIBRARY_PATH=/home/claude/anukul/libs/ex/usr/lib/x86_64-linux-gnu
scen=$1; ms=$2; out=$3; shift 3; mkdir -p $out
for c in "$@"; do
  tag=$(echo $c | tr ':,' '__')
  ( MAX_STEPS=$ms python /home/claude/anukul/boptest_local/runner.py $scen "$c" $out/${scen}__$tag.json 2>/dev/null | grep -v INFO > $out/${scen}__$tag.txt ) &
  while [ $(jobs -r | wc -l) -ge 2 ]; do sleep 2; done
done
wait
