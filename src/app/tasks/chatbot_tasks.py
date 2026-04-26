from app.core.celery_app import celery_app


@celery_app.task(name="chatbot.generate_summary")
def generate_chatbot_summary_task(session_id: str) -> dict[str, str]:
    return {"session_id": session_id, "status": "queued"}


def enqueue_chatbot_summary_task(session_id: str) -> None:
    delay = getattr(generate_chatbot_summary_task, "delay", None)
    if callable(delay):
        delay(session_id)
