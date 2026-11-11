#!/usr/bin/env python3
"""Refresh the `adblock` section of iosmorphe.json from the public uBlock Origin
and EasyList filter lists. Only plain data is imported (URL patterns, CSS selectors, JSON
key paths) -- never scripts. Usage:
  update_adblock.py extract <candidates.json>
  update_adblock.py apply <checked.json> <iosmorphe.json>
"""
import datetime, json, re, sys, urllib.request

BASE = "https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/filters/"
YEAR = datetime.date.today().year
SOURCES = [BASE + n for n in ["filters.txt", "quick-fixes.txt"] + [f"filters-{y}.txt" for y in (YEAR - 1, YEAR)]]
SOURCES.append("https://raw.githubusercontent.com/uBlockOrigin/uAssetsCDN/main/thirdparties/easylist.txt")
YT = {"youtube.com", "www.youtube.com", "m.youtube.com"}
PROCEDURAL = (":has-text(", ":upward(", ":matches-", ":xpath(", ":style(", ":remove(",
              ":watch-attr(", ":min-text-length(", ":others(", ":contains(", ":-abp-",
              ":spath(", ":if(", ":if-not(", ":remove-attr(", ":remove-class(", ":shadow(")
PATH = re.compile(r"^(\[\]\.)?[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$")
SCRIPTLET = re.compile(r"^json-prune(?:-fetch-response|-xhr-response)?,\s*([^,)]+)")


def fetch(name):
    try:
        with urllib.request.urlopen(name, timeout=60) as r:
            return r.read().decode("utf-8", "replace").splitlines()
    except Exception as e:  # a missing yearly file is normal
        print("skip", name, e, file=sys.stderr)
        return []


def for_youtube(domains):
    names = [d.strip() for d in domains.split(",")]
    return any(d in YT for d in names)


def extract():
    block, hide, prune = [], [], []
    for name in SOURCES:
        for line in fetch(name):
            line = line.strip()
            if not line or line.startswith("!"):
                continue
            if "##" in line and "#@#" not in line:
                domains, _, body = line.partition("##")
                if not domains or not for_youtube(domains):
                    continue
                if body.startswith("+js("):
                    m = SCRIPTLET.match(body[4:])
                    if m:
                        prune += [t for t in m.group(1).split() if PATH.match(t)]
                elif not body.startswith("^") and not any(p in body for p in PROCEDURAL):
                    hide.append(body)
            elif line.startswith("||") and "$" not in line and "##" not in line:
                rest = line[2:].rstrip("^")
                host = rest.split("/", 1)[0]
                if (host == "youtube.com" or host.endswith(".youtube.com")) and "/" in rest:
                    block.append(re.escape(rest).replace(r"\*", ".*").replace(r"\^", ""))
    uniq = lambda xs: list(dict.fromkeys(xs))
    return {"block": uniq(block)[:100], "hide": uniq(hide)[:200], "prune_keys": uniq(prune)[:60]}


def apply(checked_path, config_path):
    got = json.load(open(checked_path))
    # The source must still look like it did when this was written; otherwise keep
    # yesterday's list rather than publish an empty or broken one.
    if len(got["prune_keys"]) < 3 or len(got["hide"]) < 3:
        sys.exit("source looks wrong (too few rules); leaving the config untouched")
    cfg = json.load(open(config_path))
    ab = cfg.setdefault("adblock", {})
    uniq = lambda xs: list(dict.fromkeys(x for x in xs if x))
    new_block = uniq(ab.get("manual_block", []) + got["block"])
    new_hide = ", ".join(uniq(ab.get("manual_hide", []) + got["hide"]))
    new_prune = uniq(ab.get("manual_prune_keys", []) + got["prune_keys"])
    if (ab.get("block"), ab.get("hide"), ab.get("prune_keys")) == (new_block, new_hide, new_prune):
        print("no change")
        return
    ab["block"], ab["hide"], ab["prune_keys"] = new_block, new_hide, new_prune
    ab["_auto_updated"] = datetime.date.today().isoformat()
    ab["_auto_source"] = "uBlockOrigin/uAssets + EasyList"
    json.dump(cfg, open(config_path, "w"), indent=2, ensure_ascii=False)
    open(config_path, "a").write("\n")
    print("updated:", len(new_block), "block,", len(got["hide"]), "hide,", len(new_prune), "prune keys")


if __name__ == "__main__":
    if sys.argv[1] == "extract":
        json.dump(extract(), open(sys.argv[2], "w"), indent=1)
    else:
        apply(sys.argv[2], sys.argv[3])
