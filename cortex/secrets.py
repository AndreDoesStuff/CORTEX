"""Secret resolution. Registry values reference secrets by name ("env:NAME");
raw tokens live only in the environment (loaded from a git-ignored .env)."""

from __future__ import annotations

import os


class MissingSecret(Exception):
    """A referenced secret is not set in the environment."""


def resolve(value: str) -> str:
    """Resolve a registry auth value. "env:JIRA_TOKEN" -> the env var's value.

    Any value not prefixed with a known scheme is returned as-is, but a literal
    secret in the registry is a bug — the plan requires "never inline".
    """
    if not isinstance(value, str):
        raise MissingSecret(f"auth value must be a string reference, got {value!r}")
    if value.startswith("env:"):
        name = value[len("env:"):]
        got = os.environ.get(name)
        if not got:
            raise MissingSecret(f"environment variable {name} is not set")
        return got
    # Non-reference values are treated as missing to enforce the no-inline rule.
    raise MissingSecret(
        f"auth value {value!r} is not an env: reference — secrets must never be inlined"
    )
