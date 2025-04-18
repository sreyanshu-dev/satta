import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# === CONFIG ===
ADMIN_IDS = [6293126201 , 5460768109]
BOT_TOKEN = "ABCD"
DATA_FILE = "match_data.json"

# === LOGGING ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === STORAGE ===
try:
    with open(DATA_FILE, "r") as f:
        db = json.load(f)
except:
    db = {
        "matches": {},
        "user_teams": {},
        "points": {},
        "amounts": {}
    }

def save_db():
    with open(DATA_FILE, "w") as f:
        json.dump(db, f)

# === LOCK DICT ===
locked_matches = {}

# === ADMIN CHECK ===
def is_admin(user_id):
    return user_id in ADMIN_IDS

# === USER HELP COMMAND ===
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "User Commands\n\n"
        "Here are the commands you can use:\n"
        "/start - Start the bot and get a welcome message.\n"
        "/schedule - View available matches and select one to create/edit a team or place a bet.\n"
        "/team - Same as /schedule, view and manage your teams.\n"
        "/editteam [match_name] - Edit your team for a specific match (optional: specify match name).\n"
        "/addamount <match_name> <amount> - Set a bet amount for a match (e.g., /addamount LSGvsCSK 2000).\n"
        "/check - View your selected teams for all matches.\n"
        "/profile - View your teams and bet amounts.\n"
        "/rankings - See the current user rankings based on points.\n\n"
        "For admins, use /admhelp to see admin commands."
    )
    await update.message.reply_text(help_text)

# === ADMIN HELP COMMAND ===
async def admhelp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    help_text = (
        "Admin Commands\n\n"
        "Here are the commands available for admins:\n"
        "/admin - Open the admin panel to manage matches.\n"
        "/addmatch <match_name> - Add a new match (e.g., /addmatch LSGvsCSK).\n"
        "/addteam <match_name> <team_name> - Add a team to a match (e.g., /addteam LSGvsCSK LSG).\n"
        "/addplayer <match_name> <team_name> <players> - Add players to a team (e.g., /addplayer LSGvsCSK LSG Player1,Player2).\n"
        "/points <player> <points> - Assign points to a player (e.g., /points Player1 100).\n"
        "/lockmatch <match_name> - Lock a match to prevent team edits or bets (e.g., /lockmatch LSGvsCSK).\n"
        "/clear - Clear all data (use with caution!).\n"
        "/announcement <message> - Broadcast a message to users (e.g., /announcement Match starts soon!).\n\n"
        "Use /help to see user commands."
    )
    await update.message.reply_text(help_text)
    
# === USER COMMANDS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Hello {user.first_name}, welcome to the Cricket Team Selection Bot! "
        f"Use /schedule to get started, /profile to view your bets, or /help for commands."
    )

