import inspect

def _local_wrap(func):
    def wraps(inner):
        async def wrapper(*args, **kwargs):
            return await inner(func, *args, **kwargs)

        wrapper.__name__ = func.__name__
        return wrapper

    return wraps

class Injection:
    @classmethod
    def command(cls, name: str = None):
        def wraps(func):
            func.__command = name or func.__name__
            if not hasattr(cls, "__commands__"):
                cls.__commands__ = {}

            cls.__commands__[name] = func
            return func

        return wraps

    @classmethod
    def listen(cls, event: str = None):
        def wraps(func):
            func.__event = e = event or func.__name__
            if not hasattr(cls, "__listeners__"):
                cls.__listeners__ = {}

            cls.__listeners__[e] = func
            return func

        return wraps

    def _inject(self, communicator):
        if not hasattr(self, "__listeners__"):
            self.__listeners__ = {}

        if not hasattr(self, "__commands__"):
            self.__commands__ = {}

        for name, listener in self.__listeners__.items():
            @_local_wrap(listener)
            async def injected(_list, *args, **kwargs):
                await _list(self, *args, **kwargs)

            communicator.dispatcher.add_listener(name, injected)
            del name, listener, injected

        for name, command in self.__commands__.items():
            @_local_wrap(command)
            async def injected(comm, *args, **kwargs):
                await comm(self, *args, **kwargs)

            communicator.commands[name] = injected
            del name, command

    def _eject(self, communicator):
        for listener in self.__listeners__.values():
            communicator.dispatcher.remove_listener(listener)

        for command in self.__commands__:
            del communicator.commands[command]