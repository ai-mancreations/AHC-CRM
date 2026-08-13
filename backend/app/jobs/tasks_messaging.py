"""
Messaging send tasks. Providers are stubbed behind a common interface so real
credentials (WhatsApp Cloud API / Twilio SMS / SMTP or SES for email) can be
dropped in later without changing calling code.
"""
from app.jobs.celery_app import celery_app
from app.jobs.async_helper import run_async


class BaseSender:
    async def send(self, to: str, subject: str | None, body: str) -> dict:
        raise NotImplementedError


class StubSender(BaseSender):
    """Logs the outbound message instead of calling a real provider."""
    def __init__(self, channel: str):
        self.channel = channel

    async def send(self, to: str, subject: str | None, body: str) -> dict:
        print(f"[STUB {self.channel}] to={to} subject={subject!r} body={body[:120]!r}")
        return {"ok": True, "channel": self.channel, "to": to, "stubbed": True}


def get_sender(channel: str) -> BaseSender:
    # Swap in real implementations here once Settings > Integrations has credentials:
    #   WHATSAPP -> WhatsApp Cloud API / Gupshup sender
    #   SMS      -> Twilio / MSG91 sender
    #   EMAIL    -> SES / SMTP sender
    return StubSender(channel)


async def _render_and_send(template_id: str, to: str, context: dict):
    from app.models.settings_entity import MessageTemplate
    tpl = await MessageTemplate.get(template_id)
    if not tpl:
        return {"ok": False, "error": "Template not found"}
    body = tpl.body
    for key, value in context.items():
        body = body.replace(f"{{{{{key}}}}}", str(value))
    sender = get_sender(tpl.channel)
    return await sender.send(to, tpl.subject, body)


@celery_app.task(name="app.jobs.tasks_messaging.send_templated_message")
def send_templated_message(template_id: str, to: str, context: dict):
    return run_async(lambda: _render_and_send(template_id, to, context))
