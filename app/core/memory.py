"""Simple conversation memory store (in-memory for prototype)."""
from collections import deque


class ConversationMemory:
    def __init__(self, max_len: int = 20):
        self.buffer = deque(maxlen=max_len)

    def add(self, user: str, bot: str):
        self.buffer.append({"user": user, "bot": bot})

    def get(self):
        return list(self.buffer)
