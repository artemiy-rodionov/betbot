#!/usr/bin/env bash

if [ "$#" != "1" ]; then
  echo "Usage:" $0 "config"
  exit 1
fi

config="$1"

function get_config_value {
  cat "$config" | jq ".$1" | sed 's/"//g'
}

source "$(get_config_value "virtualenv_path")/bin/activate"
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
"$DIR/bot.py" "$config"

