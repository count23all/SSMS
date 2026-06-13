Stupidly Simple Messaging Service - for CLI AI agents to communicate to each other with minimal overhead

# SSMS — Stupidly Simple Messaging Service

A dependency-free message bus for a handful of cooperating AI agents. No database,
no server, no daemon — just a few small Python scripts over append-only JSONL logs.

## What it gives you

- **`get "Name"`** returns only *your unread* mail and marks it read — so you never
  re-read the same thing, and your context isn't burned scanning a growing file.
- **Per-message seen-by roster** — you can see exactly who has read each message.
- **Free-form identities** — any agent name works (`Claude A`, `Gemini`,
  `Deep Seek 4`); names are normalized for matching, no central registry, no enroll.
- **Deterministic archiving** — `archive.py` only moves messages everyone has
  already read; it never truncates a body or relies on one agent's judgement.
- **Safe under concurrency** — simultaneous posts are serialized by an OS lock
- **No message size limit** — bodies are stored verbatim (multi-line, full Unicode).

## The scripts

| script        | what it does                                              |
|---------------|-----------------------------------------------------------|
| `get.py`      | fetch + consume my unread (the everyday read)             |
| `put.py`      | post a message                                            |
| `history.py`  | read-only look-back / single message / roster             |
| `archive.py`  | move fully-read messages out of the live logs             |
| `ssms_core.py`| shared core (lock, ids, JSONL, normalize, unread/seen)    |
| `test_ssms.py`| self-test                                                 |

### get.py — read your mail
```
python get.py "Claude A"            # your unread, oldest-first, marked read
python get.py "Claude A" --peek     # don't mark read
python get.py "Claude A" --count    # just the number unread
python get.py "Claude A" --json     # machine-readable
```

### put.py — send
```
python put.py "Claude A" --to "Claude B" "Codex" --msg "the message"
python put.py "Claude A" --to all --msg "broadcast to everyone"
python put.py "Claude A" --to "Claude B" --msg - < longnote.txt    # body from stdin
python put.py "Claude A" --to "Claude B" --msg-file note.md        # body from a file
python put.py "Claude A" --to "Claude B" --msg "..." --subject "topic"
```
- First positional = **sender**. `--to` delimits **recipients** (so the sender can
  never be confused with a recipient; a sender listed under `--to` is dropped).

### history.py — look back (never consumes)
```
python history.py "Claude A"        # to/from Claude A, oldest-first
python history.py                   # whole bus, oldest-first
python history.py --id <id>         # one message, full body + seen_by
python history.py --agents          # roster + per-agent unread counts
```

### archive.py — maintenance
```
python archive.py --dry-run         # show what would be archived
python archive.py --keep 200        # keep 200 most-recent live; archive read+older
```

## Where data lives

By default the scripts read/write a `data/` folder next to them, and archives go to
`archive/`. Point them elsewhere with `--home <dir>` or the `SSMS_HOME` env var, so
several projects can share one store. Files:

```
data/messages.jsonl   # one message per line (immutable)
data/receipts.jsonl   # one read-receipt per line (who saw what)
data/.lock            # write-serialization lock
archive/messages_<date>.jsonl, receipts_<date>.jsonl
```

## Data model

Message (one JSON object per line):
```json
{"id":"0001781330105747-d7b1","ts":"2026-06-13T...Z",
 "from":"claude a","from_label":"Claude A",
 "to":["claude b","codex"],"to_labels":["Claude B","Codex"],
 "subject":"...","body":"..."}
```
Receipts are a separate append-only log (`{"msg_id","agent","ts"}`), so a message
line is never rewritten — that's what makes concurrent writes safe. `seen_by` and
"unread for X" are *derived* from receipts at read time.

`id` is a 13-digit millisecond timestamp + random suffix: it sorts
chronologically, is unique even under simultaneous posts (minted while holding the
lock), and needs no central counter.

## Identity

Names are free-form and normalized for matching only (lowercased,
whitespace/`-`/`_` collapsed): `"Claude A"`, `"claude a"`, `"claude-a"` are the
same agent; the original spelling is kept for display. `all` is the one reserved
word (broadcast).

## How to use
Drop the SSMS package into your project directory, update the agent/claude/gemini.MD file for each agent you are running this project space to include the agent instructions. On session run, give each agent a name (Claude A, B, C, Codex A, B, C...) and then it should kick off. At most you might have to remind the AIs to engage a monitor/loop to check the "get" function when not actively working, or use a hook/skill as compatible. 
