import time
import praw
from redditbasebot.bot import Bot
from config import *
from redditbasebot.basebot import BaseBot, BotUtil
from redditbasebot.bot_queues import bot_queues, BotQueues
from redditbasebot.workers import Watcher, Filter, Doer


class SubmissionKeywordWatcher(Watcher):

    def __init__(self, bot):
        super().__init__(bot)
        self._subreddits_to_watch_list = SUBRREDITS_TO_WATCH_LIST
        self._subreddits_to_watch = '+'.join(self._subreddits_to_watch_list)
        self.log.info('Watching subrredit {}'.format(self._subreddits_to_watch))

    def worker_logic(self):
        sub = self.reddit.subreddit(self._subreddits_to_watch)
        stream = sub.stream.submissions()
        for submission in stream:
            self.log.info(f'Got submission from user {submission.author} with title {submission.title}')
            bot_queues[BotQueues.bot_queue_unfiltered].put(submission)


class SubmissionKeywordFilter(Filter):

    def __init__(self, bot):
        super().__init__(bot)
        self._start_time = BotUtil.get_utc_unix_timestamp()

    def worker_logic(self):
        if not bot_queues[BotQueues.bot_queue_unfiltered].empty():
            item = bot_queues[BotQueues.bot_queue_unfiltered].get()
            if self._start_time > item.created_utc and DISCARD_ITEMS_AFTER_BOT_START:
                self.log.debug(f'Discarding submission from {item.author.name} made after bot start')
            elif KEYWORD_TO_LOOK_FOR in item.selftext.lower() or KEYWORD_TO_LOOK_FOR in item.title.lower():
                self.log.debug(f'Got submission from {item.author}, filter True, adding to filtered queue')
                bot_queues[BotQueues.bot_queue_filtered].put(item)
            else:
                self.log.debug(f'Got submission from {item.author}, filter False')


class SubmissionKeywordDoer(Doer):

    def __init__(self, bot):
        super().__init__(bot)

    def worker_logic(self):
        item = None
        try:
            if not bot_queues[BotQueues.bot_queue_retry].empty():
                item = bot_queues[BotQueues.bot_queue_retry].get()
            elif not bot_queues[BotQueues.bot_queue_filtered].empty():
                item = bot_queues[BotQueues.bot_queue_filtered].get()
            if item:
                msg = 'Got submission from user {}'.format(item.author)
                self.log.info(msg)
                redditor = self.reddit.redditor(USERNAME_TO_NOTIFY)
                BotUtil.do_pm_reply('Found submission with keyword', item.permalink, redditor, self.log)
        except praw.exceptions.APIException as ex_msg:
            self.log.error('praw.exceptions.APIException inside doer_logic')
            self.log.error(ex_msg)
            bot_queues[BotQueues.bot_queue_retry].put(item)
            time_to_sleep = BotUtil.try_get_seconds_to_wait(str(ex_msg))
            self.log.info(f'Waiting for {time_to_sleep} until next doer because reddit of api exception')
            time.sleep(time_to_sleep)


if __name__ == '__main__':
    bot = Bot('dummy')
    workers = [SubmissionKeywordWatcher(bot), SubmissionKeywordFilter(bot), SubmissionKeywordDoer(bot)]
    bot.add_worker(workers)
    bot.run()
