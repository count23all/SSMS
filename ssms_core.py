"""SSMS - Stupidly Simple Messaging Service (shared core).

All the tricky bits live here once: store paths, the write lock, id minting,
JSONL append/parse, name normalization, and unread/seen derivation. The put/get/
history/archive scripts are thin wrappers around these helpers.

No third-party dependencies - stdlib only.
"""

from __future__ import annotations

import json
import os
import sys
import time
import datetime as _dt

# ---------------------------------------------------------------------------
# Store location
# ---------------------------------------------------------------------------

def resolve_home(explicit: str | None) -> str:
    """Pick the data home: --home arg > SSMS_HOME env > this file's directory."""
    home = explicit or os.environ.get("SSMS_HOME") or os.path.dirname(os.path.abspath(__file__))
    home = os.path.abspath(home)
    os.makedirs(os.path.join(home, "data"), exist_ok=True)
    os.makedirs(os.path.join(home, "archive"), exist_ok=True)
    return home


def _data(home: str, name: str) -> str:
    return os.path.join(home, "data", name)


def messages_path(home: str) -> str:
    return _data(home, "messages.jsonl")


def receipts_path(home: str) -> str:
    return _data(home, "receipts.jsonl")


def lock_path(home: str) -> str:
    return _data(home, ".lock")


def archive_dir(home: str) -> str:
    return os.path.join(home, "archive")


# ---------------------------------------------------------------------------
# Identity normalization (free-form names -> a stable match key)
# ---------------------------------------------------------------------------

def normalize(name: str) -> str:
    """'Claude A', 'claude-a', 'claude_a' -> 'claude a'. 'all' stays 'all'."""
    s = (name or "").strip().lower()
    for ch in ("-", "_", "\t", "\n"):
        s = s.replace(ch, " ")
    s = " ".join(s.split())
    return s


# ---------------------------------------------------------------------------
# Cross-platform write lock (OS advisory lock - auto-released on crash)
# ---------------------------------------------------------------------------

class FileLock:
    def __init__(self, path: str, timeout: float = 10.0):
        self.path = path
        self.timeout = timeout
        self.f = None

    def __enter__(self):
        self.f = open(self.path, "a+")
        if os.name == "nt":
            import msvcrt
            deadline = time.time() + self.timeout
            while True:
                try:
                    self.f.seek(0)
                    msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
                    return self
                except OSError:
                    if time.time() >= deadline:
                        raise TimeoutError(f"ssms: could not acquire write lock ({self.path})")
                    time.sleep(0.05)
        else:
            import fcntl
            fcntl.flock(self.f.fileno(), fcntl.LOCK_EX)
            return self

    def __exit__(self, *exc):
        try:
            if os.name == "nt":
                import msvcrt
                self.f.seek(0)
                try:
                    msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl
                fcntl.flock(self.f.fileno(), fcntl.LOCK_UN)
        finally:
            self.f.close()
            self.f = None


# ---------------------------------------------------------------------------
# Time / ids
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
        f"{_dt.datetime.now(_dt.timezone.utc).microsecond // 1000:03d}Z"


def mint_id() -> str:
    """Sortable, monotonic-ish, collision-free id. Minted while holding the lock.

    13-digit zero-padded millisecond timestamp (sorts lexically == chronologically,
    good past year 2286) + 4 random hex. Ties within a millisecond break by file
    insertion order, which is the true order anyway.
    """
    ms = time.time_ns() // 1_000_000
    return f"{ms:013d}-{os.urandom(2).hex()}"


# ---------------------------------------------------------------------------
# JSONL read (lock-free; tolerates a partial trailing line mid-write)
# ---------------------------------------------------------------------------

def _read_jsonl(path: str) -> list[dict]:
    """Read a stream of JSON records. Tolerant of BOTH layouts:
    compact one-per-line, and pretty-printed multi-line records separated by blank
    lines. Uses raw_decode so internal newlines in a record don't matter, and a
    half-written trailing record (concurrent writer) is simply dropped.
    """
    out: list[dict] = []
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    dec = json.JSONDecoder()
    idx, n = 0, len(text)
    while idx < n:
        while idx < n and text[idx] in " \t\r\n":
            idx += 1
        if idx >= n:
            break
        try:
            obj, end = dec.raw_decode(text, idx)
        except json.JSONDecodeError:
            break  # partial/garbage tail (e.g. a concurrent half-written record)
        out.append(obj)
        idx = end
    return out


def _archive_files(home: str, kind: str) -> list[str]:
    d = archive_dir(home)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d)
                  if f.startswith(f"{kind}_") and f.endswith(".jsonl"))


def load_messages(home: str, include_archive: bool = False) -> list[dict]:
    msgs = _read_jsonl(messages_path(home))
    if include_archive:
        for f in _archive_files(home, "messages"):
            msgs += _read_jsonl(f)
    return msgs


