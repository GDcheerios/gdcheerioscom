class Event:
    def __init__(self, name: str, argcount: int = 0) -> None:
        self._name = name
        self._argcount = argcount
        self._callbacks = []

    def __call__(self, *args) -> None:
        if len(args) != self._argcount:
            raise RuntimeError(
                f"event '{self._name}' called with wrong number of arguments! called with: {len(args)}. expected: {self._argcount}")

        for idx, callback in enumerate(self._callbacks):
            try:
                callback(*args)
            except Exception as e:
                raise RuntimeError(
                    f"event '{self._name}' callback number: {idx} raised an error") from e

    def __iadd__(self, callback: 'Callable') -> 'Event':
        if not callable(callback):
            raise RuntimeError("event callback must be a callable")

        self._callbacks.append(callback)
        return self

    def __isub__(self, callback: 'Callable') -> 'Event':
        if not callable(callback):
            raise RuntimeError("event callback must be a callable")

        self._callbacks.remove(callback)
        return self
