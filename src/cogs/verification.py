"""
Verification Cog for Discord Mind Matrix Bot
Handles /verify and /otp commands with email OTP verification
Supports automatic Role & Channel creation for University/Course/Batch system

CSV Format (5 columns):
    - Column 1: Name
    - Column 2: Email id
    - Column 3: University (e.g., "VTU" or "GTU")
    - Column 4: Course (becomes Category name, e.g., "Android App Development")
    - Column 5: Batch name (becomes Batch role name, e.g., "Nomads")

Structure created per university:
    VTU - Android App Development (Category)
        #vtu-android-app-development-announcements
        #vtu-android-app-development-discussion
        #vtu-nomads-official (batch-specific)
"""

import os
import re
import random
import string
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import discord
from discord import app_commands
from discord.ext import commands
import aiosmtplib
from dotenv import load_dotenv

import config
from database import db, init_database

load_dotenv()
logger = logging.getLogger("verification")


class Verification(commands.Cog):
    """Cog for handling student email verification"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.otp_cooldowns = {}  # Track OTP request cooldowns
    
    async def cog_load(self):
        """Called when the cog is loaded - initialize database"""
        await init_database()
        logger.info("Verification cog loaded and database initialized")
    
    # ============================================
    # HELPER: AUTO-CREATE COURSE RESOURCES (Category + Shared Channels)
    # ============================================
    async def ensure_course_resources(self, guild: discord.Guild, university: str, course_name: str) -> tuple[discord.Role, discord.CategoryChannel]:
        """
        Ensures the Course Role and Category with shared channels exist.
        Now includes university prefix for organization.
        
        CSV: university = "VTU", course = "Android App Development"
        Creates (if not exists):
            - Role: "VTU-Android App Development Intern"
            - Category: "VTU - Android App Development"
                - #announcements-vtu-android-app-development (read-only for students)
                - #discussions-vtu-android-app-development (all students can chat)
        
        Returns:
            tuple: (course_role, category) or (None, None) on error
        """
        if not course_name:
            return (None, None)
        
        # Build names with university prefix if provided
        if university:
            course_role_name = f"{university}-{course_name} Intern"
            category_name = f"{university} - {course_name}"
            channel_prefix = f"{university.lower()}-{course_name.lower().replace(' ', '-')}"
        else:
            course_role_name = f"{course_name} Intern"
            category_name = course_name
            channel_prefix = course_name.lower().replace(" ", "-")
        
        # 1. Get or Create COURSE ROLE
        course_role = discord.utils.get(guild.roles, name=course_role_name)
        if not course_role:
            try:
                course_role = await guild.create_role(
                    name=course_role_name,
                    mentionable=True,
                    reason=f"Auto-created by Mind Matrix Bot for {university} - {course_name}" if university else f"Auto-created by Mind Matrix Bot for {course_name}"
                )
                logger.info(f"✅ Created Course Role: {course_role_name}")
            except discord.Forbidden:
                logger.error(f"❌ Missing Permissions: Cannot create role '{course_role_name}'")
                return (None, None)
        
        # 2. Get or Create CATEGORY
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            try:
                # Category permissions: Hidden from @everyone, visible to Course Role
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    course_role: discord.PermissionOverwrite(view_channel=True),
                    guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True)
                }
                category = await guild.create_category(
                    name=category_name,
                    overwrites=overwrites,
                    reason=f"Auto-created by Mind Matrix Bot for {university} - {course_name}" if university else f"Auto-created by Mind Matrix Bot for {course_name}"
                )
                logger.info(f"✅ Created Category: {category_name}")
            except discord.Forbidden:
                logger.error(f"❌ Missing Permissions: Cannot create category '{category_name}'")
                return (course_role, None)
        
        # 3. Create SHARED CHANNELS inside the Category
        announcement_channel_name = f"announcements-{channel_prefix}"
        discussion_channel_name = f"discussions-{channel_prefix}"
        
        # 3a. Announcements Channel (Students can view, only Admin can send)
        announcement_channel = discord.utils.get(guild.text_channels, name=announcement_channel_name, category=category)
        if not announcement_channel:
            try:
                announcement_overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    course_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),  # Read-only
                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                }
                await guild.create_text_channel(
                    name=announcement_channel_name,
                    category=category,
                    overwrites=announcement_overwrites,
                    topic=f"📢 Official announcements for {university} - {course_name}. Only admins can post." if university else f"📢 Official announcements for {course_name}. Only admins can post."
                )
                logger.info(f"✅ Created Channel: #{announcement_channel_name}")
            except discord.Forbidden:
                logger.error(f"❌ Missing Permissions: Cannot create channel '{announcement_channel_name}'")
        
        # 3b. Discussion Channel (All students can chat)
        discussion_channel = discord.utils.get(guild.text_channels, name=discussion_channel_name, category=category)
        if not discussion_channel:
            try:
                discussion_overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    course_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                }
                await guild.create_text_channel(
                    name=discussion_channel_name,
                    category=category,
                    overwrites=discussion_overwrites,
                    topic=f"💬 Discussion forum for all {university} - {course_name} students" if university else f"💬 Discussion forum for all {course_name} students"
                )
                logger.info(f"✅ Created Channel: #{discussion_channel_name}")
            except discord.Forbidden:
                logger.error(f"❌ Missing Permissions: Cannot create channel '{discussion_channel_name}'")
        
        return (course_role, category)
    
    # ============================================
    # HELPER: AUTO-CREATE BATCH RESOURCES (Batch Role + Private Channel)
    # ============================================
    async def ensure_batch_resources(self, guild: discord.Guild, university: str, course_name: str, batch_name: str, category: discord.CategoryChannel) -> discord.Role:
        """
        Ensures the Batch-specific Role and Channel exist.
        Now includes university prefix for organization.
        
        CSV: university = "VTU", course = "Android App Development", batch = "Nomads"
        Creates (if not exists):
            - Role: "VTU-Nomads"
            - Channel: #vtu-nomads-official (inside the Course Category)
        
        Returns:
            discord.Role or None on error
        """
        if not batch_name:
            return None
        
        # Build names with university prefix if provided
        if university:
            batch_role_name = f"{university}-{batch_name}"
            channel_name = f"{university.lower()}-{batch_name.lower().replace(' ', '-')}-official"
        else:
            batch_role_name = batch_name
            channel_name = f"{batch_name.lower().replace(' ', '-')}-official"
        
        # 1. Get or Create BATCH ROLE
        batch_role = discord.utils.get(guild.roles, name=batch_role_name)
        if not batch_role:
            try:
                batch_role = await guild.create_role(
                    name=batch_role_name,
                    mentionable=True,
                    reason=f"Auto-created by Mind Matrix Bot for {university} batch {batch_name}" if university else f"Auto-created by Mind Matrix Bot for batch {batch_name}"
                )
                logger.info(f"✅ Created Batch Role: {batch_role_name}")
            except discord.Forbidden:
                logger.error(f"❌ Missing Permissions: Cannot create role '{batch_role_name}'")
                return None
        
        # 2. Get or Create BATCH-SPECIFIC CHANNEL
        batch_channel = discord.utils.get(guild.text_channels, name=channel_name)
        
        if not batch_channel and category:
            try:
                # Channel visible only to this specific batch
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    batch_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                }
                await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites,
                    topic=f"🔒 Private channel for {university} - {batch_name} batch only" if university else f"🔒 Private channel for {batch_name} batch only"
                )
                logger.info(f"✅ Created Batch Channel: #{channel_name}")
            except discord.Forbidden:
                logger.error(f"❌ Missing Permissions: Cannot create channel '{channel_name}'")
        
        return batch_role
    
    # ============================================
    # HELPER: GROUP CATEGORY & CHANNEL (Sub-batches of ~100 students)
    # ============================================
    def _batch_to_slug(self, batch_name: str) -> str:
        """Convert batch name to channel-safe slug (e.g., 'Nomads' -> 'nomads')"""
        return (batch_name or "").lower().replace(" ", "-")
    
    def _group_channel_name(self, university: str, batch: str, group_id: str) -> str:
        """Format: UNIVERSITY-BATCH-GROUP (e.g. vtu-ascenders-g1). Handles empty university."""
        b = (batch or "").upper().replace(" ", "-")
        g = (str(group_id or "").upper().replace(" ", "-"))
        if not b or not g:
            return ""
        u = (university or "").upper().replace(" ", "-")
        return f"{u}-{b}-{g}".lower() if u else f"{b}-{g}".lower()

    def _group_role_name(self, university: str, batch: str, group_id: str) -> str:
        """Format: University-Batch-Group (e.g. VTU-Ascenders-G1). Handles empty university."""
        b = (batch or "").strip().replace(" ", "-")
        g = (str(group_id or "").strip().upper().replace(" ", "-"))
        if not b or not g:
            return ""
        u = (university or "").strip().replace(" ", "-")
        return f"{u}-{b}-{g}" if u else f"{b}-{g}"

    async def ensure_group_role(self, guild: discord.Guild, university: str, batch: str, group_id: str) -> Optional[discord.Role]:
        """Get or create group role (e.g. VTU-Ascenders-G1)."""
        role_name = self._group_role_name(university, batch, group_id)
        if not role_name:
            return None
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            try:
                role = await guild.create_role(
                    name=role_name,
                    mentionable=True,
                    reason=f"Auto-created group role for {university} {batch} {group_id}"
                )
                logger.info(f"✅ Created Group Role: {role_name}")
            except discord.Forbidden:
                logger.error(f"❌ Cannot create role {role_name}")
                return None
        return role

    async def ensure_group_category(
        self, guild: discord.Guild, university: str, course_name: str, fallback_index: int = 0
    ) -> Optional[discord.CategoryChannel]:
        """
        Ensures the Project Discussion category exists.
        Base: "{University} Project Discussion". Fallback when full: "... 2", "... 3", etc.
        Discord limit: 50 channels per category.
        """
        base = f"{university} Project Discussion" if university else "Project Discussion"
        category_name = f"{base} {fallback_index}" if fallback_index > 0 else base
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            try:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True)
                }
                category = await guild.create_category(
                    name=category_name,
                    overwrites=overwrites,
                    reason=f"Auto-created Project Discussion category for {university}"
                )
                logger.info(f"✅ Created Group Category: {category_name}")
            except discord.Forbidden:
                logger.error(f"❌ Missing Permissions: Cannot create category '{category_name}'")
                return None
        return category

    def _get_category_with_space(self, guild: discord.Guild, university: str) -> Optional[discord.CategoryChannel]:
        """Find a Project Discussion category with < 50 channels, or return None to create new."""
        base = f"{university} Project Discussion" if university else "Project Discussion"
        for cat in guild.categories:
            if cat.name == base or (cat.name.startswith(base + " ") and cat.name[len(base) + 1:].isdigit()):
                if len(cat.channels) < 50:
                    return cat
        return None
    
    async def ensure_group_channel(
        self,
        guild: discord.Guild,
        group_category: discord.CategoryChannel,
        university: str,
        batch_name: str,
        group_id: str,
        group_role: discord.Role
    ) -> Optional[discord.TextChannel]:
        """
        Get or create group channel with role-based access.
        Channel name: {UNIVERSITY}-{BATCH}-{GROUP} (e.g., vtu-ascenders-g1)
        Handles Discord 50-channel-per-category limit by using fallback categories.
        """
        channel_name = self._group_channel_name(university, batch_name, group_id)
        if not channel_name:
            return None
        # Search in category first, then by name only (channel may exist in different category)
        channel = discord.utils.get(guild.text_channels, name=channel_name, category=group_category)
        if not channel:
            channel = discord.utils.get(guild.text_channels, name=channel_name)
        if channel:
            # Ensure group_role has access (in case channel existed without it)
            try:
                await channel.set_permissions(
                    group_role,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    reason="Sync group channel access"
                )
            except discord.Forbidden:
                logger.warning(f"Cannot set permissions on #{channel_name} for {group_role.name}")
            return channel

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            group_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True)
        }

        async def _create_in_category(category: discord.CategoryChannel):
            return await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"💬 Discussion group {group_id} for {batch_name} batch"
            )

        # Try main category first
        try:
            channel = await _create_in_category(group_category)
            logger.info(f"✅ Created Group Channel: #{channel_name}")
            return channel
        except discord.Forbidden:
            logger.error(f"❌ Missing Permissions: Cannot create channel '{channel_name}'")
            return None
        except discord.HTTPException as e:
            err_str = str(e).lower()
            if "50" not in err_str and "maximum number of channels" not in err_str:
                raise

        # Main category full (50 limit) - try fallback categories
        logger.warning(f"Category {group_category.name} full (50 channels), trying fallback...")
        cat_with_space = self._get_category_with_space(guild, university)
        if cat_with_space:
            try:
                channel = await _create_in_category(cat_with_space)
                logger.info(f"✅ Created Group Channel: #{channel_name} (in {cat_with_space.name})")
                return channel
            except discord.HTTPException as e2:
                if "50" in str(e2) or "maximum number of channels" in str(e2).lower():
                    pass  # fall through to create new
                else:
                    raise

        # Create new fallback category (VTU Project Discussion 2, 3, ...)
        for idx in range(2, 20):
            fallback_cat = await self.ensure_group_category(guild, university, "", idx)
            if fallback_cat and len(fallback_cat.channels) < 50:
                try:
                    channel = await _create_in_category(fallback_cat)
                    logger.info(f"✅ Created Group Channel: #{channel_name} (in {fallback_cat.name})")
                    return channel
                except discord.HTTPException as e3:
                    if "50" in str(e3) or "maximum number of channels" in str(e3).lower():
                        continue
                    raise

        logger.error(f"❌ Could not create channel #{channel_name}: all categories full")
        return None

    async def ensure_student_group(
        self,
        guild: discord.Guild,
        student: dict,
        email: Optional[str] = None,
    ) -> tuple[Optional[discord.Role], Optional[str]]:
        """
        Shared logic: ensure group role/channel exist, auto-assign group_id if missing.
        Does NOT assign the role to the user — caller does that.

        Returns:
            (group_role, assigned_group_id) or (None, None) on failure
        """
        batch = student.get("batch")
        course = student.get("course")
        university = student.get("university", "")
        group_id = student.get("group_id")
        email = email or student.get("email")

        if not batch or not course:
            logger.warning(f"ensure_student_group: skipping (missing batch or course) batch={batch!r} course={course!r}")
            return (None, None)

        # Auto-assign group if missing (balance across G1–G5)
        if not group_id or not str(group_id).strip():
            counts = await db.get_group_counts_for_batch(university, course, batch)
            group_id = min(counts, key=counts.get)
            if email:
                await db.set_student_group_id(email, group_id)
                logger.info(f"Auto-assigned {email} to group {group_id} (batch {batch})")
        group_id = str(group_id).strip().upper()

        try:
            group_role = await self.ensure_group_role(guild, university, batch, group_id)
            if not group_role:
                logger.warning(f"ensure_student_group: ensure_group_role returned None for {university}-{batch}-{group_id}")
                return (None, None)

            group_category = await self.ensure_group_category(guild, university, course)
            if group_category:
                try:
                    ch = await self.ensure_group_channel(
                        guild, group_category, university, batch, group_id, group_role
                    )
                    if ch:
                        logger.info(f"ensure_student_group: group channel ready for {group_id}")
                    else:
                        logger.warning(f"ensure_student_group: ensure_group_channel returned None for {group_id}")
                except Exception as ch_err:
                    logger.warning(f"ensure_student_group: channel creation failed for {group_id}: {ch_err}")
                    # Still return role - user gets group role even if channel failed (channel may exist elsewhere)
            else:
                logger.warning(f"ensure_student_group: ensure_group_category returned None for {university}")
            return (group_role, group_id)
        except Exception as e:
            logger.exception(f"ensure_student_group failed: {e}")
            return (None, None)

    def _get_student_channel_names(self, university: str, course: str, batch: str, group_id: Optional[str] = None) -> list[str]:
        """Return list of channel names the student has access to (course, batch, group)."""
        channels = []
        u = (university or "").lower().replace(" ", "-")
        c = (course or "").lower().replace(" ", "-")
        b = (batch or "").lower().replace(" ", "-")
        if u and c:
            prefix = f"{u}-{c}"
        elif c:
            prefix = c
        else:
            return channels
        channels.append(f"#announcements-{prefix}")
        channels.append(f"#discussions-{prefix}")
        if batch:
            if u:
                channels.append(f"#{u}-{b}-official")
            else:
                channels.append(f"#{b}-official")
        if group_id:
            channels.append(f"#{self._group_channel_name(university or '', batch, str(group_id))}")
        return channels

    async def ensure_full_student_access(
        self,
        guild: discord.Guild,
        user: discord.Member,
        student: dict,
        email: Optional[str] = None,
    ) -> tuple[list[discord.Role], list[str], bool, Optional[str]]:
        """
        Ensure student has ALL roles (course, batch, group). Create resources if needed,
        add any missing roles (skip if already has). Auto-assign group if missing.

        Returns:
            (roles_added, channel_names, any_roles_were_added, assigned_group_id)
        """
        university = student.get("university", "")
        course = student.get("course")
        batch = student.get("batch")
        email = email or student.get("email")
        roles_to_add = []
        any_added = False
        assigned_group_id = None

        if not course:
            return ([], [], False, None)

        # 0. Verified role (if user is verified in DB but missing the role)
        if config.VERIFIED_ROLE_ID:
            verified_role = guild.get_role(config.VERIFIED_ROLE_ID)
            if verified_role and verified_role not in user.roles:
                roles_to_add.append(verified_role)
                any_added = True

        # 1. Course role + category + announcements/discussions
        course_role, category = await self.ensure_course_resources(guild, university, course)
        if course_role and course_role not in user.roles:
            roles_to_add.append(course_role)
            any_added = True

        # 2. Batch role + channel
        if batch and category:
            batch_role = await self.ensure_batch_resources(
                guild, university, course, batch, category
            )
            if batch_role and batch_role not in user.roles:
                roles_to_add.append(batch_role)
                any_added = True

        # 3. Group role + channel (auto-assign if missing)
        group_role, assigned_group_id = await self.ensure_student_group(guild, student, email)
        if group_role and group_role not in user.roles:
            roles_to_add.append(group_role)
            any_added = True

        # Assign any missing roles
        if roles_to_add:
            try:
                await user.add_roles(*roles_to_add, reason="Sync roles via verify/my-group")
            except discord.Forbidden:
                logger.warning(f"Cannot assign roles to {user.id}: missing permission")
                any_added = False
            except Exception as e:
                logger.exception(f"Error assigning roles: {e}")
                any_added = False

        channel_names = self._get_student_channel_names(
            university, course, batch, assigned_group_id
        )
        return (roles_to_add, channel_names, any_added, assigned_group_id)

    # ============================================
    # UTILITY FUNCTIONS
    # ============================================
    def generate_otp(self, length: int = 6) -> str:
        """Generate a random numeric OTP code"""
        return ''.join(random.choices(string.digits, k=length))
    
    async def send_otp_email(self, email: str, otp: str, name: str = "Student") -> bool:
        """Send OTP code via email"""
        try:
            # Email configuration
            smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
            smtp_port = int(os.getenv("SMTP_PORT", 587))
            smtp_email = os.getenv("SMTP_EMAIL")
            smtp_password = os.getenv("SMTP_PASSWORD")
            
            if not all([smtp_email, smtp_password]):
                logger.error("SMTP credentials not configured")
                return False
            
            # Create email message
            message = MIMEMultipart("alternative")
            message["Subject"] = "🔐 Your Discord Verification Code"
            message["From"] = smtp_email
            message["To"] = email
            
            # Plain text version
            text = f"""
