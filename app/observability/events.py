from app.observability.logger import logger


def log_event(
    event: str,
    node: str,
    **kwargs
):
    metadata = " | ".join(
        f"{key}={value}"
        for key, value in kwargs.items()
    )

    message = (
        f"event={event} | "
        f"node={node}"
    )

    if metadata:
        message += f" | {metadata}"

    logger.info(message)