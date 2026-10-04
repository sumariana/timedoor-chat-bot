# Timedoor Project Assistant Bot — Setup Guide

Follow every step in order. Steps marked **[YOU]** require actions in external websites or your terminal. Steps marked **[FILE]** are edits to project files.

---

## Step 1 — Create a Discord Bot Application [YOU]

1. Go to https://discord.com/developers/applications
2. Click **New Application** → enter a name (e.g. `Timedoor Project Assistant`) → click **Create**
3. In the left sidebar click **Bot**
4. Click **Reset Token** → confirm → copy the token and save it somewhere safe
   - This is your `DISCORD_BOT_TOKEN`
5. Scroll down to **Privileged Gateway Intents** and enable both:
   - **Server Members Intent**
   - **Message Content Intent**
6. Click **Save Changes**

---

## Step 2 — Invite the Bot to Your Discord Server [YOU]

1. In the left sidebar click **OAuth2 → URL Generator**
2. Under **Scopes** check: `bot`
3. Under **Bot Permissions** check:
   - `Send Messages`
   - `Read Messages / View Channels`
   - `Embed Links`
   - `Read Message History`
4. Copy the generated URL at the bottom and open it in your browser
5. Select your **Timedoor Discord server** from the dropdown → click **Authorize**

---

## Step 3 — Copy Your Discord Server and Channel IDs [YOU]

You need these to fill in `config/config.yaml` later.

**Server ID:**
1. Open Discord → right-click your Timedoor server icon in the left sidebar
2. Click **Copy Server ID**
3. Save this as `timedoor_server_id`

**Channel IDs (for each channel where the bot should respond):**
1. Right-click the channel name → click **Copy Channel ID**
2. Repeat for every allowed channel
3. Save these as `allowed_channels`

> If "Copy ID" is not visible, go to Discord **Settings → Advanced** and enable **Developer Mode** first.

---

## Step 4 — Create a Notion Integration [YOU]

1. Go to https://www.notion.so/my-integrations
2. Click **+ New integration**
3. Enter a name (e.g. `Timedoor Bot`) and select your Timedoor workspace
4. Under **Capabilities** make sure these are checked:
   - **Read content**
   - **Read user information without email**
5. Click **Save** → copy the **Internal Integration Secret**
   - This is your `NOTION_API_TOKEN`

---

## Step 5 — Connect the Integration to Each Team Database [YOU]

Do this for each of the three team databases: **Mobile**, **Web**, and **Backend**.

1. Open the database in Notion
2. Click the **...** menu (top-right corner of the page)
3. Click **Connections** → search for your integration name → click **Connect**
4. Copy the **Database ID** from the browser URL:
   - URL format: `https://www.notion.so/{workspace}/{DATABASE_ID}?v=...`
   - The Database ID is the long string of letters and numbers before the `?`
5. Save each ID — you will need: `mobile_team`, `web_team`, `backend_team`

---

## Step 6 — Get a Gemini API Key [YOU]

1. Go to https://aistudio.google.com/app/apikey
2. Click **Create API key**
3. Copy the key
   - This is your `GEMINI_API_KEY`

---

## Step 7 — Install the Notion MCP Server [YOU]

Run this once on the machine where the bot will run:

```bash
npm install -g @notionhq/notion-mcp-server
```

Verify the install succeeded:

```bash
notion-mcp-server --version
```

> Requires Node.js 18 or higher. Install from https://nodejs.org if not already installed.

---

## Step 8 — Fill in the `.env` File [FILE]

At the project root, copy the example file:

```bash
cp .env.example .env
```

Open `.env` and fill in the three values from the steps above:

```env
DISCORD_BOT_TOKEN=paste_token_from_step_1
NOTION_API_TOKEN=paste_secret_from_step_4
GEMINI_API_KEY=paste_key_from_step_6
```

**Never commit `.env` to git.**

---

## Step 9 — Fill in `config/config.yaml` [FILE]

Open `config/config.yaml` and replace every `REPLACE_WITH_...` placeholder:

```yaml
discord:
  allowed_channels:
    - "PASTE_CHANNEL_ID_1"     # from Step 3
    - "PASTE_CHANNEL_ID_2"     # add more lines if needed
  denied_channels: []
  allow_dms: true
  dm_require_server_membership: true
  timedoor_server_id: "PASTE_SERVER_ID"   # from Step 3

notion:
  databases:
    mobile_team: "PASTE_MOBILE_DB_ID"     # from Step 5
    web_team: "PASTE_WEB_DB_ID"
    backend_team: "PASTE_BACKEND_DB_ID"
```

Leave everything else (session, cache, llm, rate_limit) at its default value.

---

## Step 10 — Install Python Dependencies [YOU]

```bash
cd apps/bot
python -m venv .venv

# Mac / Linux:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate

pip install -r requirements.txt
```

---

## Step 11 — Run the Bot Locally [YOU]

From the `apps/bot` directory with the virtual environment active:

```bash
python main.py
```

You should see this in the console within a few seconds:

```
Logged in as Timedoor Project Assistant#XXXX
```

If the bot logs in successfully, it is ready to receive messages in Discord.

---

## Step 12 — Smoke Test in Discord [YOU]

Go to one of the allowed channels in your Timedoor Discord server and run these test queries one at a time:

| Test | What to send | Expected result |
|------|-------------|-----------------|
| Basic project info | `@bot info about [ProjectName]` | Project details embed (green) |
| Bug count | `@bot berapa bug di [ProjectName]` | Bug count embed |
| Bug by environment | `@bot bug staging mobile [ProjectName]` | Filtered bug count |
| Latest version | `@bot versi terbaru [ProjectName]` | Changelog entry |
| Credentials | `@bot credentials [ProjectName]` | Yellow embed, host/URL only, no passwords |
| Session reset | `@bot reset` | Reset confirmation message |
| Rate limit | Send 6 messages quickly | Rate limit embed on the 6th |

If a query returns wrong or empty data, check:
- The Notion property names match what the normalizer expects (see `apps/bot/src/router/normalizer.py`)
- The integration has access to the database (re-check Step 5)
- The Status field values in the Bug List exactly match: `Open`, `In progress`, `Re-Opened`, `Re-Test`

---

## Troubleshooting

| Error | Likely cause | Fix |
|-------|-------------|-----|
| `EnvironmentError: Required environment variable is missing: DISCORD_BOT_TOKEN` | `.env` not filled in or not found | Check `.env` exists at project root with all 3 keys |
| `FileNotFoundError: Configuration file not found` | Wrong working directory | Run `python main.py` from inside `apps/bot/` |
| Bot online but not responding | Message Content Intent not enabled | Re-check Step 1 item 5 |
| Bot responds in DM but not in channels | Channel IDs wrong or not in allowlist | Re-check Step 3 and `config.yaml` |
| Bug count always returns 0 | Status property type or value mismatch | Verify Status values in Notion match exactly: `Open`, `In progress`, `Re-Opened`, `Re-Test` |
| MCP errors at startup | `notion-mcp-server` not installed | Re-run Step 7 |
| `notion_mcp-server` not found | Node.js PATH issue | Restart terminal after npm install |