async def addamount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if len(context.args) < 2:
        keyboard = [[InlineKeyboardButton(m, callback_data=f"addamount::{m}")] for m in db["matches"].keys()]
        await update.message.reply_text("Select a match to set your bet amount:", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    match_name, amount = context.args[0], context.args[1]
    if match_name not in db["matches"]:
        await update.message.reply_text("Match not found.")
        return
    if locked_matches.get(match_name, False):
        await update.message.reply_text("❌ This match is locked. You can't place bets.")
        return
    try:
        amount = int(amount)
        if amount <= 0:
            await update.message.reply_text("Please enter a positive amount.")
            return
    except ValueError:
        await update.message.reply_text("Invalid amount. Please enter a number.")
        return
    db["amounts"].setdefault(user_id, {})[match_name] = amount
    save_db()
    await update.message.reply_text(
        f"Bet of {amount} points added for {match_name}. Please tag @Trainer_OFFicial in the group."
    )

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    msg = f"📋 *Your Profile* 📋\n\n"
    
    # Teams section
    if user_id not in db["user_teams"] or not db["user_teams"][user_id]:
        msg += "No teams selected yet.\n"
    else:
        msg += "Your Teams:\n"
        for match, players in db["user_teams"][user_id].items():
            msg += f"{match}:\n"
            for i, p in enumerate(players):
                role = " (Captain)" if i == 0 else " (Vice-Captain)" if i == 1 else ""
                msg += f"- {p}{role}\n"
            msg += "\n"
    
    # Bets section
    if user_id not in db["amounts"] or not db["amounts"][user_id]:
        msg += "No bets placed yet.\n"
    else:
        msg += "Your Bets:\n"
        for match, amount in db["amounts"][user_id].items():
            msg += f"{match}: {amount} points\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in db["user_teams"]:
        await update.message.reply_text("You haven't selected a team yet.")
        return
    msg = "Your teams:\n\n"
    for match, players in db["user_teams"][user_id].items():
        msg += f"{match}:\n"
        for i, p in enumerate(players):
            role = ""
            if i == 0:
                role = " (Captain)"
            elif i == 1:
                role = " (Vice-Captain)"
            msg += f"- {p}{role}\n"
        if user_id in db["amounts"] and match in db["amounts"][user_id]:
            msg += f"Bet: {db['amounts'][user_id][match]} points\n"
        msg += "\n"
    await update.message.reply_text(msg)

async def rankings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scores = {}
    for uid, matches in db["user_teams"].items():
        total = 0
        for m, players in matches.items():
            for i, p in enumerate(players):
                pt = db["points"].get(p, 0)
                if i == 0:
                    total += pt * 2  # Captain
                elif i == 1:
                    total += pt * 1.5  # Vice-captain
                else:
                    total += pt  # Normal player
        scores[uid] = total
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    msg = "Rankings:\n"
    for i, (uid, pts) in enumerate(sorted_scores, 1):
        msg += f"{i}. User {uid} - {int(pts)} pts\n"
    await update.message.reply_text(msg)

async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(m, callback_data=f"user_match_{m}")] for m in db["matches"].keys()]
    await update.message.reply_text("Select a match:", reply_markup=InlineKeyboardMarkup(keyboard))

async def team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await schedule(update, context)

# === ADMIN COMMANDS ===
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not an admin.")
        return
    keyboard = [[InlineKeyboardButton(m, callback_data=f"admin_match_{m}")] for m in db["matches"].keys()]
    await update.message.reply_text("Admin Panel - Matches:", reply_markup=InlineKeyboardMarkup(keyboard))

async def addmatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 1: return await update.message.reply_text("Usage: /addmatch match1")
    match = context.args[0]
    if match in db["matches"]:
        await update.message.reply_text("Match already exists.")
    else:
        db["matches"][match] = {"teams": {}, "players": []}
        save_db()
        await update.message.reply_text(f"Match {match} added.")

async def addteam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 2: return await update.message.reply_text("Usage: /addteam match1 teamname")
    match, team = context.args[0], context.args[1]
    if match not in db["matches"]: return await update.message.reply_text("Match not found.")
    db["matches"][match]["teams"][team] = []
    save_db()
    await update.message.reply_text(f"Team {team} added to {match}.")

async def addplayer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 3: return await update.message.reply_text("Usage: /addplayer match1 team (p1,p2)")
    match, team = context.args[0], context.args[1]
    try:
        player_str = " ".join(context.args[2:])
        players = [p.strip().strip("(),") for p in player_str.split(",")]
        db["matches"][match]["teams"][team].extend(players)
        db["matches"][match]["players"].extend(players)
        save_db()
        await update.message.reply_text(f"Players added to {team} in {match}: {', '.join(players)}")
    except:
        await update.message.reply_text("Failed to parse players.")

async def points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 2: return await update.message.reply_text("Usage: /points player 100")
    player = context.args[0]
    pts = int(context.args[1])
    db["points"][player] = pts
    save_db()
    await update.message.reply_text(f"{player} got {pts} points.")

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    db.clear()
    db.update({"matches": {}, "user_teams": {}, "points": {}, "amounts": {}})
    save_db()
    await update.message.reply_text("All data cleared.")

async def lock_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    if not context.args:
        await update.message.reply_text("Please provide the match name to lock. Example: /lockmatch LSGvsCSK")
        return
    match_name = context.args[0]
    locked_matches[match_name] = True
    await update.message.reply_text(f"✅ Match '{match_name}' has been locked. Users can no longer edit teams or place bets.")

async def announcement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    if not context.args:
        await update.message.reply_text("Please provide a message to announce. Example: /announcement Match LSGvsCSK starts soon!")
        return
    message = " ".join(context.args)
    await update.message.reply_text(f"📢 *Announcement*: {message}", parse_mode="Markdown")
    await update.message.reply_text("Announcement sent to the group.")

