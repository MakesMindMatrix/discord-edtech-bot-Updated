"""
Migration script: Create Discord channels and assign verified students.
Run LOCALLY first, then upload updated DB + code to VM.

Prerequisite: Run import_csv.py with CSV that has Groups column (G1–G5).

Usage:
    - Automatically runs when main.py bot starts (once)
    - Automatically runs after import_csv.py loads students
    - Standalone: python create_sub_batches.py

What it does:
    - Reads verified students with group_id from DB (G1, G2, G3, G4, G5)
    - Creates group ROLES (e.g. VTU-Ascenders-G1)
    - Category: "{University} Project Discussion"
    - Channel: vtu-ascenders-g1 (with role-based access)
    - Assigns group role to each verified student

Logs: logs/create_sub_batches.log (and console)
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

import discord
import aiosqlite

from database import DB_PATH, init_database

GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))

# Setup logging (only when run standalone; main.py may have its own)
def _setup_logging():
    LOG_DIR = Path(__file__).resolve().parent / "logs"
    LOG_DIR.mkdir(exist_ok=True)
    LOG_FILE = LOG_DIR / "create_sub_batches.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

log = logging.getLogger("create_sub_batches")


def make_channel_name(university: str, batch: str, group_id: str) -> str:
    """Format: UNIVERSITY-BATCH-GROUP (e.g. vtu-ascenders-g1). Handles empty university."""
    b = (batch or "").upper().replace(" ", "-")
    g = (str(group_id or "").upper().replace(" ", "-"))
    if not b or not g:
        return ""
    u = (university or "").upper().replace(" ", "-")
    return f"{u}-{b}-{g}".lower() if u else f"{b}-{g}".lower()


def make_role_name(university: str, batch: str, group_id: str) -> str:
    """Format: University-Batch-Group (e.g. VTU-Ascenders-G1). Handles empty university."""
    b = (batch or "").strip().replace(" ", "-")
    g = (str(group_id or "").strip().upper().replace(" ", "-"))
    if not b or not g:
        return ""
    u = (university or "").strip().replace(" ", "-")
    return f"{u}-{b}-{g}" if u else f"{b}-{g}"


async def migrate_groups(bot: discord.Client):
    """Create channels and assign verified students based on group_id."""
    log.info("migrate_groups: starting")
    guild = bot.get_guild(GUILD_ID) if GUILD_ID else (next(iter(bot.guilds), None) if bot.guilds else None)
    if not guild:
        log.error("No guild found. Set DISCORD_GUILD_ID in .env or ensure bot is in a server.")
        log.debug("GUILD_ID=%s, bot.guilds=%s", GUILD_ID, [g.id for g in bot.guilds] if bot.guilds else [])
        return

    log.info("Running migration on: %s (ID: %s)", guild.name, guild.id)
    log.info("Loading verified students with group_id from DB...")

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                SELECT email, discord_id, COALESCE(university, ''), course, COALESCE(batch, ''), group_id
                FROM students
                WHERE is_verified = 1 AND discord_id IS NOT NULL AND group_id IS NOT NULL AND group_id != ''
            """)
            rows = await cursor.fetchall()
    except Exception as e:
        log.exception("Failed to query database: %s", e)
        raise

    log.info("Students with group_id: %d", len(rows))
    if len(rows) == 0:
        log.warning("No students found. Run import_csv.py with Groups column (G1–G5) first.")

    # Group by (university, course, batch) for category/channel creation
    batches = defaultdict(list)
    skipped = 0
    for email, discord_id, university, course, batch, group_id in rows:
        if not course or not batch or not group_id:
            skipped += 1
            continue
        batches[(university, course, batch)].append((email, discord_id, str(group_id).strip().upper()))
    if skipped:
        log.debug("Skipped %d rows (missing course/batch/group_id)", skipped)
    log.info("Batches to process: %d", len(batches))

    total_roles = 0
    total_channels = 0
    total_assignments = 0

    for idx, ((university, course, batch), students) in enumerate(batches.items()):
        log.info("[%d/%d] Processing: university=%r, course=%r, batch=%r, students=%d",
                 idx + 1, len(batches), university or "(empty)", course, batch, len(students))
        # Category: "{University} Project Discussion"
        category_name = f"{university} Project Discussion" if university else "Project Discussion"

        # Get or create category
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            try:
                category = await guild.create_category(
                    name=category_name,
                    overwrites={
                        guild.default_role: discord.PermissionOverwrite(view_channel=False),
                        guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True),
                    },
                    reason="Migration: Sub-batch groups",
                )
                log.info("Created category: %s", category_name)
            except discord.Forbidden as e:
                log.error("Cannot create category %s: %s", category_name, e)
                continue

        # Get unique group_ids (G1, G2, G3, G4, G5)
        group_ids = sorted(set(g.upper() for _, _, g in students))
        roles = {}

        for group_id in group_ids:
            role_name = make_role_name(university, batch, group_id)
            if not role_name:
                log.debug("Skipping empty role_name for group_id=%s", group_id)
                continue
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                try:
                    role = await guild.create_role(
                        name=role_name,
                        mentionable=True,
                        reason=f"Migration: group {group_id} for {batch}",
                    )
                    total_roles += 1
                    log.info("Created role: %s", role_name)
                except discord.Forbidden as e:
                    log.error("Cannot create role %s: %s", role_name, e)
                    continue

            # Create channel with role permission (handle 50-channel-per-category limit)
            channel_name = make_channel_name(university, batch, group_id)
            channel = discord.utils.get(guild.text_channels, name=channel_name, category=category)
            if not channel:
                channel = discord.utils.get(guild.text_channels, name=channel_name)
            if not channel:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                    guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True),
                }
                categories_to_try = [c for c in guild.categories if c.name.startswith(category_name) and len(c.channels) < 50]
                if not categories_to_try:
                    categories_to_try = [category]
                for idx in range(2, 20):
                    fallback_name = f"{category_name} {idx}"
                    fc = discord.utils.get(guild.categories, name=fallback_name)
                    if fc and len(fc.channels) < 50 and fc not in categories_to_try:
                        categories_to_try.append(fc)
                        break
                    if not fc:
                        try:
                            fc = await guild.create_category(
                                name=fallback_name,
                                overwrites={
                                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                                    guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True),
                                },
                                reason="Migration: 50-channel limit fallback",
                            )
                            categories_to_try.append(fc)
                            break
                        except discord.Forbidden:
                            break
                for cat in categories_to_try:
                    try:
                        channel = await guild.create_text_channel(
                            name=channel_name,
                            category=cat,
                            overwrites=overwrites,
                            topic=f"Discussion group {group_id} for {batch} batch",
                        )
                        total_channels += 1
                        log.info("Created channel: #%s (in %s)", channel_name, cat.name)
                        break
                    except discord.Forbidden as e:
                        log.error("Cannot create channel %s: %s", channel_name, e)
                        break
                    except discord.HTTPException as e:
                        if "50" in str(e) or "maximum number of channels" in str(e).lower():
                            continue
                        raise

            roles[group_id.upper()] = role

        # Assign group role to each student
        members_not_found = 0
        for email, discord_id, group_id in students:
            gid = group_id.upper()
            role = roles.get(gid)
            if not role:
                continue

            member = guild.get_member(int(discord_id))
            if member:
                try:
                    await member.add_roles(role, reason="Migration: group assignment")
                    total_assignments += 1
                except discord.Forbidden as e:
                    log.warning("Forbidden adding role %s to %s: %s", role.name, email, e)
            else:
                members_not_found += 1
        if members_not_found:
            log.debug("Members not in guild for this batch: %d", members_not_found)

        await asyncio.sleep(1)  # Rate limit: 1s per batch

    log.info("=" * 50)
    log.info("Migration complete!")
    log.info("  Students processed: %d", len(rows))
    log.info("  Roles created: %d", total_roles)
    log.info("  Channels created: %d", total_channels)
    log.info("  Role assignments: %d", total_assignments)
    log.info("=" * 50)


