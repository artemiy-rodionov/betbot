#!/usr/bin/env bash
# Run the test suite with pytest via uv.
# Extra args are passed through to pytest, e.g.:
#   ./run_tests.sh -k pending -v

set -o pipefail
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

exec uv run --group dev pytest "$@"
