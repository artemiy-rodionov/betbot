
from dynaconf import Dynaconf

config = Dynaconf(
    envvar_prefix="DYNACONF",
    settings_files=['instance/settings.json'],
)

# `envvar_prefix` = export envvars with `export DYNACONF_FOO=bar`.
# `settings_files` = Load these files in the order.