Hello {name},

Your Discord verification code is: {otp}

This code will expire in 5 minutes.

If you did not request this code, please ignore this email.

Best regards,
Mind Matrix Team
            """
            
            # HTML version
            html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px; }}
        .container {{ max-width: 500px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .otp-code {{ font-size: 36px; font-weight: bold; color: #5865F2; letter-spacing: 8px; text-align: center; padding: 20px; background: #f0f0f0; border-radius: 8px; margin: 20px 0; }}
        .header {{ color: #333; text-align: center; }}
        .footer {{ color: #888; font-size: 12px; text-align: center; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h2 class="header">🔐 Discord Verification</h2>
        <p>Hello <strong>{name}</strong>,</p>
        <p>Your verification code is:</p>
        <div class="otp-code">{otp}</div>
        <p>This code will expire in <strong>5 minutes</strong>.</p>
        <p>Enter this code using <code>/otp code:{otp}</code> in Discord.</p>
        <div class="footer">
            <p>If you did not request this code, please ignore this email.</p>
        </div>
    </div>
</body>
</html>
            """
            
            message.attach(MIMEText(text, "plain"))
            message.attach(MIMEText(html, "html"))
            
            # Send email
            await aiosmtplib.send(
                message,
                hostname=smtp_host,
                port=smtp_port,
                username=smtp_email,
                password=smtp_password,
                start_tls=True
            )
            
            logger.info(f"OTP email sent to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send OTP email to {email}: {e}")
            return False
    
    def is_on_cooldown(self, user_id: int) -> tuple[bool, int]:
        """Check if user is on OTP request cooldown"""
        if user_id in self.otp_cooldowns:
            cooldown_end = self.otp_cooldowns[user_id]
            if datetime.utcnow() < cooldown_end:
                remaining = int((cooldown_end - datetime.utcnow()).total_seconds())
                return True, remaining
        return False, 0
    
    def set_cooldown(self, user_id: int):
        """Set OTP request cooldown for user"""
        self.otp_cooldowns[user_id] = datetime.utcnow() + timedelta(seconds=config.OTP_COOLDOWN)
    
    # ============================================
    # SLASH COMMANDS
    # ============================================
    @app_commands.command(name="verify", description="Verify your email to access course channels")
    @app_commands.describe(email="Your registered email address")
    async def verify(self, interaction: discord.Interaction, email: str):
        """
        Start the verification process by sending an OTP to the user's email
        This response is EPHEMERAL - only visible to the user
        """
        await interaction.response.defer(ephemeral=True)  # Ephemeral = private response
        
        user = interaction.user
        email = email.strip().lower()
        
        logger.info(f"Verification attempt: {user.name} ({user.id}) with email {email}")
        
        # Check cooldown
        on_cooldown, remaining = self.is_on_cooldown(user.id)
        if on_cooldown:
            embed = discord.Embed(
                title="⏳ Please Wait",
                description=f"You can request another OTP in **{remaining}** seconds.",
                color=config.WARNING_COLOR
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Check if user is already verified
        existing_student = await db.get_student_by_discord_id(user.id)
        if existing_student and existing_student.get("is_verified"):
            embed = discord.Embed(
                title="✅ Already Verified",
                description="You are already verified! You should have access to your course channels.",
                color=config.SUCCESS_COLOR
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Check if email exists in database
        student = await db.get_student_by_email(email)
        if not student:
            embed = discord.Embed(
                title="❌ Email Not Found",
                description=config.EMAIL_NOT_FOUND,
                color=config.ERROR_COLOR
            )
            await db.log_verification_action(email, user.id, "VERIFY_REQUEST", "FAILED", "Email not in database")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Check if email is already linked to another Discord account
        if await db.is_email_already_verified(email):
            embed = discord.Embed(
                title="⚠️ Email Already Linked",
                description=config.ALREADY_VERIFIED,
                color=config.WARNING_COLOR
            )
            await db.log_verification_action(email, user.id, "VERIFY_REQUEST", "FAILED", "Email already linked")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Generate and send OTP
        otp = self.generate_otp()
        student_name = student.get("name", "Student")
        
        # Store OTP in database
        await db.store_otp(email, otp, user.id)
        
        # Send OTP email
        email_sent = await self.send_otp_email(email, otp, student_name)
        
        if email_sent:
            self.set_cooldown(user.id)
            embed = discord.Embed(
                title="📧 OTP Sent!",
                description=f"A verification code has been sent to:\n**{email}**\n\nPlease check your inbox (and spam folder).",
                color=config.EMBED_COLOR
            )
            embed.add_field(
                name="Next Step",
                value="Use `/otp code:XXXXXX` to complete verification.",
                inline=False
            )
            embed.add_field(
                name="⏰ Expires In",
                value="5 minutes",
                inline=True
            )
            embed.set_footer(text="Code not received? Wait 60 seconds and try again.")
            
            await db.log_verification_action(email, user.id, "OTP_SENT", "SUCCESS")
        else:
            embed = discord.Embed(
                title="❌ Error Sending Email",
                description="We couldn't send the verification email. Please try again later or contact support.",
                color=config.ERROR_COLOR
            )
            await db.log_verification_action(email, user.id, "OTP_SENT", "FAILED", "Email send failed")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="otp", description="Enter your OTP code to complete verification")
    @app_commands.describe(code="The 6-digit code sent to your email")
    async def otp(self, interaction: discord.Interaction, code: str):
        """
        Verify the OTP code and assign roles
        Uses new 4-column CSV format: Name, Email, Course (category), Batch (batch role)
        """
        await interaction.response.defer(ephemeral=True)
        
        user = interaction.user
        code = code.strip()
        
        logger.info(f"OTP verification attempt: {user.name} ({user.id})")
        
        # Verify OTP
        result = await db.verify_otp(user.id, code)
        
        if not result["valid"]:
            embed = discord.Embed(
                title="❌ Verification Failed",
                description=result["error"],
                color=config.ERROR_COLOR
            )
            await db.log_verification_action(result.get("email"), user.id, "OTP_VERIFY", "FAILED", result["error"])
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        email = result["email"]
        
        # OTP is valid - verify the student in database
        verified = await db.verify_student(email, user.id)
        
        if not verified:
            embed = discord.Embed(
                title="❌ Verification Error",
                description="An error occurred during verification. Please contact support.",
                color=config.ERROR_COLOR
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # ============================================
        # GET STUDENT DATA & ASSIGN ALL ROLES (verified, course, batch, group)
        # Uses shared ensure_full_student_access for G1–G5 group assignment
        # ============================================
        university, course, batch = await db.get_student_university_course_batch(email)
        student = await db.get_student_by_email(email) or {}
        student.update({
            "email": email,
            "university": university,
            "course": course,
            "batch": batch,
        })
        logger.info(f"Processing student: University='{university}', Course='{course}', Batch='{batch}'")

        roles_added, channel_names, any_added, assigned_group_id = await self.ensure_full_student_access(
            interaction.guild, user, student, email
        )
        assigned_roles = [r.name for r in roles_added]
        role_assignment_errors = []
        if not any_added and not assigned_roles and (course or batch):
            role_assignment_errors.append("Roles may already be assigned, or check bot permissions.")
        if assigned_roles:
            logger.info(f"Successfully assigned roles to {user.name} ({user.id}): {assigned_roles}")
        
        # Success message
        embed = discord.Embed(
            title="✅ Verification Successful!",
            description=config.VERIFICATION_SUCCESS.format(username=user.display_name),
            color=config.SUCCESS_COLOR
        )
        embed.add_field(name="Email", value=email, inline=True)
        if university:
            embed.add_field(name="University", value=university, inline=True)
        embed.add_field(name="Course", value=course or "N/A", inline=True)
        if batch:
            embed.add_field(name="Batch", value=batch, inline=True)
        
        # Show all channels (course, batch, group) - from ensure_full_student_access
        if channel_names:
            embed.add_field(
                name="📂 Your Channels",
                value="\n".join(channel_names),
                inline=False
            )
        if assigned_group_id:
            embed.add_field(
                name="📚 Discussion Group",
                value=f"Group {assigned_group_id}\nUse `/my-group` anytime to sync roles or view your channels.",
                inline=False
            )
        
        # Show assigned roles
        if assigned_roles:
            embed.add_field(name="Roles Assigned", value=", ".join(assigned_roles), inline=False)
        
        # Warn user if there were any role assignment issues
        if role_assignment_errors:
            embed.add_field(
                name="⚠️ Notice", 
                value="Some roles couldn't be assigned. Contact an admin if you can't access your course channels.",
                inline=False
            )
            logger.warning(f"Role assignment issues for {user.name}: {role_assignment_errors}")
        
        embed.set_thumbnail(url=user.avatar.url if user.avatar else None)
        
        await db.log_verification_action(
            email, user.id, "VERIFICATION_COMPLETE", "SUCCESS", 
            f"University: {university}, Course: {course}, Batch: {batch}, Roles: {assigned_roles}, Errors: {role_assignment_errors or 'None'}"
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Log to admin channel
        log_channel = interaction.guild.get_channel(config.LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="🎓 New Student Verified",
                color=config.SUCCESS_COLOR,
                timestamp=datetime.utcnow()
            )
            log_embed.add_field(name="User", value=f"{user.mention} ({user.name})", inline=True)
            log_embed.add_field(name="Email", value=email, inline=True)
            if university:
                log_embed.add_field(name="University", value=university, inline=True)
            log_embed.add_field(name="Course", value=course or "N/A", inline=True)
            if batch:
                log_embed.add_field(name="Batch", value=batch, inline=True)
            log_embed.set_footer(text=f"User ID: {user.id}")
            
            try:
                await log_channel.send(embed=log_embed)
            except Exception as e:
                logger.error(f"Failed to send log message: {e}")
    
    @app_commands.command(name="reverify", description="Request a new verification code")
    async def reverify(self, interaction: discord.Interaction):
        """Allow users to request re-verification if they have a pending OTP"""
        await interaction.response.defer(ephemeral=True)
        
        user = interaction.user
        
        # Check if user has a pending OTP
        pending = await db.get_pending_otp(user.id)
        
        if not pending:
            embed = discord.Embed(
                title="ℹ️ No Pending Verification",
                description="You don't have a pending verification.\nUse `/verify email:your@email.com` to start.",
                color=config.EMBED_COLOR
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Check cooldown
        on_cooldown, remaining = self.is_on_cooldown(user.id)
        if on_cooldown:
            embed = discord.Embed(
                title="⏳ Please Wait",
                description=f"You can request another OTP in **{remaining}** seconds.",
                color=config.WARNING_COLOR
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        email = pending["email"]
        student = await db.get_student_by_email(email)
        
        # Generate and send new OTP
        otp = self.generate_otp()
        await db.store_otp(email, otp, user.id)
        
        email_sent = await self.send_otp_email(email, otp, student.get("name", "Student") if student else "Student")
        
        if email_sent:
            self.set_cooldown(user.id)
            embed = discord.Embed(
                title="📧 New OTP Sent!",
                description=f"A new verification code has been sent to:\n**{email}**",
                color=config.EMBED_COLOR
            )
            embed.add_field(name="Next Step", value="Use `/otp code:XXXXXX` to complete verification.", inline=False)
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to send new OTP. Please try again later.",
                color=config.ERROR_COLOR
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(
        name="my-group",
        description="Sync your roles and view all your channels (course, batch, group)"
    )
    @app_commands.describe(email="Your registered email address")
    async def my_group(self, interaction: discord.Interaction, email: str):
        """Check all roles (course, batch, group), add any missing, show all assigned channels. Never sends OTP."""
        await interaction.response.defer(ephemeral=True)

        email = (email or "").strip()
        if not email:
            await interaction.followup.send("❌ Please provide your registered email address.", ephemeral=True)
            return

        # Look up by email first (direct like /verify)
        student = await db.get_student_by_email(email)
        if not student:
            await interaction.followup.send(
                f"❌ No student found with email **{email}**. Check your email or contact an admin.",
                ephemeral=True
            )
            return
        # Ensure it's the same user (discord_id must match when verified)
        if student.get("discord_id") and int(student.get("discord_id", 0)) != interaction.user.id:
            await interaction.followup.send(
                "❌ This email is linked to another Discord account. Use the account you verified with.",
                ephemeral=True
            )
            return

        if not student.get("is_verified"):
            await interaction.followup.send(
                f"❌ You are not verified yet. Use `/verify email:{email}` to verify and get access.",
                ephemeral=True
            )
            return

        course = student.get("course")
        batch = student.get("batch")

        if not course or not batch:
            await interaction.followup.send(
                "❌ You are not assigned to a course/batch. Contact an admin.",
                ephemeral=True
            )
            return

        user = interaction.user
        guild = interaction.guild

        # Ensure all roles exist, add any missing (creates G1/G2 channels if needed)
        _, channel_names, any_added, assigned_group_id = await self.ensure_full_student_access(
            guild, user, student, email
        )

        if not channel_names:
            await interaction.followup.send(
                "❌ Could not load your channels. Contact an admin.",
                ephemeral=True
            )
            return

        university = student.get("university", "")
        group_id = assigned_group_id or student.get("group_id")
        role_name = self._group_role_name(university, batch, str(group_id)) if group_id else None

        embed = discord.Embed(
            title="📂 Your Channels",
            color=config.SUCCESS_COLOR if any_added else config.EMBED_COLOR
        )
        embed.add_field(
            name="Course",
            value=course or "—",
            inline=True
        )
        embed.add_field(
            name="Batch",
            value=batch or "—",
            inline=True
        )
        if group_id:
            embed.add_field(
                name="Group",
                value=f"{group_id} ({role_name or ''})",
                inline=True
            )
        embed.add_field(
            name="Assigned Channels",
            value="\n".join(channel_names),
            inline=False
        )
        if any_added:
            embed.add_field(
                name="✅ Roles Synced",
                value="Added missing roles. You now have access to all channels above.",
                inline=False
            )
        embed.set_footer(text="Use @role to notify your group" if role_name else "Run anytime to sync")

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot"""
    await bot.add_cog(Verification(bot))
