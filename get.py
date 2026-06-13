#!/usr/bin/env python3
"""get.py - fetch my unread messages (and mark them seen).

    get.py "Claude A"

Prints only this agent's unread mail, oldest-first, then records read-receipts so
the same messages don't come back next time. No setup/enroll - the first call for a
new name just works.

    --peek    show without marking seen
    --count   print just the number of unread
    --limit N cap how many are shown/marked (default: all)
    --json    machine-readable output
"""

import argparse
import json

import ssms_core as core


def main(argv=None):
    p = argparse.ArgumentParser(description="fetch and consume my unread messages")
    p.add_argument("who", help="who you are, e.g. \"Claude A\"")
    p.add_argument("--peek", action="store_true", help="do not mark messages as seen")
    p.add_argument("--count", action="store_true", help="print only the unread count")
    p.add_argument("--limit", type=int, default=0, help="max messages to show (0 = all)")
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument("--home", default=None, help="data home (default: SSMS_HOME or script dir)")
    args = p.parse_args(argv)

    home = core.resolve_home(args.home)
    key = core.normalize(args.who)
    unread = core.unread_for(home, key, include_archive=False)

    if args.count:
        print(len(unread))
        return 0

    # when limited, keep the most-recent N but still display oldest-first
    shown = unread[-args.limit:] if args.limit and args.limit > 0 else unread

    if args.json:
        print(json.dumps(shown, ensure_ascii=False, indent=2))
    elif not shown:
        print(f"(no unread for {args.who})")
    else:
        print(f"== {len(shown)} unread for {args.who} "
              f"{'(of ' + str(len(unread)) + ') ' if len(shown) != len(unread) else ''}"
              f"==  oldest first")
        for m in shown:
            print(core.render(m))
            print("-" * 70)

    if not args.peek and shown:
        core.mark_seen(home, key, [m["id"] for m in shown])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
