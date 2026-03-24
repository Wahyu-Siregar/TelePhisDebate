from types import SimpleNamespace

from src.bot.actions import BotActions


def _make_message(chat_id: int, message_id: int, username: str | None, chat_type: str):
    return SimpleNamespace(
        chat_id=chat_id,
        message_id=message_id,
        chat=SimpleNamespace(username=username, type=chat_type),
    )


def test_build_message_link_public_chat():
    actions = BotActions(bot=None)
    msg = _make_message(chat_id=-1001234567890, message_id=77, username="telephisgroup", chat_type="supergroup")

    link = actions._build_message_link(msg)

    assert link == "https://t.me/telephisgroup/77"


def test_build_message_link_private_supergroup():
    actions = BotActions(bot=None)
    msg = _make_message(chat_id=-1001234567890, message_id=88, username=None, chat_type="supergroup")

    link = actions._build_message_link(msg)

    assert link == "https://t.me/c/1234567890/88"


def test_build_message_link_private_chat_none():
    actions = BotActions(bot=None)
    msg = _make_message(chat_id=1362435992, message_id=99, username=None, chat_type="private")

    link = actions._build_message_link(msg)

    assert link is None
