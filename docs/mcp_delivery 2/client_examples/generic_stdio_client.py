#!/usr/bin/env python3
"""Minimal stdio MCP client example; credentials are inherited from the environment."""

import json
import subprocess
import sys


server = subprocess.Popen(
    [sys.executable, "app/server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
)


def call(message):
    server.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
    server.stdin.flush()
    while True:
        response = json.loads(server.stdout.readline())
        if response.get("id") == message.get("id"):
            return response


print(call({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "example", "version": "1"}
    }
}))
print(call({
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {"name": "health_check", "arguments": {}}
}))
server.terminate()
