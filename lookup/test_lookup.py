import base64
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import yaml


loader = importlib.machinery.SourceFileLoader("lookup", str(Path(__file__).with_name("lookup")))
spec = importlib.util.spec_from_loader(loader.name, loader)
lookup = importlib.util.module_from_spec(spec)
loader.exec_module(lookup)


class Output(io.TextIOWrapper):
    def __init__(self):
        super().__init__(io.BytesIO(), encoding="utf-8")

    def value(self):
        self.flush()
        return self.buffer.getvalue()


class Response:
    status = 200

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return self.body


class LookupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        env = patch.dict(os.environ, {"HOME": str(self.base), "XDG_CONFIG_HOME": str(self.base / "xdg")})
        env.start()
        self.addCleanup(env.stop)
        self.path = lookup.config_path()
        self.path.parent.mkdir(parents=True)
        self.config = {"api_key_sid": "SK" + "0" * 32, "api_key_secret": "fake-secret",
                       "fields": ["caller_name", "line_type_intelligence"]}
        self.write_config()
        self.opener_patch = patch.object(lookup.urllib.request, "build_opener")
        self.opener = self.opener_patch.start().return_value
        self.addCleanup(self.opener_patch.stop)
        self.body = b'{ "valid": true, "caller_name": null, "code": 1, "network": "01", "errors": [], "nested": {"a": false}, "phone_number": "+14155550100" }\n'
        self.opener.open.return_value = Response(self.body)

    def write_config(self):
        self.path.write_text(json.dumps(self.config))
        self.path.chmod(0o600)

    def run_cli(self, args):
        output, errors = Output(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                code = lookup.main(args)
            except SystemExit as exit_error:
                code = exit_error.code
        return code, output.value(), errors.getvalue()

    def test_yaml_types(self):
        code, output, errors = self.run_cli(["+14155550100"])
        self.assertEqual(code, 0)
        self.assertEqual(errors, "")
        self.assertEqual(yaml.safe_load(output), json.loads(self.body))
        self.assertIn(b"valid: true", output)

    def test_raw_and_json_exact_bytes(self):
        for flag in ("--raw", "--json"):
            for body in (self.body, b'{"a":1}', b'not JSON\r\n\xff'):
                self.opener.open.return_value = Response(body)
                code, output, errors = self.run_cli([flag, "+14155550100"])
                self.assertEqual((code, output, errors), (0, body, ""))

    def test_argument_errors_never_request(self):
        for args in ([], ["--raw"], ["one", "two"], ["--unknown"], [""]):
            self.assertEqual(self.run_cli(args)[0], 2)
        self.opener.open.assert_not_called()
        self.assertEqual(self.run_cli(["--help"])[0], 0)

    def test_phone_encoding_auth_and_timeout(self):
        self.run_cli(["+1 (415)/555?0100#"])
        args, kwargs = self.opener.open.call_args
        request = args[0]
        self.assertIn("/%2B1%20%28415%29%2F555%3F0100%23?", request.full_url)
        query = lookup.urllib.parse.parse_qs(lookup.urllib.parse.urlsplit(request.full_url).query)
        self.assertEqual(query, {"Fields": ["caller_name,line_type_intelligence"]})
        encoded = request.get_header("Authorization").split()[1]
        self.assertEqual(base64.b64decode(encoded), (self.config["api_key_sid"] + ":fake-secret").encode())
        self.assertEqual(kwargs, {"timeout": 30})

    def test_http_error_raw_and_yaml(self):
        body = b'{ "code": 20003, "message": "Authentication Error" }'
        for flag in ([], ["--raw"], ["--json"]):
            self.opener.open.side_effect = urllib.error.HTTPError("mock", 401, "Unauthorized", {}, io.BytesIO(body))
            code, output, errors = self.run_cli(["+14155550100"] + flag)
            self.assertEqual(code, 1)
            self.assertIn("HTTP 401", errors)
            self.assertNotIn("fake-secret", errors)
            self.assertEqual(output, body) if flag else self.assertEqual(yaml.safe_load(output), json.loads(body))

    def test_network_error_does_not_expose_credentials(self):
        self.opener.open.side_effect = urllib.error.URLError("fake-secret")
        code, output, errors = self.run_cli(["+14155550100"])
        self.assertEqual((code, output), (1, b""))
        self.assertNotIn("fake-secret", errors)

    def test_malformed_json(self):
        for body in (b"<html>error</html>", b"\xff"):
            self.opener.open.return_value = Response(body)
            code, output, errors = self.run_cli(["+14155550100"])
            self.assertEqual((code, output), (1, b""))
            self.assertIn("malformed JSON", errors)

    def test_missing_config(self):
        self.path.unlink()
        code, output, errors = self.run_cli(["+14155550100"])
        self.assertEqual((code, output), (1, b""))
        self.assertIn("Missing config", errors)
        self.opener.open.assert_not_called()

    def test_xdg_and_fallback(self):
        fallback = self.base / ".config" / "twilio-lookup" / "config.json"
        for value in ("", "relative"):
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": value}):
                self.assertEqual(lookup.config_path(), fallback)
        with patch.dict(os.environ):
            os.environ.pop("XDG_CONFIG_HOME")
            self.assertEqual(lookup.config_path(), fallback)
        self.assertEqual(lookup.config_path(), self.path)
        fallback.parent.mkdir(parents=True)
        fallback.write_bytes(self.path.read_bytes())
        fallback.chmod(0o600)
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "relative"}):
            self.assertEqual(self.run_cli(["+14155550100"])[0], 0)

    def test_bad_config_and_permissions(self):
        self.path.chmod(0o644)
        self.assertIn("chmod 600", self.run_cli(["one"])[2])
        self.path.chmod(0o600)
        for text in ('{bad', '[]', '{}', '{"api_key_sid": "secret"}'):
            self.path.write_text(text)
            self.assertEqual(self.run_cli(["one"])[0], 1)
        self.opener.open.assert_not_called()

    def test_package_selection(self):
        for fields in ([], list(lookup.PACKAGES)):
            self.config["fields"] = fields
            self.write_config()
            self.assertEqual(self.run_cli(["one"])[0], 0)
            url = self.opener.open.call_args[0][0].full_url
            self.assertEqual("?" in url, bool(fields))
        for fields in (["unknown"], "caller_name", ["caller_name", "caller_name"], [{}]):
            self.config["fields"] = fields
            self.write_config()
            self.assertEqual(self.run_cli(["one"])[0], 1)

    def test_omitted_fields_requests_all_three(self):
        self.config.pop("fields")
        self.write_config()
        self.assertEqual(self.run_cli(["one"])[0], 0)
        query = lookup.urllib.parse.parse_qs(lookup.urllib.parse.urlsplit(self.opener.open.call_args[0][0].full_url).query)
        self.assertEqual(query, {"Fields": [",".join(lookup.PACKAGES)]})

    def test_each_disable_flag_after_config_selection(self):
        self.config["fields"] = list(lookup.PACKAGES)
        self.write_config()
        for package in lookup.PACKAGES:
            self.assertEqual(self.run_cli(["one", "--no-" + package.replace("_", "-")])[0], 0)
            query = lookup.urllib.parse.parse_qs(lookup.urllib.parse.urlsplit(self.opener.open.call_args[0][0].full_url).query)
            self.assertEqual(query["Fields"], [",".join(p for p in lookup.PACKAGES if p != package)])

    def test_disable_flags_combine_and_do_not_add_packages(self):
        flags = ["--no-" + p.replace("_", "-") for p in lookup.PACKAGES]
        self.assertEqual(self.run_cli(["one"] + flags)[0], 0)
        self.assertNotIn("?", self.opener.open.call_args[0][0].full_url)
        self.config["fields"] = ["caller_name"]
        self.write_config()
        self.assertEqual(self.run_cli(["one", "--no-line-status"])[0], 0)
        self.assertIn("Fields=caller_name", self.opener.open.call_args[0][0].full_url)

    def test_free_overrides_every_package_config(self):
        for fields in (list(lookup.PACKAGES), ["future_paid_package"], "invalid", None):
            self.config["fields"] = fields
            self.write_config()
            for flags in (["--free"], ["--free", "--raw"], ["--free", "--json", "--no-caller-name"]):
                code, output, errors = self.run_cli(["one"] + flags)
                self.assertEqual((code, errors), (0, ""))
                self.assertNotIn("?", self.opener.open.call_args[0][0].full_url)
                if "--raw" in flags or "--json" in flags:
                    self.assertEqual(output, self.body)

    def test_package_error_preserved(self):
        self.opener.open.return_value = Response(b'{"line_type_intelligence":{"error_code":60601}}')
        code, output, errors = self.run_cli(["one"])
        self.assertEqual(code, 0)
        self.assertEqual(yaml.safe_load(output)["line_type_intelligence"]["error_code"], 60601)

    def test_redirect_disabled(self):
        self.assertIsNone(lookup.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.com"))

    def test_raw_does_not_need_yaml(self):
        with patch.dict("sys.modules", {"yaml": None}):
            self.assertEqual(self.run_cli(["one", "--raw"])[0], 0)
            self.opener.open.reset_mock()
            code, output, errors = self.run_cli(["one"])
            self.assertEqual((code, output), (1, b""))
            self.assertIn("needs PyYAML", errors)
            self.opener.open.assert_not_called()


if __name__ == "__main__":
    unittest.main()
