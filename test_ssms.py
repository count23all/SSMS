#!/usr/bin/env python3
"""Self-test for SSMS. Runs the full flow against a throwaway temp store and
asserts the invariants. Run: python test_ssms.py
"""

import os
import shutil
import tempfile

import ssms_core as core


def main():
    home = tempfile.mkdtemp(prefix="ssms_test_")
    try:
        run(home)
        print("\nALL TESTS PASSED")
        return 0
    finally:
        shutil.rmtree(home, ignore_errors=True)


def run(home):
    home = core.resolve_home(home)

    # post: sender + multiple recipients
    m1 = core.post_message(home, "Claude A", ["Claude B", "Gemini"], "first message", subject="hi")
    assert m1["from"] == "claude a"
    assert m1["to"] == ["claude b", "gemini"], m1["to"]
    print("post 1 ok:", m1["id"])

    # unread visible to addressee, name normalizes
    u = core.unread_for(home, core.normalize("claude-b"))
    assert len(u) == 1 and u[0]["id"] == m1["id"], u
    # not visible to a non-addressee
    assert core.unread_for(home, core.normalize("Codex")) == []
    print("unread targeting ok")

    # mark seen -> no longer unread, seen_by reflects it
    core.mark_seen(home, core.normalize("Claude B"), [m1["id"]])
    assert core.unread_for(home, core.normalize("Claude B")) == []
    assert "claude b" in core.seen_map(home)[m1["id"]]
    print("mark-seen / seen_by ok")

    # sender never gets own message; self in --to is dropped
    m2 = core.post_message(home, "Claude A", ["Claude A", "Claude B"], "no self delivery")
    assert m2["to"] == ["claude b"], m2["to"]
    assert core.unread_for(home, core.normalize("Claude A")) == []
    print("no-self-delivery ok")

    # broadcast reaches everyone who has appeared (except sender)
    bcast = core.post_message(home, "Gemini", ["all"], "to everyone")
    assert any(m["id"] == bcast["id"] for m in core.unread_for(home, core.normalize("Claude A")))
    assert any(m["id"] == bcast["id"] for m in core.unread_for(home, core.normalize("Claude B")))
    # sender never receives its own broadcast
    assert all(m["id"] != bcast["id"] for m in core.unread_for(home, core.normalize("Gemini")))
    print("broadcast ok")

    # oldest-first ordering (chronological)
    ids = [m["id"] for m in core.unread_for(home, core.normalize("Claude B"))]
    assert ids == sorted(ids)
    print("ordering ok")

    # no length / unicode truncation
    big = ("x" * 50000) + "\n многострочный\nUnicode: — ✓ \U0001f680\n" + ("y" * 50000)
    m3 = core.post_message(home, "Codex", ["Claude A"], big)
    got = [m for m in core.load_messages(home) if m["id"] == m3["id"]][0]
    assert got["body"] == big, "body was altered/truncated!"
    print(f"no-truncation ok ({len(big)} chars round-tripped exactly)")

    # roster derived without enrollment
    r = core.roster(home)
    assert {"claude a", "claude b", "gemini", "codex"}.issubset(r), r
    print("derived roster ok:", sorted(r))


if __name__ == "__main__":
    raise SystemExit(main())
