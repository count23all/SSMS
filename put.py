#!/usr/bin/env python3
"""put.py - post a message to the bus.

    put.py "Claude A" --to "Gemini" "Deep Seek 4" -m "the message body"

First positional is the SENDER (you, reporting yourself). --to introduces one or
more recipient names (or the single word `all` to broadcast). The body is --msg,
or piped on stdin (--msg -), or --msg-file FILE for anything large. No length limit.
"""

import argparse
import sys

import ssms_core as core


def main(argv=None):
    p = argparse.ArgumentParser(description="post a message to the SSMS bus")
    p.add_argument("sender", help="who you are, e.g. \"Claude A\"")
    p.add_argument("--to", nargs="+", required=True, metavar="NAME",
                   help='recipient name(s), each quoted; or the word "all" to broadcast')
    p.add_argument("--msg", help='message body; use "-" to read from stdin')
    p.add_argument("--msg-file", help="read the body from this file (for long messages)")
    p.add_argument("--subject", default="", help="optional short subject")
    p.add_argument("--home", default=None, help="data home (default: SSMS_HOME or script dir)")
    args = p.parse_args(argv)

    if args.msg_file:
        with open(args.msg_file, "r", encoding="utf-8") as fh:
            body = fh.read()
    elif args.msg is None or args.msg == "-":
        body = sys.stdin.read()
    else:
        body = args.msg

    home = core.resolve_home(args.home)
    try:
        msg = core.post_message(home, args.sender, args.to, body,
                                subject=args.subject)
    except ValueError as e:
        p.error(str(e))
        return 2

    to = " + ".join(msg["to_labels"])
    print(f"posted {msg['id']}  {msg['from_label']} -> {to}  ({len(body)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
