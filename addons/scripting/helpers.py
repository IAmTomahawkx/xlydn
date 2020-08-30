
class Injection:
    __listeners__ = {}
    @classmethod
    def listen(cls, event: str = None):
        def wraps(func):
            func.__event = e = event or func.__name__
            cls.__listeners__[e] = func
            return func

        return wraps

    def _inject(self, communicator):
        for listener in self.__listeners__:
            communicator.dispatcher.add_listener(listener)

    def _eject(self, communicator):
        for listener in self.__listeners__:
            communicator.dispatcher.remove_listener(listener)