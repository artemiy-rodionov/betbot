# Build Plan — Gated Signup (Admin Approval Queue) + Self-Serve Name Change

## Goal
Replace the mandatory "admin forwards every user's message to `/register`" flow with a
self-serve **request-access** flow gated by **admin one-tap approval**. Keep the existing
forward-based `/register` / `/registerAdmin` as a manual admin fallback. Additionally, let
registered users change their own display name.

## Current state (for reference)
- Registration is admin-only: admin replies `/register` to a *forwarded* user message;
  `helpers.check_forwarded_from` reads `reply_to_message.forward_from`. Breaks silently when
  the user has "link forwarded messages to my account" disabled.
- Unregistered users hit `on_not_registered` → static "DM the admin" message. No self-serve path.
- `players.display_name` column exists, is set to `None` on creation, and is never editable.
  `Player.name()` already prefers `display_name` when present — so the name feature only needs
  a writer + command.
- One global catch-all callback handler (`@bot.callback_query_handler(lambda m: True)`) assumes
  every callback is a bet (`b_`/`l_` regex) and calls `get_player()` which asserts registration.

---

## Workstream 1 — Admin approval queue (gated signup)

### 1.1 Data model (`betbot/database.py`)
Add a `PendingRequests` table + accessor class (pattern: mirror `Players`/`DbTable`).

```
CREATE TABLE IF NOT EXISTS pending_requests (
    id integer PRIMARY KEY,          -- telegram user id
    first_name text,
    last_name text,
    username text,
    requested_at text not null        -- ISO utc
)
```
Methods: `addRequest(user)`, `getRequest(uid)`, `removeRequest(uid)`, `listRequests()`,
`isPending(uid)`. Wire into `Database.__init__` next to `self.players`.

### 1.2 New `Players` writer
- `changeName(pid, display_name)` → `UPDATE players SET display_name=? WHERE id=?`.
  (Reused by Workstream 2.)

### 1.3 Bot handlers (`betbot/bot.py`)
**Ordering matters** — telebot uses first-match-wins. These must be registered **before** the
generic `on_not_registered` catch-all.

- `/start` and `/join` (private chat, unregistered user):
  - If already registered → friendly "you're already in" + help.
  - If already pending → "your request is pending, hang tight."
  - Else → `pending.addRequest(user)`, confirm to user, and notify the admin
    (`config["admin_id"]`) with an inline keyboard:
    `Approve ✅` (`approve_<uid>`) / `Reject ❌` (`reject_<uid>`), showing name + @username + id.
- Update `on_not_registered`: instead of static text, attach a **"Request access"** inline
  button (`callback_data=join_request`) so existing unregistered users have an obvious entry point.

### 1.4 Approval callback handler
Add a **dedicated** `@bot.callback_query_handler` for `approve_` / `reject_` / `join_request`,
registered **before** the betting catch-all, so it doesn't fall through to the `b_`/`l_` parser.

- `join_request` → same as `/join` for `query.from_user`.
- `approve_<uid>` (admin only): pull the pending record, `db_helper.register_player(...)` using
  stored name fields, remove from pending, DM the user the welcome (`START_MSG` + `HELP_MSG`),
  and edit the admin message to "✅ Approved {name}".
- `reject_<uid>` (admin only): remove from pending, DM the user a polite rejection, edit admin
  message to "❌ Rejected {name}".
- Guard: ignore taps from non-admins; handle already-registered / already-handled (stale button)
  gracefully.

> Note: `register_player` currently takes a `user` object (uses `.id/.first_name/.last_name`).
> Either build a small shim from the pending row or add a `register_player_by_fields(...)`
> variant. Prefer the latter to avoid faking telebot user objects.

### 1.5 Keep the fallback
Leave `/register`, `/registerAdmin`, `check_forwarded_from`, `change_queen` untouched.

---

## Workstream 2 — Self-serve name change

### 2.1 Command (`betbot/bot.py`)
- `/setname <new name>` (private chat, registered users):
  - No argument → reply with current name + usage hint (and how to reset).
  - With argument → validate, `players.changeName(pid, cleaned)`, confirm.
- Optional `/myname` to just display the current name.
- Validation in `helpers`: strip whitespace, reject empty, cap length (e.g. ≤ 64 chars), strip
  Markdown control chars to avoid breaking `parse_mode="Markdown"` renders elsewhere.

`Player.name()` already returns `display_name` first, so leaderboards/scores update automatically.

---

## Workstream 3 — Copy / messages (`betbot/messages.py`)
Add (Russian, matching existing tone):
- `REQUEST_RECEIVED`, `REQUEST_PENDING`, `REQUEST_APPROVED_USER`, `REQUEST_REJECTED_USER`
- Admin notify: `NEW_REQUEST_ADMIN` (+ button labels `APPROVE_BUTTON`, `REJECT_BUTTON`,
  `REQUEST_ACCESS_BUTTON`)
- `NAME_CHANGED`, `NAME_USAGE`, `NAME_TOO_LONG`
- Extend `NOT_REGISTERED` to mention the Request-access button.
- Add `/setname` (and self-signup note) to `HELP_MSG`; add nothing new to `ADMIN_HELP_MSG`
  except optionally `/setname`.

---

## Workstream 4 — Tests (`test_bot.py`)
Extend existing pytest suite:
- `pending_requests` CRUD round-trip.
- `/join` creates a pending row + admin notification; duplicate `/join` is idempotent.
- `approve_<uid>` registers the player and clears pending; `reject_<uid>` clears without
  registering; non-admin taps are ignored.
- `/setname` updates `display_name` and is reflected by `Player.name()`; empty/too-long rejected.
- Regression: a normal `b_...` bet callback still routes to the betting handler (ordering check).

---

## Sequencing
1. DB: `PendingRequests` table/class + `changeName`. (foundation)
2. Messages copy.
3. `/setname` (smallest, self-contained — ship first to de-risk).
4. `/join` + `/start` + updated `on_not_registered`.
5. Approval callback handler (the trickiest bit — callback ordering).
6. Tests + manual end-to-end with two Telegram accounts (one admin, one new user).

## Risks / watch-outs
- **Callback ordering**: the new approval handler must be declared before the `lambda m: True`
  betting handler, or approvals get swallowed and error out.
- **Handler ordering**: `/join` & `/start` must precede `on_not_registered`.
- **Markdown injection** in user-set names → sanitize before any Markdown send.
- **Admin DM reachability**: if the admin never started the bot, `send_message(admin_id, ...)`
  raises — wrap in try/except and log (mirror existing `_remind_players` pattern).
- **Stale buttons**: approving an already-approved/expired request should fail soft.

## Out of scope
Invite codes / deep-links, group-membership auto-gate, rate-limiting of requests, multi-admin
approval. (Easy follow-ups if desired.)
