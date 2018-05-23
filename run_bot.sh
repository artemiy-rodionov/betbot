#!/usr/bin/env bash

if [ "$#" -lt "1" ]; then
  echo "Usage:" $0 "config [bot args]"
  exit 1
fi

config="$1"

function get_config_value {
  cat "$config" | jq ".$1" | sed 's/"//g'
}

source "$(get_config_value "virtualenv_path")/bin/activate"
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
set -o pipefail
until stdbuf -oL "$DIR/bot.py" "$@" 2>&1 | tee -a "$(get_config_value "log_file")"; do
  sleep 5
done

