"""Upload-and-run demo for the hello workflow.

Uploads the workflow directory to the cluster via the orchestrator's
/workflows/upload endpoint, then tails the result Redis stream over
WebSocket until the hello function's message arrives.

Usage:
    python upload-demo.py

Required:
    CATBROWER_API_KEY environment variable (or edit API_KEY below)
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import swarm_sdk
from swarm_sdk import OrchestratorService

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Use the cluster LAN IP directly — api.catbrower.com routes through Cloudflare
# which is unreachable from on-LAN machines.  SSL verification is disabled
# because the cert is issued for the hostname, not the IP.
BASE_URL = "https://192.168.1.2"
API_KEY = os.environ.get("CATBROWER_API_KEY", "")
STREAM_TIMEOUT = 60  # seconds to wait for the workflow to write its output
POLL_INTERVAL = 3.0  # seconds between retries while stream doesn't exist yet

WORKFLOW_DIR = Path(__file__).parent  # test_workflow/


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run() -> int:
    if not API_KEY:
        print("error: CATBROWER_API_KEY is not set", file=sys.stderr)
        return 1

    svc = OrchestratorService(
        base_url=BASE_URL,
        api_key=API_KEY,
        verify=False,
        host="api.catbrower.com",
    )

    # --- 1. Upload the workflow zip to the cluster ---
    print(f"Uploading workflow from {WORKFLOW_DIR} ...")
    try:
        zip_path = swarm_sdk.zip_workflow(WORKFLOW_DIR)
        result = svc.upload_workflow(str(zip_path), command=None)
        zip_path.unlink(missing_ok=True)
    except Exception as exc:
        print(f"error: upload failed — {exc}", file=sys.stderr)
        return 1

    deployment_id = result.get("deploymentId")
    status = result.get("status", "unknown")
    full_name = result.get("fullName", "")
    print(f"Deployed: status={status!r}  deploymentId={deployment_id}  fullName={full_name!r}")

    # --- 2. Tail the output stream ---
    stream_name = f"test_workflow_{deployment_id}"
    print(f"\nWaiting for output on stream {stream_name!r} (timeout {STREAM_TIMEOUT}s, polling every {POLL_INTERVAL}s) ...")

    message = None
    try:
        async with asyncio.timeout(STREAM_TIMEOUT):
            async for msg in svc.tail_stream(stream_name, poll_interval=POLL_INTERVAL):
                message = msg
                break
    except TimeoutError:
        print(f"error: timed out waiting for stream {stream_name!r}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: stream read failed — {exc}", file=sys.stderr)
        return 1

    if message is None:
        print("error: stream closed without delivering a message", file=sys.stderr)
        return 1

    # --- 3. Print the result ---
    print("\nReceived message:")
    raw_data = message.get("data", message)
    if isinstance(raw_data, str):
        try:
            raw_data = json.loads(raw_data)
        except json.JSONDecodeError:
            pass
    print(json.dumps(raw_data, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
