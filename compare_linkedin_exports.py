#!/usr/bin/env python3
"""Compare the structure of two LinkedIn data export zips.

Reports: renamed / new / removed files, CSV column changes, JSON key changes,
and (with --counts) row-count / size deltas. Handles UTF-8 and UTF-16 CSVs,
comma / tab / semicolon / pipe delimiters, 'Notes:' preambles, and headerless
CSVs. Example values (from the NEW zip) are shown for new columns/keys; use
--samples 0 for a structure-only report that is safe to share.

Usage:
    python compare_linkedin_exports.py old.zip new.zip
    python compare_linkedin_exports.py old.zip new.zip --samples 0 --counts --out report.md
"""
import argparse
import csv
import io
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from itertools import islice

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

PLACEHOLDERS = {"n/a", "na", "none", "null", "nil", "-", "--"}
DATA_RE = re.compile(r"^(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4}|https?://|\d{1,3}(\.\d{1,3}){3}$)")
COLLAPSE_AT = 5  # collapse folders with this many files or more in added/removed lists


# ---------- CSV reading ----------
def detect_encoding(zf, name):
    with zf.open(name) as f:
        b = f.read(4)
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"
    if b[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    if len(b) >= 2 and b[0] != 0 and b[1] == 0:
        return "utf-16-le"
    return "utf-8-sig"


def detect_delimiter(zf, name, enc):
    with zf.open(name) as raw:
        sample = io.TextIOWrapper(raw, encoding=enc, errors="replace", newline="").read(65536)
    lines = sample.splitlines()
    if len(sample) >= 65536 and len(lines) > 1:
        lines = lines[:-1]
    lines = lines[:50]
    best, best_score = ",", 0.0
    for d in [",", "\t", ";", "|"]:
        lens = [len(r) for r in csv.reader(lines, delimiter=d) if r]
        if not lens:
            continue
        mode, cnt = Counter(lens).most_common(1)[0]
        score = mode * cnt / len(lens) if mode > 1 else 0
        if score > best_score:
            best, best_score = d, score
    return best


def iter_csv(zf, name):
    enc = detect_encoding(zf, name)
    delim = detect_delimiter(zf, name, enc)
    with zf.open(name) as raw:
        text = io.TextIOWrapper(raw, encoding=enc, errors="replace", newline="")
        for row in csv.reader(text, delimiter=delim):
            if row and any(c.strip() for c in row):
                yield row


def looks_like_data(row):
    return any(DATA_RE.match(c.strip()) or len(c) > 120 for c in row)


def find_header(head):
    """Return (index_of_header_row, headerless_flag)."""
    mode = Counter(len(r) for r in head).most_common(1)[0][0]
    idx = next(i for i, r in enumerate(head) if len(r) == mode)
    return idx, looks_like_data(head[idx])


def csv_info(zf, name):
    head, count = [], 0
    for row in iter_csv(zf, name):
        count += 1
        if len(head) < 50:
            head.append(row)
    if not head:
        return [], 0, False, 0
    idx, headerless = find_header(head)
    ncols = len(head[idx])
    if headerless:
        return [], count - idx, True, ncols
    header = [c.strip() for c in head[idx] if c.strip()]
    return header, max(count - idx - 1, 0), False, ncols


def json_keys(zf, name):
    try:
        with zf.open(name) as f:
            data = json.load(f)
    except Exception:
        return None
    if isinstance(data, list):
        data = next((x for x in data if isinstance(x, dict)), {})
    return sorted(data.keys()) if isinstance(data, dict) else []


def inventory(path):
    inv = {}
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename
            e = {"size": info.file_size, "header": None, "rows": None, "keys": None,
                 "headerless": False, "ncols": 0}
            low = name.lower()
            try:
                if low.endswith(".csv"):
                    e["header"], e["rows"], e["headerless"], e["ncols"] = csv_info(zf, name)
                elif low.endswith(".json"):
                    e["keys"] = json_keys(zf, name)
            except Exception as ex:  # keep going on a bad file
                print(f"warning: could not parse {name}: {ex}", file=sys.stderr)
            inv[name] = e
    return inv


# ---------- samples ----------
def sample_values(zf, name, cols, n, scan=5000):
    found = {c: [] for c in cols}
    low = name.lower()

    def add(c, v):
        if isinstance(v, (dict, list)):
            v = json.dumps(v)
        v = " ".join(str(v).split())
        if v.lower() in PLACEHOLDERS:
            return
        if v and v not in found[c] and len(found[c]) < n:
            found[c].append(v[:60] + ("..." if len(v) > 60 else ""))

    if low.endswith(".csv"):
        rows = list(islice(iter_csv(zf, name), scan))
        if not rows:
            return found
        idx, headerless = find_header(rows[:50])
        if headerless:
            return found
        pos = {}
        for i, c in enumerate(rows[idx]):
            if c.strip():
                pos.setdefault(c.strip(), i)
        for row in rows[idx + 1:]:
            for c in cols:
                if c in pos and pos[c] < len(row):
                    add(c, row[pos[c]])
            if all(len(v) >= n for v in found.values()):
                break
    elif low.endswith(".json"):
        try:
            with zf.open(name) as f:
                data = json.load(f)
        except Exception:
            return found
        items = data if isinstance(data, list) else [data]
        for item in items[:scan]:
            if isinstance(item, dict):
                for c in cols:
                    if c in item:
                        add(c, item[c])
            if all(len(v) >= n for v in found.values()):
                break
    return found


def sample_lines(sample, cols, indent="      "):
    if not sample or not cols:
        return []
    vals = sample(cols)
    return [f"{indent}{c}: " + " | ".join(vals[c]) for c in cols if vals[c]]


# ---------- diffing ----------
def key(name):
    """Normalise: lowercase, drop numeric-ID / _vN suffixes, ignore space/_/- differences."""
    n = name.lower()
    n = re.sub(r"_\d{5,}(?=\.)", "", n)
    n = re.sub(r"_v\d+(?=\.)", "", n)
    return re.sub(r"[ _\-]", "", n)


def base(name):
    return key(name.rsplit("/", 1)[-1])


def jaccard(a, b):
    a, b = set(a or []), set(b or [])
    return len(a & b) / len(a | b) if a | b else 0.0


def match_renames(removed, added, old, new, min_jaccard=0.6):
    pairs, rem, add = [], list(removed), list(added)

    def take(r, a, why):
        pairs.append((r, a, why))
        rem.remove(r)
        add.remove(a)

    for r in list(rem):  # pass 1: same normalised full path
        hit = next((a for a in add if key(a) == key(r)), None)
        if hit:
            take(r, hit, "name")
    rb, ab = defaultdict(list), defaultdict(list)  # pass 2: same normalised basename, unique both sides
    for r in rem:
        rb[base(r)].append(r)
    for a in add:
        ab[base(a)].append(a)
    for k, rs in rb.items():
        if len(rs) == 1 and len(ab.get(k, [])) == 1:
            take(rs[0], ab[k][0], "name, moved folder")
    cands = []  # pass 3: CSV column overlap
    for r in rem:
        for a in add:
            if old[r]["header"] and new[a]["header"]:
                j = jaccard(old[r]["header"], new[a]["header"])
                if j >= min_jaccard:
                    cands.append((j, r, a))
    for j, r, a in sorted(cands, reverse=True):
        if r in rem and a in add:
            take(r, a, f"columns {j:.0%} overlap")
    return pairs, rem, add


def list_diff(old, new):
    o, n = set(old), set(new)
    added = [c for c in new if c not in o]
    removed = [c for c in old if c not in n]
    moved = [c for c in old if c in n] != [c for c in new if c in o]
    return added, removed, moved


def schema_lines(o, n, sample=None):
    lines = []
    if o["headerless"] and not n["headerless"]:
        lines.append(f"  ~ old file had no header row ({o['ncols']} columns)")
    elif n["headerless"] and not o["headerless"]:
        lines.append(f"  ~ new file has no header row ({n['ncols']} columns)")
    if (o["header"] is not None and n["header"] is not None and o["header"] != n["header"]
            and not (o["headerless"] and n["headerless"])):
        a, r, moved = list_diff(o["header"], n["header"])
        if a:
            samples = sample_lines(sample, a)
            note = "  [no non-empty values found]" if sample and not samples else ""
            lines.append(f"  + new columns: {', '.join(a)}{note}")
            lines.extend(samples)
        if r:
            lines.append(f"  - removed columns: {', '.join(r)}")
        if moved and not a and not r:
            lines.append("  ~ columns reordered")
    if o["keys"] is not None and n["keys"] is not None and o["keys"] != n["keys"]:
        a, r, _ = list_diff(o["keys"], n["keys"])
        if a:
            lines.append(f"  + new JSON keys: {', '.join(a)}")
            lines.extend(sample_lines(sample, a))
        if r:
            lines.append(f"  - removed JSON keys: {', '.join(r)}")
    return lines


def collapse(files):
    """Yield (label, original_file_or_None); folders with many files become one line."""
    by_dir = defaultdict(list)
    for f in files:
        by_dir[f.rsplit("/", 1)[0] if "/" in f else ""].append(f)
    out = []
    for d, fs in sorted(by_dir.items()):
        if d and len(fs) >= COLLAPSE_AT:
            exts = Counter(f.rsplit(".", 1)[-1].lower() if "." in f.rsplit("/", 1)[-1] else "(none)" for f in fs)
            out.append((f"{d}/  ({len(fs)} files: " + ", ".join(f"{c} {e}" for e, c in exts.most_common()) + ")", None))
        else:
            out.extend((f, f) for f in sorted(fs))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old_zip")
    ap.add_argument("new_zip")
    ap.add_argument("--samples", type=int, default=3, metavar="N",
                    help="example values per new column/key (default 3; 0 = structure only)")
    ap.add_argument("--counts", action="store_true", help="also list row-count/size changes")
    ap.add_argument("--out", help="also write the report to this file")
    args = ap.parse_args()

    old, new = inventory(args.old_zip), inventory(args.new_zip)
    nz = zipfile.ZipFile(args.new_zip)

    def sampler_for(name):
        return (lambda cols: sample_values(nz, name, cols, args.samples)) if args.samples > 0 else None

    out = []
    p = out.append
    common = sorted(set(old) & set(new))
    pairs, removed_files, added_files = match_renames(
        sorted(set(old) - set(new)), sorted(set(new) - set(old)), old, new)

    p(f"# LinkedIn export comparison\n\nOld: {args.old_zip} ({len(old)} files)\nNew: {args.new_zip} ({len(new)} files)\n")

    p(f"## Renamed files ({len(pairs)})")
    for r, a, why in sorted(pairs):
        p(f"~ {r} -> {a}  [{why}]")
        out.extend(schema_lines(old[r], new[a], sampler_for(a)))
    p("")

    p(f"## New files ({len(added_files)})")
    for label, f in collapse(added_files):
        if f is None:
            p(f"+ {label}")
            continue
        e = new[f]
        if e["headerless"]:
            extra = f" - no header row ({e['ncols']} columns)"
        elif e["header"]:
            extra = f" - columns: {', '.join(e['header'])}"
        else:
            extra = ""
        p(f"+ {f}{extra}")
        if e["header"]:
            out.extend(sample_lines(sampler_for(f), e["header"]))
    p("")

    p(f"## Removed files ({len(removed_files)})")
    for label, _ in collapse(removed_files):
        p(f"- {label}")
    p("")

    p("## Schema changes in files present in both")
    changed = 0
    for f in common:
        lines = schema_lines(old[f], new[f], sampler_for(f))
        if lines:
            changed += 1
            p(f)
            out.extend(lines)
    if not changed:
        p("(none)")
    p("")

    if args.counts:
        p("## Row-count / size changes")
        for f in common:
            o, n = old[f], new[f]
            if o["rows"] is not None and o["rows"] != n["rows"]:
                p(f"{f}: rows {o['rows']} -> {n['rows']}")
            elif o["rows"] is None and o["size"] != n["size"]:
                p(f"{f}: bytes {o['size']} -> {n['size']}")
        p("")

    report = "\n".join(out)
    print(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(report)


if __name__ == "__main__":
    main()
