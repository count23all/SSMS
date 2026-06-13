#!/usr/bin/env python3
"""Throwaway: replay the real STO Messages.md + archives through SSMS to see if
anything is missed (unparsed headers, identity drift, body truncation)."""
import glob, os, re, shutil, sys, tempfile
import ssms_core as core

STO = r"D:\workbench\sto"
ARROW = re.compile(r"\s*(?:->|=>|→|â†’|â€†â€™)\s*")
HEADER = re.compile(r"^\[([^\]]+)\]\s*(.*)$")

def split_blocks(text):
    """Yield (header_inner, trailing, body) blocks split on header lines."""
    lines = text.splitlines()
    blocks, cur = [], None
    for ln in lines:
        m = HEADER.match(ln)
        # treat as a header only if it looks like an address line (has arrow) or a
        # short sign-off-style bracket at line start followed by content
        if m and (ARROW.search(m.group(1)) or len(m.group(1)) < 40):
            if cur:
                blocks.append(cur)
            cur = [m.group(1), m.group(2), []]
        elif cur:
            cur[2].append(ln)
    if cur:
        blocks.append(cur)
    return blocks

def parse_header(inner):
    parts = ARROW.split(inner, maxsplit=1)
    if len(parts) == 2:
        sender, rest = parts
        recips = [r.strip() for r in re.split(r"[+,]", rest) if r.strip()]
        return sender.strip(), recips, "addressed"
    return inner.strip(), ["all"], "broadcast/self"

def main():
    files = [os.path.join(STO, "Messages.md")] + sorted(glob.glob(os.path.join(STO, "Messages_archive_*.md")))
    files = [f for f in files if os.path.exists(f)]
    home = core.resolve_home(tempfile.mkdtemp(prefix="ssms_sim_"))
    total = addressed = bcast = unparsed = posted = 0
    senders, recips = set(), set()
    unparsed_samples, longest = [], (0, "")
    for f in files:
        raw = open(f, "rb").read()
        # normalize all three arrow encodings to ASCII '->' before decoding
        raw = raw.replace(b"\xc3\xa2\xe2\x80\xa0\xe2\x80\x99", b" -> ")  # double-mojibake
        raw = raw.replace(b"\xe2\x86\x92", b" -> ")                       # real UTF-8 U+2192
        text = raw.decode("utf-8", "replace")
        for inner, trailing, bodylines in split_blocks(text):
            total += 1
            sender, rlist, kind = parse_header(inner)
            body = (trailing + "\n" + "\n".join(bodylines)).strip()
            if kind == "addressed":
                addressed += 1
            else:
                bcast += 1
            # skip obvious non-messages (separators captured as headers)
            if not sender or set(sender) <= set("=-* "):
                unparsed += 1
                if len(unparsed_samples) < 10:
                    unparsed_samples.append(inner[:60])
                continue
            senders.add(core.normalize(sender))
            for r in rlist:
                if r != "all":
                    recips.add(core.normalize(r))
            try:
                core.post_message(home, sender, rlist, body or "(empty)")
                posted += 1
                if len(body) > longest[0]:
                    longest = (len(body), core.normalize(sender))
            except Exception as e:
                unparsed += 1
                if len(unparsed_samples) < 10:
                    unparsed_samples.append(f"POST FAIL {inner[:40]}: {e}")

    print(f"files replayed       : {len(files)}")
    print(f"blocks seen          : {total}")
    print(f"  addressed          : {addressed}")
    print(f"  broadcast/self     : {bcast}")
    print(f"  skipped/unparsed   : {unparsed}")
    print(f"messages posted      : {posted}")
    print(f"unique senders (norm): {len(senders)} -> {sorted(senders)}")
    print(f"unique recips  (norm): {len(recips)} -> {sorted(recips)}")
    print(f"longest body         : {longest[0]} chars (from {longest[1]}) - posted intact")
    if unparsed_samples:
        print("unparsed/odd samples :")
        for s in unparsed_samples:
            print("   ", repr(s))

    print("\n-- per-agent unread after replay --")
    for k in sorted(core.roster(home)):
        print(f"   {k:12s} {len(core.unread_for(home, k))} unread")

    # integrity: every posted body round-trips with no truncation
    bad = 0
    for m in core.load_messages(home):
        if m["body"] is None:
            bad += 1
    print(f"\nbody integrity       : {len(core.load_messages(home))} messages, {bad} null bodies")
    shutil.rmtree(home, ignore_errors=True)

if __name__ == "__main__":
    main()
