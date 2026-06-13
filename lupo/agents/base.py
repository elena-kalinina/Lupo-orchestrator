"""Agent base. Each agent has a name (shown on the canvas) and an events handle."""


class Agent:
    role = "agent"

    def __init__(self, name, events):
        self.name = name
        self.events = events

    def emit(self, kind, **data):
        return self.events.emit(kind, self.name, **data)
