import json
from pathlib import Path

import requests


def main():
    tokens = json.loads(Path("/tmp/helpdesk-perf-tokens.json").read_text())

    headers = {
        "Authorization": f"Bearer {tokens['requester']}",
    }

    instance_a = "http://127.0.0.1:8002"
    instance_b = "http://127.0.0.1:8003"

    for instance in [instance_a, instance_b]:
        response = requests.get(
            f"{instance}/api/v1/tickets",
            headers=headers,
            timeout=10,
        )

        assert response.status_code == 200

    print("Before logout: both instances returned 200")

    logout = requests.post(
        f"{instance_a}/api/v1/auth/logout",
        headers=headers,
        timeout=10,
    )

    assert logout.status_code == 200

    print("Logout through instance A: successful")

    for instance in [instance_a, instance_b]:
        response = requests.get(
            f"{instance}/api/v1/tickets",
            headers=headers,
            timeout=10,
        )

        assert response.status_code == 401

        print(f"{instance}: HTTP 401 Unauthorized")

    print("Cross-instance session revocation passed.")


if __name__ == "__main__":
    main()
