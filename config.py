"""
Configuration file for Discord Mind Matrix Bot
Store all constants and settings here
"""

# ============================================
# DISCORD ROLE IDs
# Replace with your actual Role IDs from Discord
# you can add new roles as needed
# ============================================
COURSE_A_ROLE_ID = 1451843622491127808  # Role for Course A students
COURSE_B_ROLE_ID = 1451844655707590676  # Role for Course B students
COURSE_C_ROLE_ID = 1451845123456789123  # Role for Course C students
COURSE_D_ROLE_ID = 1451845789123456789  # Role for Course D students

# ============================================
# NOTE: BATCH ROLES ARE NOW AUTO-CREATED
# ============================================
# For batch-based courses like "Androidapp_B1" or "DataAnalystB5",
# the bot will AUTOMATICALLY create:
#   1. Parent Role (e.g., "Androidapp Intern") - Shared across all batches
#   2. Batch Role (e.g., "Androidapp_B1") - Specific to each batch
#   3. Category (e.g., "Androidapp Internship") with channels:
#      - #androidapp-announcements (read-only for students)
#      - #androidapp-discussion (all interns can chat)
#      - #androidapp-b1-official (batch-specific private channel)
#
# NO NEED to add Role IDs here for batch courses!

# ============================================
# INTERNSHIP DISPLAY NAMES (Customization)
# ============================================
# Map CSV internship names to prettier display names for Discord.
# The bot uses these when creating Roles, Categories, and Channels.
#
# CSV Value       →  Display Name (used in Discord)
# "Androidapp"    →  "Android App"
# "DataAnalyst"   →  "Data Analyst"
#
# HOW IT WORKS:
#   - CSV has: "Androidapp_B1"
#   - Bot parses: internship="Androidapp", batch="B1"
#   - Bot looks up: INTERNSHIP_DISPLAY_NAMES["Androidapp"] = "Android App"
#   - Creates: Role "Android App Intern", Category "Android App Internship"
#
INTERNSHIP_DISPLAY_NAMES = {
    "Androidapp": "Android App",
    "DataAnalyst": "Data Analyst",
    # Add more as needed:
    # "WebDev": "Web Development",
    # "MLEngineer": "ML Engineer",
}

# ============================================
# SUPPORTED UNIVERSITIES
# ============================================
# List of valid university codes for validation
# Students will be organized under university-specific categories
# Example: VTU students get "VTU - Android App Development" category
#          GTU students get "GTU - Android App Development" category
SUPPORTED_UNIVERSITIES = ["VTU", "GTU"]

# ============================================
# General Roles
# ============================================
VERIFIED_ROLE_ID = 1452628492263882825  # General "Verified" role

# ============================================
# DISCORD CHANNEL IDs
# ============================================
VERIFY_CHANNEL_ID = 1452628764000260116  # The #verify channel
LOG_CHANNEL_ID = 1453305111383244851     # Admin log channel

# ============================================
# COURSE MAPPING
# Maps course names from database to Discord Role IDs
# ============================================
#
# INFRASTRUCTURE STRATEGY (Role-Based Category Access):
# ======================================================
# We use Discord's native permission system for channel access.
# The bot ONLY assigns Roles - it does NOT manage channel permissions.
#
# SETUP INSTRUCTIONS:
# 1. Create a Role for each course (e.g., "Course A", "Course B")
# 2. Copy each Role ID and paste it below
# 3. In Discord Server Settings → Create a Category for each course
# 4. Edit the Category permissions:
#    - @everyone → Deny "View Channel"
#    - Course Role (e.g., @Course A) → Allow "View Channel"
# 5. All channels inside that Category will inherit these permissions
#
# When a student verifies, the bot assigns their course Role,
# and Discord automatically reveals the Category to them.
# ======================================================
#
COURSE_ROLE_MAPPING = {
    # Legacy courses (manual Role ID mapping)
    "Course A": COURSE_A_ROLE_ID,
    "Course B": COURSE_B_ROLE_ID,
    "Course C": COURSE_C_ROLE_ID,
    "Course D": COURSE_D_ROLE_ID,
    
    # ============================================
    # BATCH COURSES ARE AUTO-MANAGED
    # ============================================
    # Courses with batch format (e.g., "Androidapp_B1", "DataAnalystB5")
    # are AUTOMATICALLY handled by the bot.
    # 
    # The bot will:
    #   - Parse "Androidapp_B1" into Internship="Androidapp", Batch="B1"
    #   - Create roles and channels dynamically
    #
    # Supported CSV formats:
    #   - "Androidapp_B1" to "Androidapp_B40"
    #   - "DataAnalystB1" to "DataAnalystB10"
    #   - Any format: "<InternshipName>_B<Number>" or "<InternshipName>B<Number>"
}

# ============================================
# BOT SETTINGS
# ============================================
BOT_PREFIX = "!"
EMBED_COLOR = 0x5865F2  # Discord Blurple
SUCCESS_COLOR = 0x57F287  # Green
ERROR_COLOR = 0xED4245   # Red
WARNING_COLOR = 0xFEE75C  # Yellow

# ============================================
# RATE LIMITING
# ============================================
ROLE_ASSIGN_DELAY = 1.0  # Seconds between role assignments (for bulk operations)
OTP_COOLDOWN = 60  # Seconds before user can request new OTP
MAX_OTP_ATTEMPTS = 3  # Max wrong OTP attempts before lockout

# ============================================
# MESSAGES
# ============================================
WELCOME_MESSAGE = """
🎓 **Welcome to our Mind Matrix Community!**

To access the course channels, please verify your email address.

Use `/verify email:your_email@example.com` to begin verification.
"""

VERIFICATION_SUCCESS = """
✅ **Verification Successful!**

You now have access to your course channels.
Welcome aboard, {username}!
"""

EMAIL_NOT_FOUND = """
❌ **Email Not Found**

The email address you provided is not registered in our system.
Please contact support if you believe this is an error.
"""

ALREADY_VERIFIED = """
⚠️ **Already Verified**

This email is already linked to a Discord account.
If you believe this is an error, please contact an admin.
"""
