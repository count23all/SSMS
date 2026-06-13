#!/usr/bin/env python3
"""archive.py - deterministic archiving (occasional maintenance).

Moves fully-seen messages out of the live logs into archive/messages_<date>.jsonl
(+ their receipts), keeping the most recent N live regardless. "Fully seen" means
every addressee has a read-receipt; for a broadcast (`all`), every agent on the
roster except the sender. No date math, no judgement calls, no truncation - it only
moves what everyone has already read.

    archive.py --dry-run     # show what would move
    archive.py --keep 200    # keep 200 most-recent messages live (default 200)
"""

import argparse
import datetime as _dt
import json
import os

import ssms_core as core


def _fully_seen(msg, seen, roster):
    got = seen.get(msg["id"], set())
    if "all" in msg.get("to", []):
        targets = roster - {msg.get("from")}
    else:
        targets = set(msg.get("to", []))
    return bool(targets) and targets.issubset(got)


def main(argv=None):
    p = argparse.ArgumentParser(description="archive fully-seen messages")
    p.add_argument("--keep", type=int, default=200, help="keep N most-recent live (default 200)")
    p.add_argument("--dry-run", action="store_true", help="show candidates, change nothing")
    p.add_argument("--home", default=None, help="data home (default: SSMS_HOME or script dir)")
    args = p.parse_args(argv)

    home = core.resolve_home(args.home)

    with core.FileLock(core.lock_path(home)):
        msgs = sorted(core._read_jsonl(core.messages_path(home)), key=lambda m: m["id"])
        receipts = core._read_jsonl(core.receipts_path(home))
        seen = {}
        for r in receipts:
            seen.setdefault(r["msg_id"], set()).add(r["agent"])
        rost = set()
        for m in msgs:
            rost.add(m.get("from"))
            rost.update(k for k in m.get("to", []) if k != "all")
        rost.discard("all")
        rost.discard(None)

        keep_recent = set(m["id"] for m in msgs[-args.keep:]) if args.keep > 0 else set()
        move = [m for m in msgs if m["id"] not in keep_recent and _fully_seen(m, seen, rost)]
        move_ids = set(m["id"] for m in move)

        if args.dry_run:
            print(f"would archive {len(move)} of {len(msgs)} messages "
                  f"(keeping {args.keep} most recent live):")
            for m in move:
                print(f"  {m['id']}  {m.get('from_label')} -> {' + '.join(m.get('to_labels', []))}")
            return 0

        if not move:
            print("nothing to archive (no fully-seen messages outside the keep window)")
            return 0

        date = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
        amsg = os.path.join(core.archive_dir(home), f"messages_{date}.jsonl")
        arcp = os.path.join(core.archive_dir(home), f"receipts_{date}.jsonl")

        with open(amsg, "a", encoding="utf-8") as fh:
            for m in move:
                fh.write(json.dumps(m, ensure_ascii=False, indent=2) + "\n\n")
        moved_receipts = [r for r in receipts if r["msg_id"] in move_ids]
        with open(arcp, "a", encoding="utf-8") as fh:
            for r in moved_receipts:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

        # rewrite live files without the moved entries (atomic via temp + replace)
        _rewrite(core.messages_path(home), [m for m in msgs if m["id"] not in move_ids], pretty=True)
        _rewrite(core.receipts_path(home), [r for r in receipts if r["msg_id"] not in move_ids], pretty=False)

    print(f"archived {len(move)} messages + {len(moved_receipts)} receipts -> {os.path.basename(amsg)}")
    return 0


def _rewrite(path, rows, pretty=False):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for r in rows:
            if pretty:
                fh.write(json.dumps(r, ensure_ascii=False, indent=2) + "\n\n")
            else:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


if __name__ == "__main__":
    raise SystemExit(main())
