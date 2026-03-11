# Discord Mind Matrix Bot

A Discord bot for managing student verification with email OTP for Mind Matrix platforms. Designed to handle **5000+ students** across **multiple internship batches** with automatic role and channel creation.

## ✨ Features

- ✅ **Email OTP Verification** - Secure verification with 6-digit codes
- 🏫 **University-Based Organization** - Separate VTU and GTU students on same server
- 🤖 **Auto Role & Channel Creation** - Bot creates roles/channels dynamically with university prefixes
- 🏢 **Multi-University Support** - Each university gets its own categories, roles, and channels
- 📢 **Shared + Private Channels** - Announcements for all students, private channels per batch
- 🛡️ **Duplicate Prevention** - Email and Discord ID uniqueness enforced
- 📊 **Admin Dashboard** - Stats, force-verify, lookup, broadcast
- 📚 **Sub-Batch Discussion Groups** - Auto-assigns ~100 students per group channel (no role explosion)
- 💾 **Local SQLite** - No external database needed

---

## 📁 Project Structure

```
discord-bot-subbatches/
├── .env                    # Secrets (NEVER commit!)
├── .gitignore
├── requirements.txt
├── config.py               # Channel IDs, Verified Role, Settings
├── main.py                 # Bot entry point — run: python main.py
├── run.sh                  # Linux: ./run.sh (auto-restart on crash)
├── database.py             # SQLite operations
├── import_csv.py           # CSV → Database import tool (local setup)
├── create_sub_batches.py   # Optional batch migration (students can use /my-group instead)
├── data/                   # Upload students.csv, student_data.db manually (not in git)
│   └── .gitkeep
├── src/
│   ├── __init__.py
│   └── cogs/
│       ├── __init__.py
│       ├── verification.py # /verify, /otp + Auto Role/Channel creation
│       ├── admin.py        # Admin commands
│       └── help.py         # Help menu
└── logs/                   # Bot logs (created at runtime)
    └── .gitkeep
```

---

## 🚀 How It Works

### University-Based Auto-Creation System

When a **VTU** student with course `"Android App Development"` and batch `"Nomads"` verifies, the bot **automatically creates**:

| Resource | Name | Who Can See |
|----------|------|-------------|
| **Course Role** | `VTU-Android App Development Intern` | - |
| **Batch Role** | `VTU-Nomads` | - |
| **Category** | `VTU - Android App Development` | VTU Android students |
| **Channel** | `#vtu-android-app-development-announcements` | All VTU Android students (read-only) |
| **Channel** | `#vtu-android-app-development-discussion` | All VTU Android students (can chat) |
| **Channel** | `#vtu-nomads-official` | Only VTU Nomads batch |
| **Category** | `VTU - Android App Development Groups` | Sub-batch discussion groups |
| **Channel** | `#nomads-group-1` to `#nomads-group-5` | ~100 students per group (permission-based) |

**GTU** students get completely separate resources:
- `GTU-Android App Development Intern` role
- `GTU - Android App Development` category
- `#gtu-android-app-development-announcements` channel
- etc.

**Key Benefits:**
- VTU and GTU students are organized separately
- No naming conflicts between universities
- Easy to manage multiple colleges on one server

### Verification Flow

```
Student joins server
        ↓
Uses /verify email:student@example.com
        ↓
Bot checks SQLite database → Email found?
        ↓ (finds: University=VTU, Course=Android App Development, Batch=Nomads)
    YES → Bot sends OTP to email
        ↓
Student uses /otp code:123456
        ↓
Bot validates OTP → Creates university-specific roles/channels if needed
        ↓
Bot assigns: @Verified + @VTU-Android App Development Intern + @VTU-Nomads
        ↓
Student sees VTU Android App Development channels! 🎉
```

---

## 🛠️ Setup Guide

### Part A: Discord Setup

#### Step 1: Create Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"** → Name it (e.g., "Mind Matrix Bot")
3. Go to **"Bot"** section → Click **"Add Bot"**
4. Click **"Reset Token"** → Copy and save securely
5. **Enable Privileged Gateway Intents**:
   - ✅ `SERVER MEMBERS INTENT`
   - ✅ `MESSAGE CONTENT INTENT`

