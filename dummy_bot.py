import time
import praw
from bot import Bot
from config import *
from basebot2 import BaseBot2, BotUtil
from bot_queues import bot_queues, BotQueues
from workers import Watcher, Filter, Doer


class DummyBotWatcher(Watcher):

    def __init__(self, bot):
        super().__init__(bot)

    def watcher_logic(self):
        pass


class DummyBotFilter(Filter):

    def __init__(self, bot):
        super().__init__(bot)
        self._start_time = BotUtil.get_utc_unix_timestamp()
        self._usernames = USERNAMES

    def filter_logic(self):
        pass


class DummyBotDoer(Doer):

    def __init__(self, bot):
        super().__init__(bot)

    def worker_logic(self):
        try:
            pass
        except praw.exceptions.APIException as ex_msg:
            self.log.error('praw.exceptions.APIException inside worker_logic')
            self.log.error(ex_msg)
            time_to_sleep = BotUtil.try_get_seconds_to_wait(str(ex_msg))
            self.log.info(f'Waiting for {time_to_sleep} until next doer because reddit of api exception')
            time.sleep(time_to_sleep)



if __name__ == '__main__':
    bot = Bot()
    workers =[DummyBotWatcher(bot), DummyBotFilter(bot), DummyBotDoer(bot)]
    bot.add_worker(workers)
    bot.run()