async def run_migrate_standalone():
    """Run migration with a standalone bot (for import_csv or CLI). Connects, migrates, exits."""
    _setup_logging()
    log.info("create_sub_batches: starting (standalone)")
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        log.error("DISCORD_TOKEN not found in .env")
        return

    log.info("Initializing database...")
    try:
        await init_database()
        log.info("Database OK (path=%s)", DB_PATH)
    except Exception as e:
        log.exception("Database init failed: %s", e)
        raise

    log.info("GUILD_ID=%s (from DISCORD_GUILD_ID)", GUILD_ID)
    intents = discord.Intents.default()
    intents.members = True
    intents.guilds = True

    bot = discord.Client(intents=intents)

    @bot.event
    async def on_ready():
        log.info("Bot connected: %s (id=%s), guilds=%s",
                 bot.user, bot.user.id if bot.user else None, [g.name for g in bot.guilds])
        try:
            await migrate_groups(bot)
        except Exception as e:
            log.exception("migrate_groups failed: %s", e)
            raise
        finally:
            await bot.close()

    try:
        log.info("Connecting to Discord...")
        await bot.start(token)
        log.info("create_sub_batches: finished normally")
    except discord.LoginFailure as e:
        log.error("Discord login failed (check DISCORD_TOKEN): %s", e)
        raise
    except Exception as e:
        log.exception("Unexpected error: %s", e)
        raise


if __name__ == "__main__":
    _setup_logging()
    try:
        asyncio.run(run_migrate_standalone())
    except KeyboardInterrupt:
        log.info("Interrupted by user")
    except Exception as e:
        log.exception("Fatal: %s", e)
        sys.exit(1)
