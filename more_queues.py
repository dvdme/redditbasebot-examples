from enum import Enum
from redditbasebot.bot_queues import bot_queues, BotQueues, add_new_queue

class MoreBotQueues:
    comment_filtered = 0
    submission_filtered = 1

add_new_queue(MoreBotQueues.comment_filtered)
add_new_queue(MoreBotQueues.submission_filtered)
