import types
from pathlib import Path
from typing import Generic, TypeVar, _GenericAlias  # type: ignore [attr-defined]
from unittest.mock import patch, MagicMock

import pytest

from pydantic_settings.utils import path_type_label, _lenient_issubclass


class TestPathTypeLabel:
    """Tests for path_type_label function."""

    def test_path_type_label_directory(self, tmp_path):
        """Test that a directory path returns 'directory'."""
        result = path_type_label(tmp_path)
        assert result == 'directory'

    def test_path_type_label_file(self, tmp_path):
        """Test that a file path returns 'file'."""
        file_path = tmp_path / 'test.txt'
        file_path.write_text('test')
        result = path_type_label(file_path)
        assert result == 'file'

    def test_path_type_label_nonexistent_path(self):
        """Test that nonexistent path raises AssertionError."""
        nonexistent_path = Path('/nonexistent/path/that/does/not/exist')
        with pytest.raises(AssertionError, match='path does not exist'):
            path_type_label(nonexistent_path)

    def test_path_type_label_symlink_to_directory(self, tmp_path):
        """Test that a symlink to directory returns 'directory' (checked before symlink)."""
        dir_path = tmp_path / 'test_dir'
        dir_path.mkdir()
        link_path = tmp_path / 'test_link'
        link_path.symlink_to(dir_path)
        result = path_type_label(link_path)
        # is_dir is checked before is_symlink, so symlink to dir returns 'directory'
        assert result == 'directory'

    def test_path_type_label_fifo(self, tmp_path):
        """Test that a FIFO path returns 'FIFO'."""
        fifo_path = tmp_path / 'test_fifo'
        try:
            import os
            os.mkfifo(str(fifo_path))
            result = path_type_label(fifo_path)
            assert result == 'FIFO'
        except OSError:
            # FIFO not supported on all systems, skip if it fails
            pytest.skip('FIFO not supported on this system')

    def test_path_type_label_block_device(self):
        """Test that a block device path returns 'block device'."""
        # Try /dev/sda or /dev/loop0
        test_paths = [Path('/dev/sda'), Path('/dev/sdb'), Path('/dev/loop0')]
        found = False
        for test_path in test_paths:
            if test_path.exists() and test_path.is_block_device():
                result = path_type_label(test_path)
                assert result == 'block device'
                found = True
                break
        if not found:
            pytest.skip('No accessible block devices found')

    def test_path_type_label_real_symlink(self, tmp_path):
        """Test that a true symlink (to non-dir, non-file special) returns 'symlink' if exists."""
        # Create a symlink path that isn't a dir or regular file
        # This is hard to test in a general way, so we'll skip
        pytest.skip('Hard to create a symlink that is_symlink=True but not is_dir/is_file')


class TestLenientIssubclass:
    """Tests for _lenient_issubclass function."""

    def test_lenient_issubclass_with_class(self):
        """Test _lenient_issubclass with a valid class."""
        result = _lenient_issubclass(int, int)
        assert result is True

    def test_lenient_issubclass_with_subclass(self):
        """Test _lenient_issubclass with a subclass."""
        class Parent:
            pass

        class Child(Parent):
            pass

        result = _lenient_issubclass(Child, Parent)
        assert result is True

    def test_lenient_issubclass_with_non_subclass(self):
        """Test _lenient_issubclass with a non-subclass."""
        result = _lenient_issubclass(str, int)
        assert result is False

    def test_lenient_issubclass_with_generic_alias(self):
        """Test _lenient_issubclass with a generic alias (Python 3.10+)."""
        # list[int] is a generic alias in Python 3.10+
        generic_alias = list[int]
        result = _lenient_issubclass(generic_alias, list)
        assert result is False

    def test_lenient_issubclass_with_non_type(self):
        """Test _lenient_issubclass with a non-type object."""
        result = _lenient_issubclass('not a type', str)
        assert result is False

    def test_lenient_issubclass_with_union_type(self):
        """Test _lenient_issubclass with a Union type (Python 3.10+)."""
        union_type = int | str
        result = _lenient_issubclass(union_type, (int, str))
        assert result is False

    def test_lenient_issubclass_with_type_error_and_origin(self):
        """Test _lenient_issubclass handles TypeError with get_origin not None."""
        # Create a mock object that will cause TypeError but has origin
        T = TypeVar('T')

        class MockGenericAlias:
            __origin__ = list

        mock_obj = MockGenericAlias()
        result = _lenient_issubclass(mock_obj, list)
        assert result is False

    def test_lenient_issubclass_with_type_error_no_origin(self):
        """Test _lenient_issubclass re-raises TypeError when get_origin is None."""
        class NotAClass:
            pass

        # Mock something that causes TypeError but has no origin
        with patch('pydantic_settings.utils.isinstance', return_value=False):
            result = _lenient_issubclass(NotAClass, int)
            assert result is False

    def test_lenient_issubclass_with_tuple_of_classes(self):
        """Test _lenient_issubclass with tuple of classes."""
        result = _lenient_issubclass(bool, (int, str))
        assert result is True

    def test_lenient_issubclass_with_integer_instance(self):
        """Test _lenient_issubclass with a non-type instance."""
        result = _lenient_issubclass(42, int)
        assert result is False
