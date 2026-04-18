"""Tests for CliSettingsSource._metavar_format_recurse targeting uncovered branches."""

import typing

import pytest

from pydantic import BaseModel
from pydantic._internal._repr import Representation

from pydantic_settings import BaseSettings, CliSettingsSource


class _MinimalSettings(BaseSettings):
    x: str = 'default'

    model_config = {'env_file': None}


@pytest.fixture
def cli_source():
    return CliSettingsSource(_MinimalSettings, cli_parse_args=[])


# --- Line 1342: module-level function ---
def _module_level_func():
    pass


def test_metavar_format_recurse_module_level_function(cli_source):
    result = cli_source._metavar_format_recurse(_module_level_func)
    # Module-level function should use __qualname__ since '<locals>' is not in qualname
    assert result == _module_level_func.__qualname__


# --- Line 1342: locally-defined function ---
def test_metavar_format_recurse_local_function(cli_source):
    def local_func():
        pass

    result = cli_source._metavar_format_recurse(local_func)
    # Locally defined function should use __name__ since '<locals>' is in qualname
    assert '<locals>' in local_func.__qualname__
    assert result == local_func.__name__
    assert result == 'local_func'


# --- Line 1344: Ellipsis ---
def test_metavar_format_recurse_ellipsis(cli_source):
    result = cli_source._metavar_format_recurse(...)
    assert result == '...'


# --- Line 1346: Representation instance ---
def test_metavar_format_recurse_representation(cli_source):
    obj = Representation()
    result = cli_source._metavar_format_recurse(obj)
    assert result == repr(obj)


# --- Line 1348: ForwardRef ---
def test_metavar_format_recurse_forward_ref(cli_source):
    ref = typing.ForwardRef('SomeModel')
    result = cli_source._metavar_format_recurse(ref)
    assert result == str(ref)


# --- Line 1351 + 1378: non-type instance that falls through to else ---
def test_metavar_format_recurse_non_type_instance(cli_source):
    # An instance of a plain class (not a type, not _typing_base, not _WithArgsTypes)
    # that hits line 1351 (obj = obj.__class__) then falls to line 1375 (isinstance(obj, type))
    # returning obj.__qualname__
    class Dummy:
        pass

    obj = Dummy()
    result = cli_source._metavar_format_recurse(obj)
    # After obj = obj.__class__, obj becomes Dummy which is a type, so line 1375-1376 applies
    assert 'Dummy' in result


# --- Line 1378: else branch for typing special forms ---
def test_metavar_format_recurse_typing_special_form(cli_source):
    # typing.Any is a _SpecialForm (instance of _Final/_typing_base) but not a type,
    # so it passes through to the else branch
    result = cli_source._metavar_format_recurse(typing.Any)
    assert result == 'Any'
