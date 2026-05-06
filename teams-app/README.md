# Teams App — real DMs (Path B)

This directory holds the Microsoft Teams app manifest required for AAM to send proactive DMs to AMs as a real Teams app (not a channel webhook).

## Why this is heavier than Path A (channel webhook)

Microsoft restricts app-only chat sending in Teams. A bot can DM a user **only after** the user has installed the bot or messaged it first — at which point Teams sends a `conversationUpdate` event the bot persists as a `ConversationReference`. AAM stores those references in `teams_conversation_refs` and uses them to message AMs proactively.

There's no shortcut. Bot Framework registration in Azure + a Teams app manifest uploaded to the tenant are required.

## One-time setup (~30–45 min, mostly Azure provisioning)

### 1. Register an Azure Bot

1. Azure Portal → search **"Azure Bot"** → **Create**
2. Name: `aam-briefings-bot` · Resource group: existing or new · Location: same as your tenant
3. Pricing: F0 (free) · Type: **Multi-tenant** *(or Single-tenant if you want to lock to your tenant)*
4. Microsoft App ID: **Create new Microsoft App ID** (the portal will generate this)
5. After create: Bot resource → **Configuration** → note the **Microsoft App ID**
6. Bot resource → **Configuration** → **Manage Password** → **+ New client secret** → copy the value (you can't see it again)

### 2. Add the Teams channel to the bot

1. Bot resource → **Channels** → **Microsoft Teams** → Apply (accept defaults)

### 3. Set the messaging endpoint

The bot needs a public HTTPS URL to receive Teams messages.

**Dev**: in one terminal run AAM's bot server:
```bash
aam teams-bot
# listens on :3978
```
In another terminal expose it:
```bash
ngrok http 3978
# copy the https URL, e.g. https://abc-123.ngrok-free.app
```
Then in the Bot resource → **Configuration** → **Messaging endpoint**:
`https://abc-123.ngrok-free.app/api/messages`

**Prod**: deploy `aam.teams_bot_server:app` behind your ingress (it's a small FastAPI app); set the messaging endpoint to its public URL.

### 4. Build and upload the Teams app

```bash
cd teams-app
# Replace placeholders in the manifest
sed -e "s/{{TEAMS_APP_GUID}}/$(uuidgen | tr A-Z a-z)/" \
    -e "s/{{AAM_TEAMS_BOT_APP_ID}}/<your-bot-app-id>/" \
    manifest.template.json > manifest.json

# Add icons (192x192 color.png, 32x32 outline.png — placeholders OK for dev)
zip aam-briefings.zip manifest.json color.png outline.png
```

Then in **Teams Admin Center** → **Manage apps** → **Upload new app** → pick `aam-briefings.zip`.

For a personal-tenant test you can instead upload directly in the Teams client: **Apps** → **Manage your apps** → **Upload an app** → **Upload a custom app**.

### 5. Install the bot for each AM

Each AM opens Teams → **Apps** → search "AAM Briefings" → **Add**. On install, AAM's `/api/messages` endpoint receives a `conversationUpdate` activity that captures their `ConversationReference` into the `teams_conversation_refs` SQLite table.

You can verify capture by checking the AAM server logs for `teams_bot.captured_ref`.

### 6. Configure the AM directory

AAM needs to map AAD object IDs (which Teams sends) to AM emails (what the briefing graph uses). Set the env var:

```bash
export AAM_AM_DIRECTORY='{"00000000-aad-0000-id-of-alice":"alice@cyberco.com","00000000-aad-0000-id-of-bob":"bob@cyberco.com"}'
```

Production: replace `_default_aad_resolver` in `teams_bot_server.py` with a real lookup against your AM directory (Microsoft Graph `/users` lookup, or your own DB).

### 7. Set the bot credentials in `.env`

```bash
AAM_TEAMS_BOT_APP_ID=<from step 1>
AAM_TEAMS_BOT_APP_PASSWORD=<from step 1>
# Required for SingleTenant bots — outbound auth needs to target your tenant,
# not the default "Bot Framework" directory. Optional for MultiTenant.
AAM_TEAMS_BOT_TENANT_ID=<your tenant id>
```

If you used `az ad app create` (vs. registering via the portal), also create a service principal so the app can authenticate in your tenant:

```bash
az ad sp create --id <bot app id>
```

### 8. Send a real DM

```bash
aam brief --am alice@cyberco.com
```

The briefing graph's `_node_teams_dm` will pick up the stored reference and DM Alice as a real Teams personal chat.

## File layout

```
teams-app/
├── manifest.template.json   # Teams app manifest (placeholders for app id + guid)
├── color.png                # 192x192, brand color (you provide)
├── outline.png              # 32x32, white-on-transparent silhouette (you provide)
└── README.md                # this file
```

## Path A vs Path B

| | Path A (channel webhook) | Path B (real DMs) |
|---|---|---|
| Setup time | 3 min | 30-45 min |
| Azure permissions needed | none | Azure Bot Service + Teams app upload |
| Where messages appear | shared channel | personal 1:1 chat |
| Suitable for | broadcast alerts, ops/sec rooms | per-AM private briefings |
| Already used in production by | Datadog, PagerDuty, GitHub | enterprise SaaS bots |

For the AAM use case both are useful. Path A is the right default for a small team where AMs share visibility on each other's accounts. Path B is required when each AM should only see their own list.
