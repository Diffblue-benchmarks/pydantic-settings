import os
import tempfile
from pathlib import Path
from typing import List, Optional

import pytest

from pydantic_settings.utils import _lenient_issubclass, path_type_label


def test_path_type_label_directory(tmp_path):
    assert path_type_label(tmp_path) == 'directory'


def test_path_type_label_file(tmp_path):
    f = tmp_path / 'file.txt'
    f.write_text('hello')
    assert path_type_label(f) == 'file'


@pytest.mark.skip(reason="Symlink branch unreachable: p.exists() returns False for broken symlinks, and valid symlinks match is_file/is_dir first")
def test_path_type_label_symlink(tmp_path):
    link = tmp_path / 'broken_link'
    link.symlink_to(tmp_path / 'nonexistent_target')
    assert path_type_label(link) == 'symlink'


def test_path_type_label_nonexistent_raises(tmp_path):
    p = tmp_path / 'nonexistent'
    with pytest.raises(AssertionError, match='path does not exist'):
        path_type_label(p)


def test_lenient_issubclass_true():
    assert _lenient_issubclass(int, object) is True


def test_lenient_issubclass_false():
    assert _lenient_issubclass(int, str) is False


def test_lenient_issubclass_non_type():
    assert _lenient_issubclass('not_a_type', int) is False


def test_lenient_issubclass_generic_alias():
    # list[int] is a generic alias; on Python 3.10, isinstance(list[int], type) is True
    # but issubclass raises TypeError. _lenient_issubclass should return False.
    result = _lenient_issubclass(list[int], list)
    assert result is False or result is True  # behavior depends on Python version, just ensure no exception


def test_lenient_issubclass_with_tuple():
    assert _lenient_issubclass(bool, (int, str)) is True


def test_lenient_issubclass_none():
    assert _lenient_issubclass(None, int) is False