async def edit_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not context.args:
        keyboard = [[InlineKeyboardButton(m, callback_data=f"editteam::{m}")] for m in db["matches"].keys()]
        await update.message.reply_text("Select a match to edit your team:", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    match_name = context.args[0]
    if match_name not in db["matches"]:
        await update.message.reply_text("Match not found.")
        return
    if locked_matches.get(match_name, False):
        await update.message.reply_text("❌ This match is locked. You can't make changes.")
        return
    current_team = db["user_teams"].get(user_id, {}).get(match_name, [])
    if not current_team:
        await update.message.reply_text("You haven't selected a team for this match.")
        return
    keyboard = [
        [InlineKeyboardButton(player, callback_data=f"removeplayer::{match_name}::{player}")]
        for player in current_team
    ]
    keyboard.append([InlineKeyboardButton("Add Players", callback_data=f"create_{match_name}")])
    keyboard.append([InlineKeyboardButton("Clear Team", callback_data=f"clearteam::{match_name}")])
    keyboard.append([InlineKeyboardButton("Back", callback_data=f"back::{match_name}")])
    await update.message.reply_text(
        f"Edit your team for {match_name}:\n\n"
        f"Captain: {current_team[0] if current_team else 'N/A'}\n"
        f"Vice-Captain: {current_team[1] if len(current_team) > 1 else 'N/A'}\n"
        f"Players: {', '.join(current_team) if current_team else 'None'}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# === CALLBACK HANDLER ===
async def user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("admin_match_"):
        match = data.replace("admin_match_", "")
        keyboard = [
            [InlineKeyboardButton("Add Team", callback_data=f"admin_addteam_{match}")],
            [InlineKeyboardButton("Add Players", callback_data=f"admin_addplayer_{match}")]
        ]
        await query.edit_message_text(f"Admin Panel for {match}:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("user_match_"):
        match = data.replace("user_match_", "")
        keyboard = [
            [InlineKeyboardButton("Create Team", callback_data=f"create_{match}")],
            [InlineKeyboardButton("Edit Team", callback_data=f"editteam::{match}")],
            [InlineKeyboardButton("Add Bet", callback_data=f"addamount::{match}")]
        ]
        await query.edit_message_text(f"Match: {match}", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("addamount::"):
        match = data.replace("addamount::", "")
        if match not in db["matches"]:
            await query.edit_message_text("Match not found.")
            return
        if locked_matches.get(match, False):
            await query.answer("❌ This match is locked. You can't place bets.", show_alert=True)
            return
        await query.edit_message_text(
            f"Please set your bet for {match} using the command:\n"
            f"/addamount {match} <amount>\n"
            f"Example: /addamount {match} 2000"
        )

    elif data.startswith("editteam::"):
        match = data.replace("editteam::", "")
        user_id = str(query.from_user.id)
        if locked_matches.get(match, False):
            await query.answer("❌ This match is locked. You can't make changes.", show_alert=True)
            return
        current_team = db["user_teams"].get(user_id, {}).get(match, [])
        if not current_team:
            await query.edit_message_text("You haven't selected a team for this match.")
            return
        keyboard = [
            [InlineKeyboardButton(player, callback_data=f"removeplayer::{match}::{player}")]
            for player in current_team
        ]
        keyboard.append([InlineKeyboardButton("Add Players", callback_data=f"create_{match}")])
        keyboard.append([InlineKeyboardButton("Clear Team", callback_data=f"clearteam::{match}")])
        keyboard.append([InlineKeyboardButton("Back", callback_data=f"back::{match}")])
        await query.edit_message_text(
            f"Edit your team for {match}:\n\n"
            f"Captain: {current_team[0] if current_team else 'N/A'}\n"
            f"Vice-Captain: {current_team[1] if len(current_team) > 1 else 'N/A'}\n"
            f"Players: {', '.join(current_team) if current_team else 'None'}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("create_"):
        match = data.replace("create_", "")
        if locked_matches.get(match, False):
            await query.answer("❌ This match is locked. You can't make changes.", show_alert=True)
            return
        db["user_teams"].setdefault(str(query.from_user.id), {}).setdefault(match, [])
        keyboard = []
        for team, players in db["matches"][match]["teams"].items():
            keyboard.append([InlineKeyboardButton(f"{team}", callback_data=f"selectteam::{match}::{team}")])
        await query.edit_message_text("Choose team to select players:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("selectteam::"):
        _, match, team = data.split("::")
        if locked_matches.get(match, False):
            await query.answer("❌ This match is locked. You can't make changes.", show_alert=True)
            return
        players = db["matches"][match]["teams"].get(team, [])
        if not players:
            await query.edit_message_text(f"No players available for team {team}.")
            return
        keyboard = [
            [InlineKeyboardButton(player, callback_data=f"selectplayer::{match}::{team}::{player}")]
            for player in players
        ]
        keyboard.append([InlineKeyboardButton("Back", callback_data=f"back::{match}")])
        await query.edit_message_text(f"Select players from {team}:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("selectplayer::"):
        _, match, team, player = data.split("::")
        if locked_matches.get(match, False):
            await query.answer("❌ This match is locked. You can't make changes.", show_alert=True)
            return
        user_teams = db["user_teams"].setdefault(str(query.from_user.id), {}).setdefault(match, [])
        if len(user_teams) < 11 and player not in user_teams:
            user_teams.append(player)
            save_db()
            await query.edit_message_text(f"{player} added to your team. ({len(user_teams)}/11)")
        else:
            await query.answer("Cannot add player. Team is full or player already added.", show_alert=True)

    elif data.startswith("removeplayer::"):
        _, match, player = data.split("::")
        if locked_matches.get(match, False):
            await query.answer("❌ This match is locked. You can't make changes.", show_alert=True)
            return
        user_id = str(query.from_user.id)
        user_team = db["user_teams"].get(user_id, {}).get(match, [])
        if player in user_team:
            user_team.remove(player)
            save_db()
            current_team = db["user_teams"].get(user_id, {}).get(match, [])
            if not current_team:
                await query.edit_message_text("Your team is now empty.")
                return
            keyboard = [
                [InlineKeyboardButton(p, callback_data=f"removeplayer::{match}::{p}")]
                for p in current_team
            ]
            keyboard.append([InlineKeyboardButton("Add Players", callback_data=f"create_{match}")])
            keyboard.append([InlineKeyboardButton("Clear Team", callback_data=f"clearteam::{match}")])
            keyboard.append([InlineKeyboardButton("Back", callback_data=f"back::{match}")])
            await query.edit_message_text(
                f"Edit your team for {match}:\n\n"
                f"Captain: {current_team[0] if current_team else 'N/A'}\n"
                f"Vice-Captain: {current_team[1] if len(current_team) > 1 else 'N/A'}\n"
                f"Players: {', '.join(current_team) if current_team else 'None'}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text(f"{player} was not in your team.")

    elif data.startswith("clearteam::"):
        match = data.replace("clearteam::", "")
        if locked_matches.get(match, False):
            await query.answer("❌ This match is locked. You can't make changes.", show_alert=True)
            return
        user_id = str(query.from_user.id)
        db["user_teams"].get(user_id, {}).pop(match, None)
        save_db()
        await query.edit_message_text(f"Your team for {match} has been cleared.")

    elif data.startswith("back::"):
        match = data.replace("back::", "")
        keyboard = [
            [InlineKeyboardButton("Create Team", callback_data=f"create_{match}")],
            [InlineKeyboardButton("Edit Team", callback_data=f"editteam::{match}")],
            [InlineKeyboardButton("Add Bet", callback_data=f"addamount::{match}")]
        ]
        await query.edit_message_text(f"Match: {match}", reply_markup=InlineKeyboardMarkup(keyboard))

# === MAIN FUNCTION ===
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("admhelp", admhelp))
    application.add_handler(CommandHandler("schedule", schedule))
    application.add_handler(CommandHandler("team", team))
    application.add_handler(CommandHandler("addmatch", addmatch))
    application.add_handler(CommandHandler("addteam", addteam))
    application.add_handler(CommandHandler("addplayer", addplayer))
    application.add_handler(CommandHandler("points", points))
    application.add_handler(CommandHandler("clear", clear))
    application.add_handler(CommandHandler("lockmatch", lock_match))
    application.add_handler(CommandHandler("announcement", announcement))
    application.add_handler(CommandHandler("rankings", rankings))
    application.add_handler(CommandHandler("check", check))
    application.add_handler(CommandHandler("editteam", edit_team))
    application.add_handler(CommandHandler("addamount", addamount))
    application.add_handler(CommandHandler("profile", profile))

    # Callback Handler
    application.add_handler(CallbackQueryHandler(user_callback))

    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()