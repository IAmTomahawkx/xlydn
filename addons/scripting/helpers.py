import inspect

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
        for name, listener in self.__listeners__.items():
            async def cls_injected(*args, **kwargs):
                await listener(self, *args, **kwargs)

            cls_injected.__eq__ = listener.__eq__

            communicator.dispatcher.add_listener(listener.__event, cls_injected)

    def _eject(self, communicator):
        for listener in self.__listeners__:
            communicator.dispatcher.remove_listener(listener)