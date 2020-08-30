from collections import defaultdict

from faker import Faker

class SessionManager():
    def __init__(self, client, db):
        self.client = client
        self.db = db
        self._sessions = {}
        self._messages = {}
        self._players = defaultdict(set)

    async def add_session(self, channel, primary, tertiary, application, verbose=False):
        session_id = SessionManager.generate_session_id(primary, tertiary)
        if not self.get_session(session_id):
            self.db.insert_bulk([primary.id, tertiary.id])
            message = await channel.send(f"{primary.display_name} booting session between {primary.display_name} and {tertiary.display_name}...")
            new_session = application(session_id=session_id, client=self.client, db=self.db, channel=channel, message=message, primary=primary, tertiary=tertiary)

            sub_message = None
            if hasattr(new_session, 'SUB_MESSAGE'):
                sub_message = await channel.send(f"{new_session.SUB_MESSAGE}")
                await new_session.initialize_sub_message(sub_message)

            await new_session.render_message()

            self._sessions[session_id] = new_session
            self._players[primary.id].add(session_id)
            self._players[tertiary.id].add(session_id)
            self._messages[message.id] = session_id
            if sub_message:
                self._messages[sub_message.id] = session_id
            return new_session
        await channel.send(f"there is already a session between {primary.display_name} and {tertiary.display_name}")
        return False

    async def remove_session(self, channel, primary, tertiary):
        session_id = SessionManager.generate_session_id(primary, tertiary)
        if self.get_session(session_id):
            await self._sessions[session_id].on_complete()
            del self._sessions[session_id]
            self._players[primary.id].remove(session_id)
            # congrats you played yourself
            if primary.id != tertiary.id:
                self._players[tertiary.id].remove(session_id)
            await channel.send(f"{primary.display_name} ended session between {primary.display_name} and {tertiary.display_name}")
            return True
        await channel.send(f"no active session found between {primary.display_name} and {tertiary.display_name}")
        return False

    def get_session(self, session_id):
        return self._sessions[session_id] if session_id in self._sessions else None

    def get_session_by_message(self, message_id):
        return self._sessions[self._messages[message_id]] \
            if message_id in self._messages and self._messages[message_id] in self._sessions else None

    def get_session_by_player(self, player_id):
        return [self._sessions[session_id] for session_id in self._players[player_id] if session_id in self._sessions] if player_id in self._players else None

    @staticmethod
    def generate_session_id(primary, tertiary):
        uuid = Faker()
        seed = (primary.id,tertiary.id) if primary.id > tertiary.id else (tertiary.id,primary.id)
        uuid.seed_instance(seed)
        return uuid.uuid4()