def load_receipts(home: str, include_archive: bool = False) -> list[dict]:
    r = _read_jsonl(receipts_path(home))
    if include_archive:
        for f in _archive_files(home, "receipts"):
            r += _read_jsonl(f)
    return r


# ---------------------------------------------------------------------------
# Derived views
# ---------------------------------------------------------------------------

def seen_map(home: str, include_archive: bool = False) -> dict:
    m: dict[str, set] = {}
    for r in load_receipts(home, include_archive):
        m.setdefault(r["msg_id"], set()).add(r["agent"])
    return m


def labels_map(home: str, include_archive: bool = True) -> dict:
    """Best-known display label for each normalized key (last write wins)."""
    out: dict[str, str] = {}
    for msg in load_messages(home, include_archive):
        if msg.get("from"):
            out[msg["from"]] = msg.get("from_label", msg["from"])
        for k, lbl in zip(msg.get("to", []), msg.get("to_labels", [])):
            out[k] = lbl
    return out


def roster(home: str, include_archive: bool = True) -> set:
    keys: set = set()
    for msg in load_messages(home, include_archive):
        if msg.get("from"):
            keys.add(msg["from"])
        for k in msg.get("to", []):
            if k != "all":
                keys.add(k)
    for r in load_receipts(home, include_archive):
        keys.add(r["agent"])
    keys.discard("all")
    return keys


def addressed_to(msg: dict, who_key: str) -> bool:
    to = msg.get("to", [])
    return who_key in to or "all" in to


def unread_for(home: str, who_key: str, include_archive: bool = False) -> list[dict]:
    seen = seen_map(home, include_archive)
    out = []
    for msg in load_messages(home, include_archive):
        if msg.get("from") == who_key:
            continue
        if not addressed_to(msg, who_key):
            continue
        if who_key in seen.get(msg["id"], ()):
            continue
        out.append(msg)
    out.sort(key=lambda m: m["id"])  # oldest first (chronological)
    return out


def involving(home: str, who_key: str, include_archive: bool = True) -> list[dict]:
    out = [m for m in load_messages(home, include_archive)
           if m.get("from") == who_key or addressed_to(m, who_key)]
    out.sort(key=lambda m: m["id"])  # oldest first (chronological)
    return out


# ---------------------------------------------------------------------------
# Writes (all take the lock)
# ---------------------------------------------------------------------------

def post_message(home: str, sender: str, recipients: list[str], body: str,
                 subject: str = "") -> dict:
    from_key = normalize(sender)
    to_keys, to_labels = [], []
    seen_keys = set()
    for r in recipients:
        k = normalize(r)
        if not k or k == from_key or k in seen_keys:
            continue  # drop blanks, self, dupes
        seen_keys.add(k)
        to_keys.append(k)
        to_labels.append(r.strip())
    if not to_keys:
        raise ValueError("no valid recipients (after dropping blanks/self/dupes)")
    with FileLock(lock_path(home)):
        msg = {
            "id": mint_id(),
            "ts": _now_iso(),
            "from": from_key,
            "from_label": sender.strip(),
            "to": to_keys,
            "to_labels": to_labels,
            "subject": subject or "",
            "body": body if body is not None else "",
        }
        with open(messages_path(home), "a", encoding="utf-8") as fh:
            # pretty-printed + blank line so the file is human-readable; the reader
            # parses this and the old compact layout transparently
            fh.write(json.dumps(msg, ensure_ascii=False, indent=2) + "\n\n")
            fh.flush()
            os.fsync(fh.fileno())
    return msg


def mark_seen(home: str, who_key: str, msg_ids: list[str]) -> int:
    if not msg_ids:
        return 0
    ts = _now_iso()
    with FileLock(lock_path(home)):
        with open(receipts_path(home), "a", encoding="utf-8") as fh:
            for mid in msg_ids:
                fh.write(json.dumps({"msg_id": mid, "agent": who_key, "ts": ts},
                                    ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    return len(msg_ids)


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def age(ts: str) -> str:
    try:
        when = _dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return "?"
    secs = max(0, int((_dt.datetime.now(_dt.timezone.utc) - when).total_seconds()))
    for unit, n in (("d", 86400), ("h", 3600), ("m", 60)):
        if secs >= n:
            return f"{secs // n}{unit}"
    return f"{secs}s"


def render(msg: dict, seen: set | None = None, oneline: bool = False) -> str:
    to = " + ".join(msg.get("to_labels") or msg.get("to", []))
    head = f"[{msg['id'][-6:]}] {msg.get('from_label', msg.get('from'))} -> {to}  ({age(msg['ts'])})"
    if msg.get("subject"):
        head += f"  | {msg['subject']}"
    if seen is not None:
        head += f"  | seen_by: {', '.join(sorted(seen)) or '-'}"
    if oneline:
        first = (msg.get("body", "").splitlines() or [""])[0]
        return head + (f"\n    {first}" if first else "")
    body = "\n".join("    " + ln for ln in msg.get("body", "").splitlines())
    return head + ("\n" + body if body else "")
