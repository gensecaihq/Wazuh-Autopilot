"""Regenerate tests/data/wazuh_rule_refs.json from an official Wazuh ruleset checkout.

The skills cite Wazuh rule IDs as `rule 5712` / `rules 5710, 5712`. This script collects every cited ID and
records its official level and description, so tests can check the skills without network access.

    git clone --depth 1 --branch v4.14.8 --filter=blob:none --sparse https://github.com/wazuh/wazuh.git /tmp/wz
    git -C /tmp/wz sparse-checkout set ruleset/rules
    python scripts/build_wazuh_rule_refs.py /tmp/wz/ruleset/rules
"""

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent
SKILLS = HERE / "app" / "skills"
OUT = HERE / "tests" / "data" / "wazuh_rule_refs.json"
CITE = re.compile(r"(?<!custom )\brules?\s+(\d{3,6}(?:\s*(?:,|and|or|/)\s*\d{3,6})*)", re.I)


def cited_ids() -> set[str]:
    ids: set[str] = set()
    for path in SKILLS.rglob("*.md"):
        for m in CITE.finditer(path.read_text()):
            ids.update(re.findall(r"\d{3,6}", m.group(1)))
    return {i for i in ids if int(i) < 100000}


def official(rules_dir: pathlib.Path) -> dict:
    out = {}
    for f in sorted(rules_dir.glob("*.xml")):
        text = re.sub(r"<!--.*?-->", "", f.read_text(errors="ignore"), flags=re.S)
        for m in re.finditer(r'<rule\s+id="(\d+)"\s+level="(\d+)"[^>]*>(.*?)</rule>', text, re.S):
            d = re.search(r"<description>(.*?)</description>", m.group(3), re.S)
            out[m.group(1)] = {"level": int(m.group(2)), "description": d.group(1).strip() if d else ""}
    return out


def main() -> None:
    rules = official(pathlib.Path(sys.argv[1]))
    ids = cited_ids()
    missing = sorted(ids - rules.keys(), key=int)
    if missing:
        sys.exit(f"skills cite rule IDs that don't exist in this ruleset: {missing}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"ruleset": "wazuh v4.14.8", "rules": {i: rules[i] for i in sorted(ids, key=int)}},
                              indent=1) + "\n")
    print(f"wrote {len(ids)} rule references to {OUT}")


if __name__ == "__main__":
    main()
