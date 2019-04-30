import time
import praw
from redditbasebot.bot import Bot
from config import *
from redditbasebot.basebot import BaseBot, BotUtil
from redditbasebot.bot_queues import bot_queues, BotQueues
from redditbasebot.workers import Watcher, Filter, Doer


class CommentKeywordWatcher(Watcher):

    def __init__(self, bot):
        super().__init__(bot)
        self._subreddits_to_watch_list = SUBRREDITS_TO_WATCH_LIST
        self._subreddits_to_watch = '+'.join(self._subreddits_to_watch_list)
        self.log.info('Watching subrredit {}'.format(self._subreddits_to_watch))

    def worker_logic(self):
        sub = self.reddit.subreddit(self._subreddits_to_watch)
        stream = sub.stream.comments()
        for comment in stream:
            self.log.info(f'Got comment from user {comment.author} with text {comment.body}')
            bot_queues[BotQueues.bot_queue_unfiltered].put(comment)


class CommentKeywordFilter(Filter):

    def __init__(self, bot):
        super().__init__(bot)
        self._start_time = BotUtil.get_utc_unix_timestamp()

    def worker_logic(self):
        if not bot_queues[BotQueues.bot_queue_unfiltered].empty():
            item = bot_queues[BotQueues.bot_queue_unfiltered].get()
            if self._start_time > item.created_utc and DISCARD_ITEMS_AFTER_BOT_START:
                self.log.debug(f'Discarding comment from {item.author.name} made after bot start')
            elif KEYWORD_TO_LOOK_FOR in item.body.lower():
                self.log.debug(f'Got comment from {item.author}, filter True, adding to filtered queue')
                bot_queues[BotQueues.bot_queue_filtered].put(item)
            else:
                self.log.debug(f'Got comment from {item.author}, filter False')


class CommentKeywordDoer(Doer):

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
                msg = 'Got comment from user {}'.format(item.author)
                self.log.info(msg)
                redditor = self.reddit.redditor(USERNAME_TO_NOTIFY)
                BotUtil.do_pm_reply('Found comment with keyword', item.link_permalink, redditor, self.log)
        except praw.exceptions.APIException as ex_msg:
            self.log.error('praw.exceptions.APIException inside doer_logic')
            self.log.error(ex_msg)
            bot_queues[BotQueues.bot_queue_retry].put(item)
            time_to_sleep = BotUtil.try_get_seconds_to_wait(str(ex_msg))
            self.log.info(f'Waiting for {time_to_sleep} until next doer because reddit of api exception')
            time.sleep(time_to_sleep)


if __name__ == '__main__':
    bot = Bot()
    workers = [CommentKeywordWatcher(bot), CommentKeywordFilter(bot), CommentKeywordDoer(bot)]
    bot.add_worker(workers)
    bot.run()