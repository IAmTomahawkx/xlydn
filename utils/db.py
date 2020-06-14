import aiosqlite3
import asyncio
import warnings

class Database:
    def __init__(self):
        self.connection = None
        self.db_path = "services/data.db"
        self.lock = asyncio.Lock()

    async def close(self):
        if self.connection is not None:
            await self.connection.close()

    async def setup(self):
        self.connection = await aiosqlite3.connect(self.db_path)

        with open("services/schema.sql") as f:
            schema = f.read()

        try:
            await self.connection.executescript(schema)
            await self.connection.commit()
        except:
            import traceback
            traceback.print_exc()

    async def cursor(self):
        if self.connection is None:
            await self.setup()
        return await self.connection.cursor()

    async def execute(self, stmt: str, *values):
        async with self.lock:
            if self.connection is None:
                await self.setup()

            try:
                ret = await self.connection.execute(stmt, tuple(values))
                await self.connection.commit()
                return ret
            except aiosqlite3.OperationalError:
                raise
        """
            except SystemError:
                try:
                    await self.connection.commit()
                except (aiosqlite3.OperationalError, SystemError):
                    raise  # this keeps passing the "not an error" error.
                else:
                    raise

            else:
                try:
                    await self.connection.commit()
                except aiosqlite3.OperationalError:
                    raise  # this keeps passing the "not an error" error.
                return ret
        """
    async def fetchval(self, stmt: str, *values, default=None):
        """
        :param stmt: the SQL statement
        :param values: the values to be sanitized
        :param default: the default to return if no value was found, or if an error occurred
        :return: the first value in the fetched row
        """
        async with self.lock:
            if self.connection is None:
                await self.setup()

            try:
                return (await (await self.connection.execute(stmt, tuple(values))).fetchone())[0] or default
            except Exception:
                return default

    async def fetchrow(self, stmt: str, *values):
        """
        :param stmt: the SQL statement
        :param values: the values to be sanitized
        :return: the fetched row
        """
        async with self.lock:
            if self.connection is None:
                await self.setup()

            try:
                return await (await self.connection.execute(stmt, tuple(values))).fetchone()
            except Exception:
                return None

    async def fetch(self, stmt: str, *values):
        async with self.lock:
            if self.connection is None:
                await self.setup()

            try:
                return await (await self.connection.execute(stmt, tuple(values))).fetchall()
            except Exception:
                return None

    async def commit(self):
        if self.connection is None:
            await self.setup()
        try:
            await self.connection.commit()
        except:
            pass

    async def executemany(self, stmt: str, values: list):
        async with self.lock:
            if self.connection is None:
                await self.setup()
            if self.connection._conn is None:
                await self.connection.connect()
            try:
                await self.connection.executemany(stmt, values)
            except aiosqlite3.OperationalError:
                await self.connection.rollback()
                raise
            else:
                await self.connection.commit()

    def __enter__(self):
        return self.connection.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.connection.__exit__(exc_type, exc_val, exc_tb)