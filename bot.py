"""Telegram Bot main app."""

import os
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, PollAnswerHandler

from config import (
    LOGS_DIR_PATH,
    MINIMUM_AGREE_MEMBERS_FOR_MOD,
    MOD_MANAGER_TIMEOUT,
    SERVER_CONFIG_DIRPATH,
    SERVER_NAME,
    TMUX_SESSION_NAME,
    ZOMBOID_START_SERVER_FILEPATH,
)
from zomboid_misc import ZomboidLogsAccessor, ZomboidModManager
from zomboid_misc.common_utils import rate_limit
from zomboid_misc.zomboid_session_manager import restart_session

load_dotenv()
polls = {}
log_accessor = ZomboidLogsAccessor(LOGS_DIR_PATH)
mod_manager = ZomboidModManager(SERVER_CONFIG_DIRPATH, SERVER_NAME, MOD_MANAGER_TIMEOUT)


@rate_limit(rate_limit_duration=220, max_calls=1, independent_call_limit=1)
async def restart_zomboid_server(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Restart zomboid server"""
    # Run the shell script and capture the return value

    # Access the output
    try:
        log_accessor.update_logs_map()
        active_players = log_accessor.get_active_players()
        restart_status = True

        # Display the return code and output
        print("[INFO] Current online player:", active_players)
        print("[INFO] Restart status:", restart_status)

        if active_players > 0:
            restart_status = False

        if restart_status:
            restart_session(TMUX_SESSION_NAME, ZOMBOID_START_SERVER_FILEPATH, SERVER_NAME)
            await update.message.reply_text(
                "Sedang merestart server ..\nMohon tunggu beberapa menit.",
                parse_mode=ParseMode.MARKDOWN,
            )
            time.sleep(210)
            await update.message.reply_text("Server telah *sukses di-restart*.", parse_mode=ParseMode.MARKDOWN)

        else:
            await update.message.reply_text(
                f"*Restart server ditolak*, terdapat {active_players} player di dalam server.",
                parse_mode=ParseMode.MARKDOWN,
            )
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Mohon beritahukan kepada pemain tersebut untuk *log out* sementara.",
                parse_mode=ParseMode.MARKDOWN,
            )

    except AttributeError:
        await update.message.reply_text("Gagal merestart, log tidak ditemukan.", parse_mode=ParseMode.MARKDOWN)


@rate_limit(rate_limit_duration=10, max_calls=5)
async def get_active_players(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Get active players"""
    active_players = log_accessor.get_active_players()

    # Access the output
    try:
        # Display the return code and output
        await update.message.reply_text(
            f"Terdapat {active_players} player yang sedang bermain di dalam server.",
            parse_mode=ParseMode.MARKDOWN,
        )
    except AttributeError:
        # Display the return code and output
        await update.message.reply_text(
            "Log tidak ditemukan, kemungkinan tidak ada player online.",
            parse_mode=ParseMode.MARKDOWN,
        )


@rate_limit(rate_limit_duration=100, max_calls=4)
async def add_mod(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles adding a mod and initiating a voting poll for approval.

    Args:
        update (Update): Incoming update object from Telegram.
        context (ContextTypes.DEFAULT_TYPE): Context object containing bot data, args, and job queue.

    Behavior:
        - Expects a single numeric mod ID passed as command arguments.
        - Validates the mod URL constructed from the mod ID.
        - Checks if the mod is already installed on the server.
        - If valid and not installed, sends a poll to the chat asking users to vote
          whether the mod should be added.
        - Starts a timer job to stop the poll after 1 hour.
        - Sends appropriate messages if the mod ID is invalid, already installed,
          or if the input is incorrect or missing.

    Usage:
        This function is typically used as a Telegram bot command handler.

    Example:
        @dp.message_handler(commands=["addmod"])
        async def add_mod_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await add_mod(update, context)
    """
    args = context.args
    if args:
        args = " ".join(args).strip()
        if args.isdigit():
            zomboid_workshop_url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={args}"
            zomboid_workshop_html = f'<a href="{zomboid_workshop_url}">Mod ID: {args}</a>'
            if not await mod_manager.validate_mod_url(zomboid_workshop_url):
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Mohon maaf, {zomboid_workshop_html} tidak valid.",
                    parse_mode=ParseMode.HTML,
                )
            elif await mod_manager.check_mod_installation(args):
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Mohon maaf, {zomboid_workshop_html} telah terinstall di dalam server.",
                    parse_mode=ParseMode.HTML,
                )
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Silahkan vote apakah MOD {zomboid_workshop_html} layak masuk server",
                    parse_mode=ParseMode.HTML,
                )

                questions = ["Setuju", "Tidak Setuju"]
                message = await context.bot.send_poll(
                    update.effective_chat.id,
                    "Gimana?",
                    questions,
                    is_anonymous=False,
                    allows_multiple_answers=False,
                )
                payload = {
                    message.poll.id: {
                        "questions": questions,
                        "message_id": message.message_id,
                        "chat_id": update.effective_chat.id,
                        "answers": 0,
                        "mod_url": zomboid_workshop_url,
                        "poll_end_time": datetime.now() + timedelta(seconds=3600),
                    }
                }
                # Init poll data
                polls[message.poll.id] = {}
                for option in questions:
                    polls[message.poll.id][option] = 0

                context.bot_data.update(payload)
                context.job_queue.run_once(
                    stop_poll_by_time,
                    timedelta(seconds=3600),
                    data=message.poll.id,
                    chat_id=update.effective_chat.id,
                    name="poll_stopper",
                )

        else:
            await update.message.reply_text("Mohon *tulis ID MOD saja*.", parse_mode=ParseMode.MARKDOWN)

    elif len(args) > 1:
        await update.message.reply_text("Mohon *tulis ID MOD saja*.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(
            "Mohon tuliskan ID MOD yang ingin ditambahkan.",
            parse_mode=ParseMode.MARKDOWN,
        )


async def stop_poll_by_time(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stops a poll when its time expires, announces the result, and initiates mod installation if approved.

    Args:
        context (ContextTypes.DEFAULT_TYPE): Context object containing job data, bot data, and bot instance.

    Behavior:
        - Checks if the poll's end time has passed.
        - Stops and deletes the poll message in the chat.
        - Counts votes for "Setuju" (agree) and "Tidak Setuju" (disagree).
        - If majority agrees, sends messages announcing approval and proceeds to
          fetch mod metadata, update configuration, and confirm addition.
        - Uses a 3-second delay between messages to improve readability.

    Usage:
        This function is intended to be scheduled as a job with `context.job_queue.run_once`
        to automatically stop the poll after a certain time period.
    """
    data = context.job.data
    answer_id = context.bot_data.get(data, {})
    chat_id = answer_id.get("chat_id")
    poll_message_id = answer_id.get("message_id")
    poll_end_time = answer_id.get("poll_end_time")

    if poll_end_time is not None and datetime.now() >= poll_end_time:
        await context.bot.stop_poll(
            chat_id,
            poll_message_id,
        )
        await context.bot.delete_message(chat_id=chat_id, message_id=poll_message_id)

        n_agree = polls[context.job.data]["Setuju"]
        n_disagree = polls[context.job.data]["Tidak Setuju"]

        if n_agree > n_disagree:
            await context.bot.send_message(
                answer_id["chat_id"],
                "Voting berakhir dan mayoritas menyetujui Mod tersebut!",
                parse_mode=ParseMode.HTML,
            )
            time.sleep(3)
            await context.bot.send_message(
                answer_id["chat_id"],
                "Mod akan diinstall!",
                parse_mode=ParseMode.HTML,
            )
            mod_metadata = await mod_manager.get_required_mod(answer_id["mod_url"])
            await context.bot.send_message(
                answer_id["chat_id"],
                " ".join(
                    [
                        "Berikut adalah Mod ID yang akan ditambahkan:\n\n",
                        "\n".join(mod_metadata.keys()).strip(),
                    ]
                ),
            )
            await mod_manager.add_to_config(mod_metadata)
            await context.bot.send_message(answer_id["chat_id"], "Mod berhasil ditambahkan.")


async def receive_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Summarize a users poll vote"""
    answer = update.poll_answer
    answered_poll = context.bot_data[answer.poll_id]
    try:
        questions = answered_poll["questions"]
    # this means this poll answer update is from an old poll, we can't do our answering then
    except KeyError:
        return

    selected_options = answer.option_ids
    answer_string = ""
    for question_id in selected_options:
        if question_id != selected_options[-1]:
            answer_string += questions[question_id] + " dan "
        else:
            answer_string += questions[question_id]

    polls[answer.poll_id][answer_string] += 1

    await context.bot.send_message(
        answered_poll["chat_id"],
        f"{update.effective_user.mention_html()} {answer_string.lower()}!",
        parse_mode=ParseMode.HTML,
    )
    answered_poll["answers"] += 1

    # Close poll after all participants voted
    if answered_poll["answers"] == MINIMUM_AGREE_MEMBERS_FOR_MOD:
        await context.bot.send_message(
            answered_poll["chat_id"],
            "Setengah dari anggota grub telah voting, polling akan ditutup 30 menit lagi!",
        )
        for job in context.job_queue.get_jobs_by_name("poll_stopper"):
            job.schedule_removal()

        context.bot_data[answer.poll_id]["poll_end_time"] = datetime.now() + timedelta(seconds=1800)

        context.job_queue.run_once(
            stop_poll_by_time,
            timedelta(seconds=1800),
            data=answer.poll_id,
            chat_id=answered_poll["chat_id"],
            name="poll_stopper",
        )

    elif answered_poll["answers"] == 5:
        await context.bot.stop_poll(
            answered_poll["chat_id"],
            answered_poll["message_id"],
        )
        await context.bot.delete_message(chat_id=answered_poll["chat_id"], message_id=answered_poll["message_id"])

        for job in context.job_queue.get_jobs_by_name("poll_stopper"):
            job.schedule_removal()

        n_agree = polls[answer.poll_id]["Setuju"]
        n_disagree = polls[answer.poll_id]["Tidak Setuju"]

        if n_agree > n_disagree:
            await context.bot.send_message(
                answered_poll["chat_id"],
                "Voting berakhir dan mayoritas menyetujui mod tersebut!",
                parse_mode=ParseMode.HTML,
            )
            time.sleep(3)
            await context.bot.send_message(
                answered_poll["chat_id"],
                "Mod akan diinstall!",
                parse_mode=ParseMode.HTML,
            )
            mod_metadata: dict = await mod_manager.get_required_mod(answered_poll["mod_url"])
            await context.bot.send_message(
                answered_poll["chat_id"],
                " ".join(
                    [
                        "Berikut adalah Mod ID yang akan ditambahkan:\n\n",
                        "\n".join(mod_metadata.keys()).strip(),
                    ]
                ),
            )
            await mod_manager.add_to_config(mod_metadata)
            await context.bot.send_message(answered_poll["chat_id"], "Mod berhasil ditambahkan.")

        else:
            await context.bot.send_message(
                answered_poll["chat_id"],
                "Voting berakhir dan mayoritas tidak menyetujui mod tersebut!",
                parse_mode=ParseMode.HTML,
            )


def run_bot() -> None:
    """Build and run bot."""
    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    application.add_handler(CommandHandler("restart_server", restart_zomboid_server))
    application.add_handler(CommandHandler("active_player", get_active_players))
    application.add_handler(CommandHandler("add_mod", add_mod))
    application.add_handler(PollAnswerHandler(receive_poll_answer))

    print("[INFO] Bot is running ..")
    application.run_polling()


if __name__ == "__main__":
    run_bot()
