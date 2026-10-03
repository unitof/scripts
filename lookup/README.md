# Twilio Lookup

Small Python 3 CLI with one dependency (PyYAML); no Twilio SDK.

```sh
lookup +14155550100
lookup +14155550100 --raw
lookup +14155550100 --json
```

The number is required. Prefer E.164 with a leading `+`; Twilio defaults national
numbers to US. Default output converts the complete JSON response to readable
YAML, preserving strings, numbers, booleans, nulls, arrays and nested objects.
`--raw` and `--json` write the HTTP body bytes unchanged, without an extra newline,
even for an HTTP error or non-JSON body. Errors exit nonzero and diagnostics go to
stderr. Package-level `error_code` values remain visible in the response; a
successful HTTP request can still contain missing package data.

## Run on zoe

PyYAML is already available in zoe's current `python3`. Put this bundle on PATH:

```sh
export PATH="$HOME/repos/scripts/lookup:$PATH"
lookup --help
```

For a Python installation without PyYAML, use an isolated environment:

```sh
python3 -m venv ~/repos/scripts/lookup/.venv
~/repos/scripts/lookup/.venv/bin/python -m pip install -r ~/repos/scripts/lookup/requirements.txt
source ~/repos/scripts/lookup/.venv/bin/activate
export PATH="$HOME/repos/scripts/lookup:$PATH"
```

## Manual local credential setup

Do this yourself locally. Do not paste secrets into chat or commit them. The CLI
only reads credentials; it does not create, modify or display the config file.
It never evaluates shell code from configuration.

The file is `$XDG_CONFIG_HOME/twilio-lookup/config.json`, falling back to
`~/.config/twilio-lookup/config.json` when XDG_CONFIG_HOME is unset, empty, or
relative, per the [XDG specification](https://specifications.freedesktop.org/basedir/latest/).
No system/shared config or environment credential fallbacks are used.

```sh
config_base="${XDG_CONFIG_HOME:-$HOME/.config}"
case "$config_base" in /*) ;; *) config_base="$HOME/.config" ;; esac
config_dir="$config_base/twilio-lookup"
(umask 077; mkdir -p "$config_dir"; cp -n ~/repos/scripts/lookup/config.example.json "$config_dir/config.json")
chmod 600 "$config_dir/config.json"
"${EDITOR:-vi}" "$config_dir/config.json"
```

Replace the placeholders with an **API Key SID** (`SK` followed by 32 hexadecimal
characters) and its **API key secret** from your Twilio Console. This is a pair,
not a single API token and not an Account SID/Auth Token pair. Twilio Lookup v2
uses these as the HTTP Basic username and password. Direct REST requests here
do not require an Account SID; Twilio SDK initialization examples also use one.
Use a key with Lookup access in the default US1 region. Group/world-accessible
configuration files are rejected. The example contains placeholders only.

## Packages and charges

Every invocation makes one HTTPS GET, with a 30-second timeout and no retries or
redirects, to `https://lookups.twilio.com/v2/PhoneNumbers/{encoded-number}`.
By default no `Fields` parameter is sent: only free basic formatting/validation
is requested. To request caller name and carrier/line type, set `"fields":
["caller_name", "line_type_intelligence"]`. Both are paid add-ons. Caller name
covers US carriers; Canada line type intelligence requires approval. Unrequested
packages such as `line_status` appear as null in the standard response.

The optional `fields` config array accepts `caller_name`, `line_type_intelligence`
and `line_status`; select all three to request status data as well at additional cost.
Use `"fields": []` for only free basic formatting/validation. All requested
packages may be billed individually. On 2026-10-03 Twilio's published line type
rate is $0.008/request and line status starts at $0.007/request; caller name is
also paid, and exact rates/availability depend on the account and market. Check
current pricing before using real credentials. No live calls were made for tests.

References: [Lookup v2 API/auth/packages](https://www.twilio.com/docs/lookup/v2-api),
[Twilio pricing](https://www.twilio.com/en-us/user-authentication-identity/pricing/lookup),
[API keys](https://www.twilio.com/docs/iam/api-keys).

## Tests

```sh
python3 -m unittest discover -s ~/repos/scripts/lookup -p 'test_*.py' -v
```

HTTP is mocked; fixtures use fake keys and phone numbers. Tests do not read real
credentials or contact Twilio. Roll back a published change with `git revert`
of the implementation commit, then push (do not reset or force-push).
