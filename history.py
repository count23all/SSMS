#!/usr/bin/env python3
"""history.py - read-only look-back over the bus (never consumes anything).

    history.py "Claude A"      # messages to/from Claude A, oldest-first
    history.py                 # the whole bus, oldest-first
    history.py --id <id>       # one message, full body + who's seen it
    history.py --agents        # who has appeared + each one's unread count

Reads through archived files too, so look-back survives archiving.
"""

import argparse
import json

import ssms_core as core


def _show_one(home, msg_id):
    msgs = {m["id"]: m for m in core.load_messages(home, include_archive=True)}
    seen = core.seen_map(home, include_archive=True)
    if msg_id not in msgs:
        # allow short id suffix match
        cand = [m for m in msgs.values() if m["id"].endswith(msg_id)]
        if len(cand) == 1:
            msg_id = cand[0]["id"]
        elif not cand:
            print(f"(no message matching {msg_id})")
            return 1
        else:
            print(f"(ambiguous id {msg_id}; matches {len(cand)})")
            return 1
    print(core.render(msgs[msg_id], seen=seen.get(msg_id, set())))
    return 0


def _show_agents(home):
    keys = core.roster(home)
    labels = core.labels_map(home)
    rows = []
    for k in sorted(keys):
        n = len(core.unread_for(home, k, include_archive=False))
        rows.append((labels.get(k, k), n))
    if not rows:
        print("(no agents yet)")
        return 0
    w = max(len(lbl) for lbl, _ in rows)
    print("agent" + " " * (w - 5) + "   unread")
    for lbl, n in rows:
        print(f"{lbl.ljust(w)}   {n}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="read-only look-back over the SSMS bus")
    p.add_argument("who", nargs="?", default=None, help="filter to this agent (from or to)")
    p.add_argument("--id", default=None, help="show one message, full body + who's seen it")
    p.add_argument("--agents", action="store_true", help="list roster + unread counts")
    p.add_argument("--limit", type=int, default=30, help="max messages (default 30)")
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument("--home", default=None, help="data home (default: SSMS_HOME or script dir)")
    args = p.parse_args(argv)

    home = core.resolve_home(args.home)

    if args.agents:
        return _show_agents(home)
    if args.id:
        return _show_one(home, args.id)

    if args.who:
        msgs = core.involving(home, core.normalize(args.who), include_archive=True)
    else:
        msgs = sorted(core.load_messages(home, include_archive=True),
                      key=lambda m: m["id"])  # oldest first
    # keep the most-recent N when limited, but still display oldest-first
    if args.limit and args.limit > 0:
        msgs = msgs[-args.limit:]

    seen = core.seen_map(home, include_archive=True)
    if args.json:
        print(json.dumps(msgs, ensure_ascii=False, indent=2))
    elif not msgs:
        print("(no messages)")
    else:
        for m in msgs:
            print(core.render(m, seen=seen.get(m["id"], set()), oneline=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
