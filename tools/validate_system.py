"""Checks that the machine-readable description of the system is valid and matches the code.

    pip install -r tools/requirements.txt
    python tools/validate_system.py

1. system.yaml is valid against system.schema.json
2. each service's openapi.yaml is a valid OpenAPI 3 document
3. system.yaml matches the code:
   - the services are the ones in docker-compose.yml, and their folders, OpenAPI documents
     and migrations exist
   - env lists exactly the variables the service's config/settings.py reads, with the same
     defaults, and secrets are the ones without a default
   - every call goes to a known service, through a variable listed in env, to endpoints
     that exist in the called service's OpenAPI document, with the timeout's default
   - the UI only calls known services
(That each OpenAPI document lists exactly the Flask routes is a unit test in each service.)
Exits with 1 and lists every problem if anything fails.
"""

import json
import re
import sys
from pathlib import Path

import jsonschema
import yaml
from openapi_spec_validator import validate as validate_openapi

ROOT = Path(__file__).resolve().parent.parent
problems = []


def problem(message):
    problems.append(message)


def settings_variables(service_path):
    """{NAME: default or None} for every os.environ.get("NAME"[, default]) in config/settings.py."""
    source = (ROOT / service_path / "config" / "settings.py").read_text()
    found = {}
    for name, default in re.findall(r'os\.environ\.get\(\s*"([A-Z0-9_]+)"\s*(?:,\s*([^)]+?))?\s*\)', source):
        found[name] = default.strip().strip("\"'") if default else None
    return found


def main():
    schema = json.loads((ROOT / "system.schema.json").read_text())
    system = yaml.safe_load((ROOT / "system.yaml").read_text())

    # 1. against the schema
    for error in jsonschema.Draft202012Validator(schema).iter_errors(system):
        problem(f"system.yaml {'/'.join(map(str, error.path)) or '(top)'}: {error.message}")
    if problems:
        return  # the rest assumes the shape is right

    services = system["services"]
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    for name in services:
        if name not in compose["services"]:
            problem(f"service {name} is not a service in docker-compose.yml")

    # 2. OpenAPI documents
    openapi = {}
    for name, service in services.items():
        path = ROOT / service["openapi"]
        if not path.exists():
            problem(f"{name}: OpenAPI document {service['openapi']} not found")
            continue
        document = yaml.safe_load(path.read_text())
        try:
            validate_openapi(document)
        except Exception as error:  # the validator raises different error types
            problem(f"{service['openapi']} is not valid OpenAPI: {error}")
        openapi[name] = document
        if "/health" not in document.get("paths", {}):
            problem(f"{service['openapi']}: /health is not documented")

    # 3. against the code
    for name, service in services.items():
        if not (ROOT / service["path"]).is_dir():
            problem(f"{name}: folder {service['path']} not found")
            continue
        migrations = ROOT / service["migrations"]
        if not migrations.is_dir() or not list(migrations.glob("*.sql")):
            problem(f"{name}: no .sql migrations in {service['migrations']}")

        in_code = settings_variables(service["path"])
        listed = service["env"]
        for variable in sorted(set(in_code) - set(listed)):
            problem(f"{name}: config/settings.py reads {variable}, which is missing from env")
        for variable in sorted(set(listed) - set(in_code)):
            problem(f"{name}: env lists {variable}, which config/settings.py never reads")
        for variable in sorted(set(in_code) & set(listed)):
            code_default, entry = in_code[variable], listed[variable]
            if entry.get("secret"):
                if code_default is not None:
                    problem(f"{name}: {variable} is marked secret but has a default in the code")
            elif code_default is None:
                problem(f"{name}: {variable} has no default in the code, so it must be secret: true")
            elif str(entry["default"]) != code_default:
                problem(f"{name}: {variable} default is {entry['default']!r} in system.yaml "
                        f"but {code_default!r} in the code")
        if int(in_code.get("PORT") or 0) != service["port_default"]:
            problem(f"{name}: port_default {service['port_default']} differs from PORT's default in the code")

        for call in service.get("calls", []):
            callee = call["service"]
            if callee not in services:
                problem(f"{name} calls unknown service {callee}")
                continue
            if call["url_env"] not in listed:
                problem(f"{name}: call to {callee} uses {call['url_env']}, which is not in env")
            timeout_variable = f"{callee.upper()}_TIMEOUT_S"
            if timeout_variable in listed and float(listed[timeout_variable].get("default", -1)) != call["timeout_s"]:
                problem(f"{name}: timeout_s for {callee} differs from {timeout_variable}'s default")
            paths = openapi.get(callee, {}).get("paths", {})
            for endpoint in call["endpoints"]:
                method, path = endpoint.split(" ", 1)
                if method.lower() not in paths.get(path, {}):
                    problem(f"{name} calls {endpoint}, which is not in {callee}'s OpenAPI document")

    for callee in system["ui"]["calls"]:
        if callee not in services:
            problem(f"the UI calls unknown service {callee}")


if __name__ == "__main__":
    main()
    if problems:
        print("system description problems:")
        for message in problems:
            print(f"  - {message}")
        sys.exit(1)
    print("system.yaml and the OpenAPI documents are valid and match the code")
