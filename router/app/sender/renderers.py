from app.sender.models import UiKeyboard


def render_keyboard_markup(keyboard: UiKeyboard | None) -> dict | None:
    if keyboard is None:
        return None

    if keyboard.kind == "reply":
        return _render_reply_keyboard_markup(keyboard)

    return _render_inline_keyboard_markup(keyboard)


def _render_reply_keyboard_markup(keyboard: UiKeyboard) -> dict:
    return {
        "keyboard": [[{"text": button.title} for button in row] for row in keyboard.rows],
        "resize_keyboard": True,
        "one_time_keyboard": False,
        "selective": True,
    }


def _render_inline_keyboard_markup(keyboard: UiKeyboard) -> dict:
    return {
        "inline_keyboard": [
            [{"text": button.title, "callback_data": button.action} for button in row]
            for row in keyboard.rows
        ]
    }
