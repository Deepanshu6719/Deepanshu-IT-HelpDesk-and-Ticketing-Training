from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


def apply_security_headers(
    headers: MutableHeaders,
    *,
    hsts_enabled: bool,
    hsts_max_age: int,
    is_https: bool,
) -> None:
    headers["X-Content-Type-Options"] = "nosniff"
    headers["X-Frame-Options"] = "DENY"
    headers["Referrer-Policy"] = "no-referrer"

    headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

    if hsts_enabled and is_https:
        headers["Strict-Transport-Security"] = f"max-age={hsts_max_age}"


class SecurityHeadersMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        hsts_enabled: bool = False,
        hsts_max_age: int = 31536000,
    ):
        self.app = app
        self.hsts_enabled = hsts_enabled
        self.hsts_max_age = hsts_max_age

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(
            message: Message,
        ) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)

                apply_security_headers(
                    headers,
                    hsts_enabled=self.hsts_enabled,
                    hsts_max_age=self.hsts_max_age,
                    is_https=scope.get("scheme") == "https",
                )

            await send(message)

        await self.app(
            scope,
            receive,
            send_with_security_headers,
        )