#### Step 2: Generate Bot Invite Link

1. Go to **"OAuth2"** → **"URL Generator"**
2. Select **Scopes**: `bot`, `applications.commands`
3. Select **Bot Permissions**:
   - ✅ Manage Roles
   - ✅ Manage Channels
   - ✅ Send Messages
   - ✅ Embed Links
   - ✅ Read Message History
   - ✅ Use Slash Commands
4. Copy URL → Open in browser → Add to your server

#### Step 3: Create Basic Roles

In your Discord server (**Server Settings → Roles**):

1. Create a `Verified` role (general access)
2. **CRITICAL**: Drag the **Bot's Role** to the **TOP** of the role list
   - The bot can only manage roles **below** its own role

#### Step 4: Create Verification Channel

1. Create `#verify` channel (visible to @everyone)
2. Create `#admin-logs` channel (visible only to admins)

---

### Part B: Local Setup

#### Step 1: Install Python

```powershell
# Download Python 3.10+ from python.org
# Verify installation
python --version
```

#### Step 2: Set Up Project

```powershell
# Navigate to project folder
cd "d:\OneDrive - IIT Kanpur\Desktop\discord-edtech-bot"

# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### Step 3: Configure `.env`

```env
# Discord Bot Token
DISCORD_TOKEN=your_bot_token_here

