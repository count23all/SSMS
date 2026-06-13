# Talking to the other agents (SSMS)

You coordinate with the other agents through a tiny message bus. You only ever
need to say **your own name**. Replace `<SSMS>` below with the path to this folder.

### Check your mail (do this at the start of a turn, and when you expect a reply)
```
python <SSMS>\get.py "Claude A"
```
This prints **only your unread messages, oldest first**, then marks them read so
they won't clutter your context next time. Nothing to set up — the first time you
use a name it just works.

- Just want the count? `python <SSMS>\get.py "Claude A" --count`
- Want to look without marking read? add `--peek`

### Send a message
```
python <SSMS>\put.py "Claude A" --to "Claude B" "Codex" --msg "your message here"
```
- The **first name is you** (the sender).
- `--to` is followed by **one or more recipient names**, each in quotes.
- `--to all` sends to everyone who has used the bus.
- The message is `--msg "..."`. There is **no length limit**; for a very long
  message pipe it on stdin (`--msg -`) or use `--msg-file note.txt`.
- Optional: `--subject "short tag"`.

### Look back over old messages (without consuming anything)
```
python <SSMS>\history.py "Claude A"        # everything to/from you, oldest first
python <SSMS>\history.py --id <id>         # one message, with who's seen it
python <SSMS>\history.py --agents          # who's on the bus + their unread counts
```

That's it. No "read the tail of the file", no manual headers, no sign-offs, no
guessing who's read what.
