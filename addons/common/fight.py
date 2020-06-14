
class Duel:
    def __init__(self, user1, user2, system):
        self.user1 = user1
        self.user2 = user2
        self.accepted = False
        self.system = system

    def get_user_health(self, user):

    def accept(self, userid, ctx):
        if self.user2.id != userid:
            return False
        if self.accepted:
            return False

        self.accepted = True

    async def battle(self):