# Gmail SMTP (for OTP emails)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=your_email@gmail.com
SMTP_PASSWORD=your_app_password
```

**Gmail App Password**:
1. Enable 2FA on Google account
2. Go to [App Passwords](https://myaccount.google.com/apppasswords)
3. Generate password for "Mail"

#### Step 4: Configure `config.py`

Only **3 IDs** needed (batch roles are auto-created):

```python
# Get by right-clicking in Discord (Developer Mode ON)
VERIFIED_ROLE_ID = 1452628492263882825   # @Verified role
VERIFY_CHANNEL_ID = 1452628764000260116  # #verify channel
LOG_CHANNEL_ID = 1452629016568791050     # #admin-logs channel
```

#### Step 5: Prepare Student CSV

Create `data/students.csv` with **5 columns**:

```csv
Name,Email id,University,Course,Batch name
Rahul Sharma,rahul@example.com,VTU,Android App Development,Nomads
Priya Singh,priya@example.com,GTU,Data Analytics,Pioneers
Amit Kumar,amit@example.com,VTU,Android App Development,Navigants
Neha Gupta,neha@example.com,GTU,Web Development,Explorers
```

**CSV Format Explained:**
| Column | Description | Example |
|--------|-------------|----------|
| Name | Student's full name | "Rahul Sharma" |
| Email id | Student's email | "rahul@example.com" |
| University | University code (VTU/GTU) | "VTU" |
| Course | Course/Category name | "Android App Development" |
| Batch name | Batch/Group name | "Nomads" |

**Supported Universities:**
- `VTU` - Visvesvaraya Technological University
- `GTU` - Gujarat Technological University
- Add more in `config.py` → `SUPPORTED_UNIVERSITIES`

#### Step 6: Import Students to Database

```powershell
python import_csv.py
# Choose option 1 to import
```

#### Step 7: Run the Bot

```powershell
.\venv\Scripts\activate
python main.py
```

Expected output:
```
==================================================
✅ Bot is ready!
📌 Logged in as: MindMatrixBot
🆔 Bot ID: 123456789
🌐 Servers: 1
==================================================
```

---

## 📋 Commands Reference

**To update commands in Discord:** Restart the bot (`python main.py`). Slash commands sync automatically on startup.

> 📄 See **[COMMANDS.md](COMMANDS.md)** for a full list of all 11 commands (students vs admin).

### 👤 Student Commands (all verified & unverified users)

| Command | Description |
|---------|-------------|
| `/verify email:your@email.com` | Start verification — sends OTP to your registered email |
| `/otp code:123456` | Complete verification — assigns course, batch, group roles; shows all channels |
| `/reverify` | Request a new OTP if the previous one expired |
| `/my-group` | Sync all roles (course, batch, group) and view all your assigned channels |
| `/help` | Show interactive help menu |

### ⚙️ Admin Commands (Administrator permission required)

| Command | Description |
|---------|-------------|
| `/stats` | View verification statistics (total, verified, unverified, pending OTPs) |
| `/force-verify user:@User email:...` | Manually verify a user (no OTP; fetches data from DB) |
| `/unverify email:...` | Remove verification by email — removes all roles and channel access |
| `/lookup user:@User` or `email:...` | Look up student record (name, email, university, course, batch, group) |
| `/add-student name:... email:... university:... course:... batch:... group:...` | Add a student with all CSV fields (G1–G5) |
| `/broadcast message:... course:...` | Send announcement to verified students (optionally by course) |

---

## 📊 What Gets Created Per University & Course

### Example: VTU - Android App Development

For **VTU** students in **Android App Development** with batches (Nomads, Pioneers, etc.):

```
📁 VTU - Android App Development (Category)
├── 📢 #vtu-android-app-development-announcements  ← All VTU Android students (read-only)
├── 💬 #vtu-android-app-development-discussion     ← All VTU Android students (can chat)
├── 🔒 #vtu-nomads-official                        ← Only VTU Nomads batch
├── 🔒 #vtu-pioneers-official                      ← Only VTU Pioneers batch
└── 🔒 #vtu-navigants-official                     ← Only VTU Navigants batch
```

**Roles Created:**
- `VTU-Android App Development Intern` (all VTU Android students)
- `VTU-Nomads` (batch-specific)
- `VTU-Pioneers` (batch-specific)
- `VTU-Navigants` (batch-specific)

### Example: GTU - Android App Development

**GTU** students get completely separate resources:

```
📁 GTU - Android App Development (Category)
├── 📢 #gtu-android-app-development-announcements
├── 💬 #gtu-android-app-development-discussion
├── 🔒 #gtu-nomads-official
└── 🔒 #gtu-pioneers-official
```

**Roles Created:**
- `GTU-Android App Development Intern`
- `GTU-Nomads`
- `GTU-Pioneers`

**Key Point:** VTU and GTU resources are completely independent - no conflicts!

### Sub-Batch Discussion Groups (G1–G5 from CSV)

Groups come from CSV `Groups` column (G1, G2, G3, G4, G5). Role-based access:

```
📁 VTU Project Discussion (Category)
├── #vtu-ascenders-g1   ← @VTU-Ascenders-G1 role
├── #vtu-ascenders-g2   ← @VTU-Ascenders-G2 role
├── #vtu-ascenders-g3
├── #vtu-ascenders-g4
├── #vtu-ascenders-g5
├── #vtu-pioneers-g1
└── ...
```

- **Role:** `{University}-{Batch}-{Group}` (e.g. VTU-Ascenders-G1) — supports @mention
- **Category:** `{University} Project Discussion`
- **Channel:** vtu-ascenders-g1 (access via role)
- **Command:** `/my-group` — Syncs all roles (course, batch, group), adds any missing, shows all channels

---

## 🔄 Groups from CSV (Local → VM)

**Recommended workflow:** Import CSV with Groups column → Deploy → Students use `/my-group` to join their group.

### Step 1: Import CSV with Groups column (LOCAL)

```powershell
# CSV format: Name, Email, University, Course, Batch, Groups
# Groups: G1, G2, G3, G4, G5
python import_csv.py
# Choose option 1 — imports + updates group_id for existing students
```

### Step 2: Deploy to VM

See [VM Setup Guide](#-vm-setup-guide) below.

---

## 🖥️ VM Setup Guide

Run the bot on a Linux VM (Ubuntu, Debian, etc.) or any server.

### 1. Copy code to VM

```bash
# From your local machine (git clone or scp/rsync)
scp -r discord-bot-subbatches/ user@your-vm-ip:~/
# Or: rsync -avz discord-bot-subbatches/ user@your-vm-ip:~/discord-bot-subbatches/
```

### 2. Upload data files (not in git)

```bash
# From local machine
scp data/student_data.db user@your-vm-ip:~/discord-bot-subbatches/data/
scp data/students.csv user@your-vm-ip:~/discord-bot-subbatches/data/  # optional, for future import_csv
```

### 3. SSH into VM and setup

```bash
ssh user@your-vm-ip
cd ~/discord-bot-subbatches
```

### 4. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Configure `.env`

```bash
cp .env.example .env
nano .env  # or vim
```

Set these in `.env`:
- `DISCORD_TOKEN` — Bot token from Discord Developer Portal
- `SMTP_EMAIL` — Gmail for OTP sending
- `SMTP_PASSWORD` — Gmail app password (not regular password)
- `DISCORD_GUILD_ID` — Optional; your server ID if bot is in multiple servers

### 6. Update `config.py`

Edit `config.py` to set your Discord channel IDs:
- `VERIFY_CHANNEL_ID` — Channel where users run /verify
- `VERIFIED_ROLE_ID` — Role given after verification
- `LOG_CHANNEL_ID` — Admin logs channel

### 7. Run the bot

```bash
python main.py
```

### 8. Run in background (production)

```bash
# Using nohup
nohup python main.py > bot.log 2>&1 &

