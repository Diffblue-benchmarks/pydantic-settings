"""Tests for CliSettingsSource._convert_positional_arg."""

from unittest.mock import MagicMock

import pytest
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from pydantic_settings import BaseSettings, CliSettingsSource


class SimpleSettings(BaseSettings):
    name: str = 'default'

    model_config = {'env_file': None}


def _make_source(**kwargs):
    return CliSettingsSource(SimpleSettings, **kwargs)


def _make_field_info(required: bool):
    fi = MagicMock(spec=FieldInfo)
    fi.is_required.return_value = required
    return fi


def _base_kwargs(dest='my_field', action=None):
    kwargs = {'dest': dest, 'required': True}
    if action is not None:
        kwargs['action'] = action
    return kwargs


def test_basic_required_positional_arg():
    """A required positional arg with no special action sets metavar and removes dest/required."""
    source = _make_source()
    field_info = _make_field_info(required=True)
    kwargs = _base_kwargs()

    arg_names, flag_prefix = source._convert_positional_arg(
        kwargs, field_info, 'my_field', PydanticUndefined
    )

    assert arg_names == ['my_field']
    assert flag_prefix == ''
    assert kwargs['default'] is PydanticUndefined
    assert kwargs['metavar'] == 'MY_FIELD'
    assert 'dest' not in kwargs
    assert 'required' not in kwargs
    assert 'nargs' not in kwargs


def test_non_required_positional_arg_sets_nargs_optional():
    """A non-required positional arg (field has default) sets nargs='?'."""
    source = _make_source()
    field_info = _make_field_info(required=False)
    kwargs = _base_kwargs()

    arg_names, flag_prefix = source._convert_positional_arg(
        kwargs, field_info, 'my_field', PydanticUndefined
    )

    assert arg_names == ['my_field']
    assert flag_prefix == ''
    assert kwargs['nargs'] == '?'
    assert 'dest' not in kwargs
    assert 'required' not in kwargs


def test_non_required_due_to_model_default():
    """When model_default is not PydanticUndefined, the arg is treated as non-required."""
    source = _make_source()
    field_info = _make_field_info(required=True)
    kwargs = _base_kwargs()

    arg_names, flag_prefix = source._convert_positional_arg(
        kwargs, field_info, 'my_field', 'some_default'
    )

    assert kwargs['nargs'] == '?'
    assert arg_names == ['my_field']


def test_append_action_required_sets_nargs_plus():
    """When action is 'append' and the field is required, nargs='+' and action is removed."""
    source = _make_source()
    field_info = _make_field_info(required=True)
    kwargs = _base_kwargs(action='append')

    arg_names, flag_prefix = source._convert_positional_arg(
        kwargs, field_info, 'items', PydanticUndefined
    )

    assert arg_names == ['my_field']
    assert kwargs['nargs'] == '+'
    assert 'action' not in kwargs
    assert 'dest' not in kwargs
    assert 'required' not in kwargs


def test_append_action_non_required_sets_nargs_star():
    """When action is 'append' and field is not required, nargs='*'."""
    source = _make_source()
    field_info = _make_field_info(required=False)
    kwargs = _base_kwargs(action='append')

    arg_names, flag_prefix = source._convert_positional_arg(
        kwargs, field_info, 'items', PydanticUndefined
    )

    assert kwargs['nargs'] == '*'
    assert 'action' not in kwargs


def test_kebab_case_metavar():
    """When cli_kebab_case is True, the metavar converts underscores to hyphens."""
    source = _make_source(cli_kebab_case=True)
    field_info = _make_field_info(required=True)
    kwargs = _base_kwargs(dest='my_field')

    source._convert_positional_arg(
        kwargs, field_info, 'my_field', PydanticUndefined
    )

    assert kwargs['metavar'] == 'MY-FIELD'


def test_no_kebab_case_metavar():
    """When cli_kebab_case is False/None, the metavar preserves underscores."""
    source = _make_source(cli_kebab_case=False)
    field_info = _make_field_info(required=True)
    kwargs = _base_kwargs(dest='my_field')

    source._convert_positional_arg(
        kwargs, field_info, 'my_field', PydanticUndefined
    )

    assert kwargs['metavar'] == 'MY_FIELD'


def test_default_is_set_to_pydantic_undefined():
    """The kwargs default is always set to PydanticUndefined."""
    source = _make_source()
    field_info = _make_field_info(required=False)
    kwargs = _base_kwargs()
    kwargs['default'] = 'original'

    source._convert_positional_arg(
        kwargs, field_info, 'alias', 'some_model_default'
    )

    assert kwargs['default'] is PydanticUndefined
