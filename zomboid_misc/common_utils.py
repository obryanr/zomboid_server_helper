"""Zomboid common utilities."""

import re
import time
from datetime import date, datetime
from functools import wraps
from typing import Callable, Optional, Union

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes


def extract_datetime_from_file(
    input_str: str, date_format: str = "%d-%m-%y", time_format: str = "%H-%M-%S"
) -> Union[datetime, date, None]:
    """Extracts a datetime or date object from a string that contains a formatted date/time.

    Args:
        input_str (str): The string to search for a datetime pattern.
        date_format (str, optional): Format of the date. Defaults to "%d-%m-%y".
        time_format (str, optional): Format of the time. Defaults to "%H-%M-%S".

    Returns:
        Union[datetime, date, None]: Parsed datetime or date object if found; None otherwise.
    """
    datetime_pattern = re.compile(r"(\d{2}-\d{2}-\d{2})(?:_(\d{2}-\d{2}-\d{2}))?")
    match = datetime_pattern.search(input_str)

    if match:
        date_part = match.group(1)
        time_part = match.group(2) if match.lastindex and match.lastindex >= 2 else None

        try:
            if time_part:
                return datetime.strptime(f"{date_part}_{time_part}", f"{date_format}_{time_format}")
            return datetime.strptime(date_part, date_format).date()
        except ValueError:
            return None
    return None


def rate_limit(rate_limit_duration: int, max_calls: int, independent_call_limit: Optional[int] = None) -> Callable:
    """A decorator to rate limit calls to an async function, typically a Telegram bot handler.

    This decorator limits how many times a user can call the decorated function within
    a specified time window (`rate_limit_duration` seconds). It also supports an optional
    global call limit (`independent_call_limit`) shared across all users.

    Args:
        rate_limit_duration (int): Time window in seconds during which calls are counted.
        max_calls (int): Maximum allowed calls per user within the time window.
        independent_call_limit (int, optional): Maximum allowed calls globally (across all users)
            within the time window. Defaults to None (no global limit).

    Returns:
        Callable: The decorated async function with rate limiting applied.

    Raises:
        None: Instead of raising exceptions, the decorator sends messages to the user
            notifying them when the rate limit is exceeded.

    Behavior:
        - Tracks calls per user and rejects calls exceeding `max_calls` within the time window.
        - If `independent_call_limit` is set, tracks combined calls and rejects if limit exceeded,
          notifying the user which user triggered the limit and remaining wait time.
        - Resets counters after `rate_limit_duration` seconds.

    Example:
        @rate_limit(rate_limit_duration=60, max_calls=5, independent_call_limit=10)
        async def handler(update, context):
            ...
    """

    def decorator(
        func: Callable[[Update, ContextTypes.DEFAULT_TYPE], None],
    ) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], None]:
        """Decorator to apply rate limiting on a Telegram bot command handler function.

        This decorator enforces two levels of rate limiting for asynchronous handler functions:

        1. **Per-user limit:** Limits how many times each user can invoke the command within a time window.
        2. **Independent call limit:** Limits how many total calls can be made independently of users,
        preventing command flooding globally.

        Args:
            func (Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]):
                The async command handler function to be wrapped and rate-limited.

        Returns:
            Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]:
                The wrapped async function with rate limiting applied.

        Behavior:
            - Maintains a dictionary `rate_limit_data` to track call counts and timestamps per user and globally.
            - Resets counts when the rate limit duration expires.
            - If the call count exceeds the allowed max within the duration, the call is rejected with an informative message.
            - Sends messages to the user when their rate limit or the global independent call limit is reached,
            indicating how many seconds remain before they can call again.
            - Calls the original function if limits are not exceeded.
            - Updates the call count and timestamp after each successful call.

        Notes:
            - Assumes the wrapped function is an async handler that takes `update` and `context` arguments.
            - Uses `update.message.from_user.username` to identify the global caller for independent call limit messages.
            - Uses `update.effective_user.id` to identify individual users for per-user limits.
            - `rate_limit_duration`, `max_calls`, and `independent_call_limit` are expected to be in the enclosing scope.

        Example:
            ```python
            @rate_limit_decorator
            async def my_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
                # handler logic here
                pass
            ```
        """
        rate_limit_data = {}

        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            """Wrapper function enforcing rate limits before executing the handler.

            Args:
                update (Update): Incoming Telegram update.
                context (ContextTypes.DEFAULT_TYPE): Context for the callback, including bot and user info.

            Returns:
                None or sends a rate-limit warning message and returns early if limits are exceeded.

            Raises:
                None explicitly, but calls to bot methods are awaited and exceptions should be handled upstream.
            """
            nonlocal rate_limit_data

            if "independent_call" in rate_limit_data:
                elapsed_time = time.time() - rate_limit_data["independent_call"]["timestamp"]

                # Reset the rate limit data if time elapsed is greater than rate_limit_duration
                if elapsed_time > rate_limit_duration:
                    rate_limit_data["independent_call"] = {
                        "count": 0,
                        "timestamp": time.time(),
                        "from_user": update.message.from_user.username,
                    }
                elif rate_limit_data["independent_call"]["count"] >= independent_call_limit:
                    caller = rate_limit_data["independent_call"]["from_user"]
                    remaining_time = int(
                        rate_limit_duration - (time.time() - rate_limit_data["independent_call"]["timestamp"])
                    )
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"Permintaan ditolak karena *telah dilakukan oleh {caller}*.\nFungsi ini akan bekerja {remaining_time} detik lagi.",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    return

            user_id = update.effective_user.id

            # Check if the user has previous rate limit data
            if user_id in rate_limit_data:
                elapsed_time = time.time() - rate_limit_data[user_id]["timestamp"]

                # Reset the rate limit data if time elapsed is greater than rate_limit_duration
                if elapsed_time > rate_limit_duration:
                    rate_limit_data[user_id] = {"count": 0, "timestamp": time.time()}
                elif rate_limit_data[user_id]["count"] >= max_calls:
                    remaining_time = int(rate_limit_duration - (time.time() - rate_limit_data[user_id]["timestamp"]))
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"Telah mencapai batas pemanggilan. Mohon tunggu {remaining_time} detik lagi.",
                    )
                    return

            # Execute the function
            await func(update, context)

            # Update rate limiting data
            if user_id in rate_limit_data:
                rate_limit_data[user_id]["count"] += 1
            else:
                rate_limit_data[user_id] = {"count": 1, "timestamp": time.time()}

            if independent_call_limit is not None:
                if "independent_call" in rate_limit_data:
                    rate_limit_data["independent_call"]["count"] += 1
                else:
                    rate_limit_data["independent_call"] = {
                        "count": 1,
                        "timestamp": time.time(),
                        "from_user": update.message.from_user.username,
                    }

        return wrapper

    return decorator
