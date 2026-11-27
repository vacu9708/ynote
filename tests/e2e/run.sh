#!/usr/bin/env bash
# Run the end-to-end tests: build the package, install it in a clean Ubuntu
# with a virtual desktop, and drive the installed Ynote there.
#
#     tests/e2e/run.sh                                  # Ubuntu 26.04
#     tests/e2e/run.sh 22.04                            # another release
#     tests/e2e/run.sh all                              # every release
#     tests/e2e/run.sh 26.04 tests/e2e/test_tables.py -k L21
#
# The tests are shared evenly among containers that run at once (JOBS, by
# default one per processor); naming test files or other pytest arguments
# runs them in one. The images come from tests/e2e/Dockerfile (see
# its header). The output of each run, and screenshots and app logs of
# failed tests, are left in tests/e2e/out/.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RELEASE="${1:-26.04}"
if [ $# -gt 0 ]; then shift; fi
case "$RELEASE" in
    all) RELEASES=(26.04 22.04) ;;
    *) RELEASES=("$RELEASE") ;;
esac
JOBS="${JOBS:-$(nproc)}"

"$ROOT/build-deb.sh" >/dev/null
OUT="$ROOT/tests/e2e/out"
rm -rf "$OUT" && mkdir -p "$OUT"

run() {  # release, log name, shard, pytest arguments...
    local release="$1" log="$2" shard="$3"
    shift 3
    docker run --rm --init -v "$ROOT":/src:ro -v "$OUT":/out \
        -e YNOTE_E2E=1 -e SHARD="$shard" "ynote-e2e:$release" \
        /src/tests/e2e/in_container.sh -W ignore::DeprecationWarning "$@" \
        > "$OUT/$log.txt" 2>&1
}

status=0
if [ $# -gt 0 ]; then
    for release in "${RELEASES[@]}"; do
        echo "==> Ubuntu $release"
        run "$release" "$release" "" "$@" || status=1
        grep -E '^(FAILED|ERROR)|passed|failed|error' "$OUT/$release.txt" || true
    done
    exit $status
fi

pids=()
names=()
SHARDS=$(( JOBS / ${#RELEASES[@]} > 0 ? JOBS / ${#RELEASES[@]} : 1 ))
for release in "${RELEASES[@]}"; do
    for shard in $(seq 0 $((SHARDS - 1))); do
        name="$release-$((shard + 1))of$SHARDS"
        run "$release" "$name" "$shard/$SHARDS" &
        pids+=($!)
        names+=("$name")
    done
done
for i in "${!pids[@]}"; do
    if ! wait "${pids[$i]}"; then status=1; fi
done
for release in "${RELEASES[@]}"; do
    passed=0; failed=0
    for log in "$OUT/$release-"*of*.txt; do
        line="$(grep -E '[0-9]+ (passed|failed)' "$log" | tail -1)"
        passed=$((passed + $(echo "$line" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' || echo 0)))
        failed=$((failed + $(echo "$line" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+' || echo 0)))
        grep -E '^(FAILED|ERROR)' "$log" || true
    done
    echo "Ubuntu $release: $passed passed, $failed failed"
    [ "$failed" -eq 0 ] || status=1
done
exit $status
