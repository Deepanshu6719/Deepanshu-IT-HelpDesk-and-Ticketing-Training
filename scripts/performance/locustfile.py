import json
import random
from pathlib import Path

from locust import HttpUser, between, task

TOKEN_FILE = Path("/tmp/helpdesk-perf-tokens.json")


class HelpdeskUser(HttpUser):
    host = "http://127.0.0.1:8002"
    wait_time = between(1, 3)

    def on_start(self):
        tokens = json.loads(TOKEN_FILE.read_text())

        self.role = random.choices(
            ["admin", "requester", "agent"],
            weights=[20, 50, 30],
            k=1,
        )[0]

        self.client.headers.update(
            {
                "Authorization": (f"Bearer {tokens[self.role]}"),
            }
        )

        self.ticket_ids = []

        self.fetch_tickets()

        if not self.ticket_ids:
            raise RuntimeError(f"No accessible tickets for {self.role}")

    def fetch_tickets(self):
        with self.client.get(
            "/api/v1/tickets",
            params={
                "page": random.randint(1, 3),
                "limit": 10,
            },
            name=f"GET /tickets [{self.role}]",
            catch_response=True,
            timeout=10,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Unexpected status: {response.status_code}")
                return

            try:
                payload = response.json()

                if payload["success"] is not True:
                    response.failure("Unsuccessful response")
                    return

                self.ticket_ids = [ticket["id"] for ticket in payload["data"]["items"]]

                if not self.ticket_ids:
                    response.failure("Empty ticket list")

            except (ValueError, KeyError, TypeError):
                response.failure("Invalid response structure")

    @task(5)
    def list_tickets(self):
        self.fetch_tickets()

    @task(3)
    def get_ticket(self):
        if not self.ticket_ids:
            return

        ticket_id = random.choice(self.ticket_ids)

        self.client.get(
            f"/api/v1/tickets/{ticket_id}",
            name=f"GET /tickets/:id [{self.role}]",
            timeout=10,
        )

    @task(2)
    def get_comments(self):
        if not self.ticket_ids:
            return

        ticket_id = random.choice(self.ticket_ids)

        self.client.get(
            f"/api/v1/tickets/{ticket_id}/comments",
            params={"page": 1, "limit": 10},
            name=f"GET /tickets/:id/comments [{self.role}]",
            timeout=10,
        )
