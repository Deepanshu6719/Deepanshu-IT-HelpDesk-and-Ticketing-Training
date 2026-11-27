import json
from pathlib import Path

import requests

INSTANCE_A = "http://127.0.0.1:8002"
INSTANCE_B = "http://127.0.0.1:8003"

TOKEN_FILE = Path("/tmp/helpdesk-perf-tokens.json")


def get_tickets(instance, token):
    response = requests.get(
        f"{instance}/api/v1/tickets",
        headers={
            "Authorization": f"Bearer {token}",
        },
        params={
            "page": 1,
            "limit": 10,
        },
        timeout=10,
    )

    response.raise_for_status()

    payload = response.json()

    assert payload["success"] is True

    return payload["data"]


def main():
    tokens = json.loads(TOKEN_FILE.read_text())

    for role, token in tokens.items():
        result_a = get_tickets(INSTANCE_A, token)
        result_b = get_tickets(INSTANCE_B, token)

        assert result_a == result_b, f"Different responses for role: {role}"

        print(f"{role}: authenticated successfully on both API instances")

        print(f"Accessible tickets: {result_a['total']}")

    print("\nCross-instance authentication verification passed.")


if __name__ == "__main__":
    main()
