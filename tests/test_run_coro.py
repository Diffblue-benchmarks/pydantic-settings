"""Tests for the run_coro inner function within CliApp._run_cli_cmd.

These tests target lines 656-661 which handle async cli_cmd execution
when there's already a running event loop (e.g., Jupyter Notebook context).
"""
import asyncio

import pytest
from pydantic import BaseModel

from pydantic_settings import BaseSettings, CliApp


class TestRunCoroWithRunningEventLoop:
    """Tests for async cli_cmd execution when an event loop is already running."""

    def test_async_cli_cmd_within_running_loop(self):
        """Test async cli_cmd runs in separate thread when event loop is running."""
        execution_log = []

        class MyModel(BaseModel):
            name: str = 'default'

            async def cli_cmd(self):
                execution_log.append('async executed')

        async def run_with_existing_loop():
            model = MyModel()
            result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)
            return result

        result = asyncio.run(run_with_existing_loop())

        assert result.name == 'default'
        assert execution_log == ['async executed']

    def test_async_cli_cmd_exception_propagates_from_thread(self):
        """Test exceptions from async cli_cmd are propagated when run in separate thread."""

        class MyModel(BaseModel):
            name: str = 'default'

            async def cli_cmd(self):
                raise ValueError('async error from thread')

        async def run_with_existing_loop():
            model = MyModel()
            CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)

        with pytest.raises(ValueError, match='async error from thread'):
            asyncio.run(run_with_existing_loop())

    def test_async_cli_cmd_with_await_operations(self):
        """Test async cli_cmd with actual await operations in running loop context."""
        execution_log = []

        class MyModel(BaseModel):
            delay_ms: int = 10

            async def cli_cmd(self):
                await asyncio.sleep(self.delay_ms / 1000)
                execution_log.append('completed after await')

        async def run_with_existing_loop():
            model = MyModel(delay_ms=5)
            result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)
            return result

        result = asyncio.run(run_with_existing_loop())

        assert result.delay_ms == 5
        assert execution_log == ['completed after await']

    def test_async_cli_cmd_access_model_fields(self):
        """Test async cli_cmd can access model fields when run in thread."""
        captured_values = []

        class MyModel(BaseModel):
            field_a: str = 'value_a'
            field_b: int = 42

            async def cli_cmd(self):
                captured_values.append((self.field_a, self.field_b))

        async def run_with_existing_loop():
            model = MyModel(field_a='test', field_b=100)
            return CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)

        result = asyncio.run(run_with_existing_loop())

        assert result.field_a == 'test'
        assert result.field_b == 100
        assert captured_values == [('test', 100)]

    def test_cliapp_run_async_cli_cmd_within_running_loop(self):
        """Test CliApp.run with async cli_cmd when event loop is running."""
        execution_log = []

        class MySettings(BaseSettings):
            name: str = 'default'

            async def cli_cmd(self):
                execution_log.append(f'executed with name={self.name}')

        async def run_with_existing_loop():
            return CliApp.run(MySettings, cli_args=['--name', 'async_test'])

        result = asyncio.run(run_with_existing_loop())

        assert result.name == 'async_test'
        assert execution_log == ['executed with name=async_test']

    def test_async_cli_cmd_runtime_error_propagates(self):
        """Test RuntimeError from async cli_cmd propagates correctly."""

        class MyModel(BaseModel):
            name: str = 'default'

            async def cli_cmd(self):
                raise RuntimeError('runtime error in async')

        async def run_with_existing_loop():
            model = MyModel()
            CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)

        with pytest.raises(RuntimeError, match='runtime error in async'):
            asyncio.run(run_with_existing_loop())

    def test_async_cli_cmd_custom_exception_propagates(self):
        """Test custom exception types propagate from async cli_cmd in thread."""

        class CustomError(Exception):
            pass

        class MyModel(BaseModel):
            name: str = 'default'

            async def cli_cmd(self):
                raise CustomError('custom error message')

        async def run_with_existing_loop():
            model = MyModel()
            CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)

        with pytest.raises(CustomError, match='custom error message'):
            asyncio.run(run_with_existing_loop())
