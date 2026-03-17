from app.routing.models import RouterCommand


def build_dedup_key(command: RouterCommand) -> str:
    action = command.action or "-"
    actor = command.actor_telegram_id or "-"
    turn_version = command.turn_version if command.turn_version is not None else "-"
    return (
        "dedup:"
        f"update:{command.update_id}:"
        f"chat:{command.chat_id}:"
        f"command:{command.command_type}:"
        f"action:{action}:"
        f"actor:{actor}:"
        f"turn:{turn_version}"
    )
