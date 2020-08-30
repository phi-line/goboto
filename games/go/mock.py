import pathlib
import asyncio

from .go import Go
from .logic import ruleset

from utils import logger

class MockGo(Go):
    SCENARIOS = {
        'capture': [
            (0,3),(0,2),(1,3),(1,2),(2,4),(0,4),(4,3),(1,4),(2,2),(2,3)
        ],
        'sacrifice': [
            (0,0),(0,3),(0,1),(1,2),(0,2),(1,4),(0,3),(2,3),(1,3)
        ],
        'occupied': [
            (5,5),(5,5),(5,3),(3,3),(5,5)
        ],
        'nested_capture': [
            (2,4),(4,5),(6,4),(5,4),(4,2),(4,3),(4,6),(3,4),(3,3),(2,2),(3,5),(2,6),(5,5),(6,6),(5,3),(6,2),(4,4)
        ]
    }

    def __init__(self, session_id, client, db, channel, message, primary, tertiary):
        super().__init__(
            session_id=session_id,
            client=client,
            db=db,
            channel=channel,
            message=message,
            primary=primary,
            tertiary=tertiary,
            verbose=True
        )
    
    async def load(self, scenario):
        try:
            moves = self.SCENARIOS[scenario]
            for idx, move in enumerate(moves):
                await self.simulate_move(move[0], move[1], self.primary if idx % 2 == 0 else self.tertiary)
        except Exception as e:
            logger.info(f"Could not simulate match {e}")
            await self.channel.send(f"Encountered error in scenario. Check debug logs.")

        
    def initialize_helper(self):
        player_order = [self.primary, self.tertiary]
        self.current_player = player_order[0]
        self.team_skin = {
            player_order[0].id: {
                'tile': self.BLACK_TILE,
                'color': self.BLACK_COLOR
            },
            player_order[1].id: {
                'tile': self.WHITE_TILE,
                'color': self.WHITE_COLOR
            }
        }
        self.board = ruleset.initialize_board(self)
        pathlib.Path(self.emoji_directory).mkdir(parents=True, exist_ok=True)
        pathlib.Path(self.assets_directory).mkdir(parents=True, exist_ok=True)

    async def simulate_move(self, row, col, member):
        await self.play_move(
            payload=FakePayload(
                message_id=self.message.id,
                member=member,
                emoji=FakePayload(
                    name=list(self.BUTTONS_ROW.keys())[row]
                )
            )
        )

        await asyncio.sleep(.5)

        await self.play_move(
            payload=FakePayload(
                message_id=self.sub_message.id,
                member=member,
                emoji=FakePayload(
                    name=list(self.BUTTONS_COL.keys())[col]
                )
            )
        )

        await asyncio.sleep(.5)


class FakePayload:
    def __init__(self, **kwds):
        self.__dict__.update(kwds)