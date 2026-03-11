# Mind Matrix Bot — Slash Commands Reference

## How Commands Update in Discord

Restart the bot to sync slash commands:

```bash
python main.py
```

Commands sync automatically on startup. After restart, new/updated commands appear in Discord (may take a few seconds).

---

## All Commands (11 total)

| Command | Who | Description |
|---------|-----|-------------|
| `/verify` | Students | Verify your email to access course channels |
| `/otp` | Students | Enter your OTP code to complete verification |
| `/reverify` | Students | Request a new verification code |
| `/my-group` | Students | Sync all roles (course, batch, group) and view all assigned channels |
| `/help` | Everyone | Get help with bot commands |
| `/stats` | **Admin only** | View verification statistics |
| `/force-verify` | **Admin only** | Manually verify a user |
| `/unverify` | **Admin only** | Remove verification by email — removes all roles and channel access |
| `/lookup` | **Admin only** | Look up a user's verification status |
| `/add-student` | **Admin only** | Add a single student to the database |
| `/broadcast` | **Admin only** | Send a message to verified students |

---

## Student Commands (5)

| Command | Usage | Description |
|---------|-------|-------------|
| `/verify` | `email:your@email.com` | Start verification — sends 6-digit OTP to your email |
| `/otp` | `code:123456` | Complete verification with OTP from email |
| `/reverify` | — | Request new OTP if previous expired |
| `/my-group` | — | Syncs course, batch, group roles (adds any missing). Shows all channels: announcements, discussions, batch-official, group (e.g. #vtu-ascenders-g1) |
| `/help` | — | Interactive help menu |

---

## Admin Commands (6)

| Command | Usage | Description |
|---------|-------|-------------|
| `/stats` | — | Total students, verified, unverified, pending OTPs |
| `/force-verify` | `user:@User email:...` | Verify user without OTP; fetches university/course/batch/group from DB |
| `/unverify` | `email:...` | Remove verification by email — removes all roles (verified, course, batch, group) |
| `/lookup` | `user:@User` or `email:...` | View student record |
| `/add-student` | `name:... email:... university:... course:... batch:... group:...` | Add student with all CSV fields (G1–G5) |
| `/broadcast` | `message:...` `course:...` (optional) | Announce to verified students |
