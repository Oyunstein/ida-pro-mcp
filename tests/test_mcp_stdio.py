"""STDIO cancellation tests that do not require IDA/idalib."""

import json
import queue
import threading
import time

from _mcp_spec_support import McpServer
from zeromcp.jsonrpc import RequestCancelledError, get_current_cancel_event


class _QueuedInput:
    def __init__(self):
        self._lines = queue.Queue()
        self._read_count = 0
        self._read_condition = threading.Condition()

    def feed(self, message):
        if message is None:
            self._lines.put(b"")
            return
        self._lines.put(json.dumps(message).encode("utf-8") + b"\n")

    def readline(self):
        line = self._lines.get(timeout=5.0)
        with self._read_condition:
            self._read_count += 1
            self._read_condition.notify_all()
        return line

    def wait_for_reads(self, count, timeout=2.0):
        deadline = time.monotonic() + timeout
        with self._read_condition:
            while self._read_count < count:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not self._read_condition.wait(remaining):
                    return False
            return True


class _CapturedOutput:
    def __init__(self):
        self._buffer = bytearray()
        self._lock = threading.Lock()

    def write(self, data):
        with self._lock:
            self._buffer.extend(data)
        return len(data)

    def flush(self):
        pass

    def messages(self):
        with self._lock:
            lines = bytes(self._buffer).splitlines()
        return [json.loads(line) for line in lines]


def test_stdio_receives_cancellation_while_tool_runs_and_remains_responsive():
    server = McpServer("test")
    started = threading.Event()

    @server.tool
    def wait_until_cancelled() -> dict:
        cancel_event = get_current_cancel_event()
        assert cancel_event is not None
        started.set()
        assert cancel_event.wait(2.0)
        raise RequestCancelledError("Request was cancelled")

    stdin = _QueuedInput()
    stdout = _CapturedOutput()
    serving = threading.Thread(
        target=server.stdio,
        kwargs={"stdin": stdin, "stdout": stdout},
        daemon=True,
    )
    serving.start()

    stdin.feed(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "wait_until_cancelled", "arguments": {}},
        }
    )
    assert started.wait(2.0)
    stdin.feed(
        {
            "jsonrpc": "2.0",
            "method": "notifications/cancelled",
            "params": {"requestId": 1, "reason": "test"},
        }
    )
    stdin.feed({"jsonrpc": "2.0", "id": 2, "method": "ping"})

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        messages = stdout.messages()
        if any(message.get("id") == 2 for message in messages):
            break
        time.sleep(0.01)
    else:
        raise AssertionError("STDIO server did not answer after cancellation")

    stdin.feed(None)
    serving.join(timeout=2.0)
    assert not serving.is_alive()
    messages = stdout.messages()
    assert [message.get("id") for message in messages] == [2]
    assert messages[0]["result"] == {}


def test_tools_call_preserves_request_cancelled_error_code():
    server = McpServer("test")

    @server.tool
    def cancelled() -> None:
        raise RequestCancelledError("cancelled by test")

    response = server.registry.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "cancelled", "arguments": {}},
        }
    )

    assert response is not None
    assert response["error"]["code"] == -32800


def test_stdio_answers_control_request_while_long_request_is_running():
    server = McpServer("test")
    started = threading.Event()
    release = threading.Event()

    @server.tool
    def long_request() -> dict:
        started.set()
        assert release.wait(2.0)
        return {"completed": True}

    stdin = _QueuedInput()
    stdout = _CapturedOutput()
    serving = threading.Thread(
        target=server.stdio,
        kwargs={"stdin": stdin, "stdout": stdout},
        daemon=True,
    )
    serving.start()
    stdin.feed(
        {
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {"name": "long_request", "arguments": {}},
        }
    )
    assert started.wait(1.0)
    stdin.feed({"jsonrpc": "2.0", "id": 21, "method": "ping"})

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        messages = stdout.messages()
        if any(message.get("id") == 21 for message in messages):
            break
        time.sleep(0.01)
    else:
        raise AssertionError("control request was serialized behind long request")
    assert not any(message.get("id") == 20 for message in stdout.messages())

    release.set()
    stdin.feed(None)
    serving.join(timeout=2.0)
    assert not serving.is_alive()
    assert {message.get("id") for message in stdout.messages()} == {20, 21}


def test_stdio_reserves_cancellation_for_a_queued_numeric_request():
    server = McpServer("test")
    all_workers_started = threading.Event()
    release_first = threading.Event()
    started_count = 0
    started_lock = threading.Lock()

    @server.tool
    def block_first() -> dict:
        nonlocal started_count
        with started_lock:
            started_count += 1
            if started_count == 4:
                all_workers_started.set()
        assert release_first.wait(2.0)
        return {"completed": True}

    @server.tool
    def observe_queued_cancel() -> dict:
        cancel_event = get_current_cancel_event()
        assert cancel_event is not None
        if not cancel_event.is_set():
            raise AssertionError("queued cancellation was lost before dispatch")
        raise RequestCancelledError("Request was cancelled while queued")

    stdin = _QueuedInput()
    stdout = _CapturedOutput()
    serving = threading.Thread(
        target=server.stdio,
        kwargs={"stdin": stdin, "stdout": stdout},
        daemon=True,
    )
    serving.start()

    for request_id in (10, 13, 14, 15):
        stdin.feed(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": "block_first", "arguments": {}},
            }
        )
    assert all_workers_started.wait(2.0)
    stdin.feed(
        {
            "jsonrpc": "2.0",
            "id": 11.5,
            "method": "tools/call",
            "params": {"name": "observe_queued_cancel", "arguments": {}},
        }
    )
    stdin.feed(
        {
            "jsonrpc": "2.0",
            "method": "notifications/cancelled",
            "params": {"requestId": 11.5, "reason": "queued test"},
        }
    )
    stdin.feed({"jsonrpc": "2.0", "id": 12, "method": "ping"})
    assert stdin.wait_for_reads(7)
    release_first.set()

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        messages = stdout.messages()
        if any(message.get("id") == 12 for message in messages):
            break
        time.sleep(0.01)
    else:
        raise AssertionError("queued cancellation blocked later STDIO requests")

    stdin.feed(None)
    serving.join(timeout=2.0)
    assert not serving.is_alive()
    response_ids = [message.get("id") for message in stdout.messages()]
    assert 11.5 not in response_ids
    assert set(response_ids) == {10, 12, 13, 14, 15}
