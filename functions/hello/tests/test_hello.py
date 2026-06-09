"""Unit tests for hello.py.

Verifies the stream key format and payload structure without requiring a
live Redis instance.
"""

import importlib
import json
import sys
import types
from unittest.mock import MagicMock, call, patch


def _load_hello(deployment_id: str) -> types.ModuleType:
    """Import hello.py with a mocked redis module and the given DEPLOYMENT_ID."""
    mock_redis_module = MagicMock()
    mock_client = MagicMock()
    mock_redis_module.Redis.return_value = mock_client

    env = {
        "DEPLOYMENT_ID": deployment_id,
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6379",
    }

    with patch.dict("sys.modules", {"redis": mock_redis_module}), \
         patch.dict("os.environ", env, clear=False):
        # Force a fresh import each time
        if "hello" in sys.modules:
            del sys.modules["hello"]
        spec = importlib.util.spec_from_file_location(
            "hello",
            str(__file__).replace("tests/test_hello.py", "src/hello.py"),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

    return module, mock_client


def test_stream_key_uses_deployment_id():
    """XADD is called with the key test_workflow_{DEPLOYMENT_ID}."""
    deployment_id = "abc-123-def"
    _, client = _load_hello(deployment_id)

    assert client.xadd.call_count == 1
    stream_key = client.xadd.call_args[0][0]
    assert stream_key == f"test_workflow_{deployment_id}", (
        f"expected 'test_workflow_{deployment_id}', got '{stream_key}'"
    )


def test_payload_contains_hello_world_message():
    """The data field written to the stream includes message='hello_world'."""
    _, client = _load_hello("test-uuid-001")

    fields = client.xadd.call_args[0][1]
    data = json.loads(fields["data"])
    assert data["message"] == "hello_world", f"unexpected message: {data}"


def test_payload_contains_deployment_id():
    """The data field written to the stream includes the deployment_id."""
    deployment_id = "test-uuid-002"
    _, client = _load_hello(deployment_id)

    fields = client.xadd.call_args[0][1]
    data = json.loads(fields["data"])
    assert data["deployment_id"] == deployment_id, (
        f"expected deployment_id='{deployment_id}', got: {data}"
    )


def test_xadd_called_exactly_once():
    """hello.py writes exactly one entry to Redis."""
    _, client = _load_hello("single-write-test")
    assert client.xadd.call_count == 1
