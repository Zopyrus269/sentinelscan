import json
import sys

data = json.load(sys.stdin)
command = data.get("tool_input", {}).get("command", "")

if "git commit" in command:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                "A git commit was just made. If this completes a feature "
                "(implemented, tested, reviewed, and now committed), update "
                "the knowledge vault now per the CLAUDE.md Knowledge Vault "
                "Protocol (append knowledge/daily-logs/YYYY-MM-DD.md, "
                "overwrite knowledge/NEXT_TASK.md). If this was a minor "
                "fixup/wip commit, it's fine to skip."
            ),
        }
    }))
