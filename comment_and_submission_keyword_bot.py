import time
import praw
from redditbasebot.bot import Bot
from config import *
from redditbasebot.basebot import BaseBot, BotUtil
from redditbasebot.bot_queues import bot_queues, BotQueues
from redditbasebot.workers import Watcher, Filter, Doer
from more_queues import MoreBotQueues


class SubmissionKeywordWatcher(Watcher):

    def __init__(self, bot):
        super().__init__(bot, watcher_name='Submission wacher')
        self._subreddits_to_watch_list = SUBRREDITS_TO_WATCH_FOR_SUBMISSIONS_LIST
        self._subreddits_to_watch = '+'.join(self._subreddits_to_watch_list)
        self.log.info(f'Watching subrredit {self._subreddits_to_watch}')

    def worker_logic(self):
        sub = self.reddit.subreddit(self._subreddits_to_watch)
        stream = sub.stream.submissions()
        for submission in stream:
            self.log.info(f'Got submission from user {submission.author} with title {submission.title}')
            bot_queues[BotQueues.bot_queue_unfiltered].put(submission)

class CommentKeywordWatcher(Watcher):

    def __init__(self, bot):
        super().__init__(bot, watcher_name='Comment watcher')
        self._subreddits_to_watch_list = SUBRREDITS_TO_WATCH_FOR_COMMENTS_LIST
        self._subreddits_to_watch = '+'.join(self._subreddits_to_watch_list)
        self.log.info(f'Watching subrredit {self._subreddits_to_watch}')

    def worker_logic(self):
        sub = self.reddit.subreddit(self._subreddits_to_watch)
        stream = sub.stream.comments()
        for comment in stream:
            self.log.info(f'Got comment from user {comment.author} with text {comment.body}')
            bot_queues[BotQueues.bot_queue_unfiltered].put(comment)


class KeywordFilter(Filter):

    def __init__(self, bot):
        super().__init__(bot)
        self._start_time = BotUtil.get_utc_unix_timestamp()

    def worker_logic(self):
        if not bot_queues[BotQueues.bot_queue_unfiltered].empty():
            item = bot_queues[BotQueues.bot_queue_unfiltered].get()
            if self._start_time > item.created_utc and DISCARD_ITEMS_AFTER_BOT_START:
                self.log.debug(f'Discarding submission from {item.author.name} made after bot start')
            elif isinstance(item, praw.models.Submission):
                if KEYWORD_TO_LOOK_FOR_SUBMISSION in item.selftext.lower():
                    self.log.debug(f'Got submission from {item.author}, filter True, adding to filtered queue')
                    bot_queues[MoreBotQueues.submission_filtered].put(item)
            elif isinstance(item, praw.models.Comment):
                if KEYWORD_TO_LOOK_FOR_COMMENT in item.body.lower():
                    self.log.debug(f'Got comment from {item.author}, filter True, adding to filtered queue')
                    bot_queues[MoreBotQueues.comment_filtered].put(item)
            else:
                raise TypeError(f'Was expecting Submisson or Comment type but got {type(item)}')


class SubmissionKeywordDoer(Doer):

    def __init__(self, bot):
        super().__init__(bot, doer_name='Submission doer')

    def worker_logic(self):
        item = None
        try:
            if not bot_queues[BotQueues.bot_queue_retry].empty():
                item = bot_queues[BotQueues.bot_queue_retry].get()
            elif not bot_queues[BotQueues.bot_queue_filtered].empty():
                item = bot_queues[BotQueues.bot_queue_filtered].get()
            if item:
                redditor = self.reddit.redditor(USERNAME_TO_NOTIFY_FOR_SUBMISSION)
                BotUtil.do_pm_reply('Found submission with keyword', item.permalink, redditor, self.log)
                self.log.info(f'Got submission from user {item.author} and sent pm')
        except praw.exceptions.APIException as ex_msg:
            self.log.error('praw.exceptions.APIException inside doer_logic')
            self.log.error(ex_msg)
            bot_queues[BotQueues.bot_queue_retry].put(item)
            time_to_sleep = BotUtil.try_get_seconds_to_wait(str(ex_msg))
            self.log.info(f'Waiting for {time_to_sleep} until next doer because reddit of api exception')
            time.sleep(time_to_sleep)


class CommentKeywordDoer(Doer):

    def __init__(self, bot):
        super().__init__(bot, doer_name='Comment doer')

    def worker_logic(self):
        item = None
        try:
            if not bot_queues[BotQueues.bot_queue_retry].empty():
                item = bot_queues[BotQueues.bot_queue_retry].get()
            elif not bot_queues[BotQueues.bot_queue_filtered].empty():
                item = bot_queues[BotQueues.bot_queue_filtered].get()
            if item:
                redditor = self.reddit.redditor(USERNAME_TO_NOTIFY_FOR_COMMENT)
                BotUtil.do_pm_reply('Found comment with keyword', item.permalink, redditor, self.log)
                self.log.info(f'Got comment from user {item.author} and sent pm')
        except praw.exceptions.APIException as ex_msg:
            self.log.error('praw.exceptions.APIException inside doer_logic')
            self.log.error(ex_msg)
            bot_queues[BotQueues.bot_queue_retry].put(item)
            time_to_sleep = BotUtil.try_get_seconds_to_wait(str(ex_msg))
            self.log.info(f'Waiting for {time_to_sleep} until next doer because reddit of api exception')
            time.sleep(time_to_sleep)


if __name__ == '__main__':
    bot = Bot()
    workers = [SubmissionKeywordWatcher(bot), CommentKeywordWatcher(bot), \
        KeywordFilter(bot), SubmissionKeywordDoer(bot), CommentKeywordDoer(bot)]    
    bot.add_worker(workers)
    bot.run()