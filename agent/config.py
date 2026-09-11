"""Shared env loading + a clear "missing key" signal (instead of a raw
KeyError) so smoke tests can report SKIPPED vs FAILED accurately."""
import os

from dotenv import load_dotenv

load_dotenv()


class MissingCredential(RuntimeError):
    def __init__(self, var_name: str):
        super().__init__(f"{var_name} is not set — copy .env.template to .env and fill it in")
        self.var_name = var_name


def require_env(var_name: str) -> str:
    value = os.environ.get(var_name)
    if not value:
        raise MissingCredential(var_name)
    return value
