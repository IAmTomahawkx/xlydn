import asyncio
import inspect
from typing import Callable, Dict, List, ClassVar

class Signal:
    def __init__(self):
        self.__emitters = []

    def listen(self):
        def wraps(func: Callable):
            self.add_listener(func)
            return func

        return wraps

    def add_listener(self, func: Callable):
        self.__emitters.append(func)

    def remove_listener(self, func: Callable):
        self.__emitters.remove(func)

    def emit(self, *args, **kwargs):
        for emitter in self.__emitters:
            emitter(*args, **kwargs)


class CoroSignal(Signal):
    def __init__(self, loop: asyncio.AbstractEventLoop = None):
        self.loop = loop or asyncio.get_event_loop()
        self.__emitters = []

    def emit(self, *args, **kwargs):
        for emitter in self.__emitters:
            asyncio.run_coroutine_threadsafe(emitter, self.loop)

class MultiSignal(Signal):
    __emitters: ClassVar[Dict[str, List[Callable]]] = {}

    def __init__(self, loop: asyncio.AbstractEventLoop = None, strict_async: bool = False):
        """
        :param loop: the event loop to run coroutines in
        :param strict_async: when true, forces all registered listeners to be coroutines
        """
        self.loop = loop or asyncio.get_event_loop()
        self.__strict = strict_async
        self.__emitters = {}

    def add_listener(self, event: str, func: Callable): # noqa
        if self.__strict and not inspect.iscoroutinefunction(func):
            raise ValueError("listeners must be coroutines")

        func._event_name = event

        if event in self.__emitters:
            self.__emitters[event].append(func)

        else:
            self.__emitters[event] = [func]

    def remove_listener(self, func: Callable): # noqa
        if not hasattr(func, "_event_name"):
            raise ValueError("function is not a listener")

        event = func._event_name # noqa
        if event in self.__emitters:
            self.__emitters[event].remove(func)

    def listen(self, event: str = None) -> Callable:
        """
        a decorator function to add a listener
        :param event: the event to listen to
        :return:
        """
        def wraps(func):
            e = event or func.__name__
            self.add_listener(e, func)

        return wraps

    def emit(self, event: str, *args, **kwargs):
        if event not in self.__emitters:
            return

        for emitter in self.__emitters[event]:
            print(args)
            if inspect.iscoroutinefunction(emitter):
                asyncio.run_coroutine_threadsafe(emitter(*args, **kwargs), loop=self.loop)

            else:
                emitter(*args, **kwargs)
