"""Tests for CliSettingsSource._is_nested_alias_path_only_workaround method."""

from unittest.mock import MagicMock, patch

import pytest

from pydantic_settings import BaseSettings, CliSettingsSource


class SimpleSettings(BaseSettings):
    name: str = 'default'
    count: int = 0

    model_config = {'env_file': None}


@pytest.fixture
def cli_source():
    return CliSettingsSource(SimpleSettings, cli_parse_args=[])


def test_returns_false_when_field_not_in_parser_map(cli_source):
    """Returns False when field_name has no entry in _parser_map (line 602)."""
    parsed_args = {'unknown_field': ['value1']}
    result = cli_source._is_nested_alias_path_only_workaround(
        parsed_args, 'unknown_field', ['value1']
    )
    assert result is False
    assert parsed_args == {'unknown_field': ['value1']}


def test_workaround_creates_new_nested_entry(cli_source):
    """When alias_path_only with nested prefix and dest not yet in parsed_args,
    creates a new JSON entry (lines 605-610, 613)."""
    mock_arg = MagicMock()
    mock_arg.is_alias_path_only = True
    mock_arg.arg_prefix = 'parent.'
    mock_arg.preferred_alias = 'child_key'

    cli_source._parser_map['parent.child_key'] = {None: mock_arg}

    parsed_args = {'parent.child_key': ['some_val']}
    with patch.object(cli_source, '_merge_parsed_list', return_value='"merged"') as mock_merge:
        result = cli_source._is_nested_alias_path_only_workaround(
            parsed_args, 'parent.child_key', ['some_val']
        )
        mock_merge.assert_called_once_with(['some_val'], 'parent.child_key')

    assert result is True
    assert 'parent.child_key' not in parsed_args
    assert parsed_args['parent'] == '{"child_key": "merged"}'


def test_workaround_appends_to_existing_nested_entry(cli_source):
    """When alias_path_only with nested prefix and dest already in parsed_args,
    appends to existing JSON entry (lines 605-608, 611, 613)."""
    mock_arg = MagicMock()
    mock_arg.is_alias_path_only = True
    mock_arg.arg_prefix = 'parent.'
    mock_arg.preferred_alias = 'second_key'

    cli_source._parser_map['parent.second_key'] = {None: mock_arg}

    parsed_args = {
        'parent': '{"first_key": "existing"}',
        'parent.second_key': ['new_val'],
    }
    with patch.object(cli_source, '_merge_parsed_list', return_value='"new_merged"'):
        result = cli_source._is_nested_alias_path_only_workaround(
            parsed_args, 'parent.second_key', ['new_val']
        )

    assert result is True
    assert 'parent.second_key' not in parsed_args
    assert parsed_args['parent'] == '{"first_key": "existing", "second_key": "new_merged"}'


def test_workaround_not_applied_when_empty_parser_map_entry(cli_source):
    """Returns False when _parser_map has the key but with empty values dict (line 602)."""
    cli_source._parser_map['empty_field'] = {}

    parsed_args = {'empty_field': ['val']}
    result = cli_source._is_nested_alias_path_only_workaround(
        parsed_args, 'empty_field', ['val']
    )
    assert result is False
    assert parsed_args == {'empty_field': ['val']}
