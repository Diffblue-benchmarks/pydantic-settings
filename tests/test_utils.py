import os
import socket
import stat
import tempfile
from pathlib import Path
from typing import List

import pytest

from pydantic_settings.utils import _lenient_issubclass, path_type_label


class TestPathTypeLabel:
    def test_path_type_label_directory(self, tmp_path: Path) -> None:
        result = path_type_label(tmp_path)
        assert result == 'directory'

    def test_path_type_label_file(self, tmp_path: Path) -> None:
        test_file = tmp_path / 'test_file.txt'
        test_file.write_text('test content')
        result = path_type_label(test_file)
        assert result == 'file'

    def test_path_type_label_symlink_to_dir(self, tmp_path: Path) -> None:
        target_dir = tmp_path / 'target_dir'
        target_dir.mkdir()
        symlink = tmp_path / 'symlink'
        symlink.symlink_to(target_dir)
        result = path_type_label(symlink)
        assert result == 'directory'

    def test_path_type_label_nonexistent_raises(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / 'nonexistent'
        with pytest.raises(AssertionError, match='path does not exist'):
            path_type_label(nonexistent)

    @pytest.mark.skipif(os.name == 'nt', reason='FIFO not supported on Windows')
    def test_path_type_label_fifo(self, tmp_path: Path) -> None:
        fifo_path = tmp_path / 'test_fifo'
        os.mkfifo(fifo_path)
        result = path_type_label(fifo_path)
        assert result == 'FIFO'

    @pytest.mark.skipif(os.name == 'nt', reason='Unix sockets not supported on Windows')
    def test_path_type_label_socket(self, tmp_path: Path) -> None:
        socket_path = tmp_path / 'test_socket'
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind(str(socket_path))
            result = path_type_label(socket_path)
            assert result == 'socket'
        finally:
            sock.close()


class TestLenientIssubclass:
    def test_lenient_issubclass_with_regular_class(self) -> None:
        assert _lenient_issubclass(int, object) is True

    def test_lenient_issubclass_with_subclass(self) -> None:
        assert _lenient_issubclass(bool, int) is True

    def test_lenient_issubclass_not_subclass(self) -> None:
        assert _lenient_issubclass(str, int) is False

    def test_lenient_issubclass_with_tuple(self) -> None:
        assert _lenient_issubclass(int, (str, int, float)) is True

    def test_lenient_issubclass_with_non_type(self) -> None:
        assert _lenient_issubclass('not a type', int) is False

    def test_lenient_issubclass_with_generic_alias(self) -> None:
        result = _lenient_issubclass(List[int], list)
        assert result is False

    def test_lenient_issubclass_with_none(self) -> None:
        assert _lenient_issubclass(None, object) is False

    def test_lenient_issubclass_with_instance(self) -> None:
        assert _lenient_issubclass(42, int) is False