# Or using screen/tmux
screen -S discord-bot
python main.py
# Ctrl+A, D to detach
```

### 9. Auto-restart on crash (optional)

Create `run.sh`:
```bash
#!/bin/bash
cd ~/discord-bot-subbatches
source venv/bin/activate
while true; do python main.py; sleep 5; done
```

Or use the included script:
```bash
chmod +x run.sh
./run.sh   # Auto-restarts on crash
```

Or use `systemd` for a proper service.

---

**Students self-serve:** Verified students run `/my-group` to sync all roles (course, batch, group) and see their channels. The bot adds any missing roles and creates resources on demand.

### Optional: Pre-assign all groups (create_sub_batches.py)

If you want to assign everyone at once instead of on-demand:
```powershell
python create_sub_batches.py  # Run with bot stopped; takes 1–2+ hours for 5000 students (Discord rate limits)
```
Creates categories/channels and assigns roles to all verified students. **Not required** — `/my-group` handles assignments as students use it.

**Optional:** Set `DISCORD_GUILD_ID` in `.env` if the bot is in multiple servers.

**Note:** `data/student_data.db` and `data/students.csv` are in `.gitignore` — upload them manually when deploying.

---

## 🔄 Adding New Students

```powershell
# 1. Edit data/students.csv with new students
# Format: Name,Email id,University,Course,Batch name
# Example: Raj Kumar,raj@example.com,VTU,Data Analytics,Batch-A

# 2. Run import (duplicates are skipped)
python import_csv.py
# Choose option 1 to import

# 3. Restart bot (optional, for new slash commands)
python main.py
```

**Adding a New University:**
1. Open `config.py`
2. Add to `SUPPORTED_UNIVERSITIES` list:
   ```python
   SUPPORTED_UNIVERSITIES = ["VTU", "GTU", "JNTU"]  # Add JNTU
   ```
3. Update CSV with new university code
4. Import and verify - bot auto-creates resources!

---

## 🛠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| Bot can't create roles | Move Bot's role to TOP in Server Settings → Roles |
| "Email not found" | Run `python import_csv.py` to import CSV |
| OTP not received | Check spam folder, verify SMTP credentials |
| Roles exist but not assigned | Bot role must be ABOVE the target roles |
| Slash commands not showing | Wait 1 hour or kick & re-invite bot |

---

## 🔒 Security Notes

- **Never commit `.env`** - Contains bot token & email password
- **Bot token leaked?** → Regenerate in Discord Developer Portal
- **OTPs expire** in 5 minutes
- **All responses are ephemeral** (private to user)

---

## 📄 License

MIT License - Free to use and modify!
