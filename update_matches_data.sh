#!/usr/bin/env bash

if [ "$#" != "1" ]; then
  echo "Usage:" $0 "config"
  exit 1
fi

config="$1"

function get_config_value {
  cat "$config" | jq ".$1" | sed 's/"//g'
}

curl "$(get_config_value "matches_data_source")" > "$(get_config_value "matches_data_file")"
