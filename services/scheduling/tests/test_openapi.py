"""The committed openapi.yaml lists exactly the endpoints this service's code has: no route
missing from the document, and nothing documented that the code doesn't serve."""

import re
from pathlib import Path

import yaml

from app import create_app

OPENAPI = Path(__file__).resolve().parent.parent / "openapi.yaml"
METHODS = {"get", "post", "put", "patch", "delete"}


def documented_endpoints():
    paths = yaml.safe_load(OPENAPI.read_text())["paths"]
    return {(method.upper(), path) for path, ops in paths.items() for method in ops if method in METHODS}


def endpoints_in_code(app):
    found = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        path = re.sub(r"<(?:[a-z]+:)?([a-z_]+)>", r"{\1}", rule.rule)  # /x/<int:id> -> /x/{id}
        found |= {(method, path) for method in rule.methods - {"HEAD", "OPTIONS"}}
    return found


def test_openapi_document_matches_the_routes(conn):
    assert endpoints_in_code(create_app(seed_demo=False)) == documented_endpoints()
