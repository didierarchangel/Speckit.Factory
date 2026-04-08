import re

REPLACEMENTS = {
    "🛡️": "[SAFE]",
    "🔄": "[AI]",
    "✅": "[OK]",
    "⚠️": "[WARN]",
    "❌": "[ERROR]",
    "ℹ️": "[INFO]",
    "🎨": "[DESIGN]",
    "✨": "[OK]",
    "📜": "[DOC]",
    "🧩": "[COMPONENT]",
    "👁️": "[VISION]",
    "🌊": "[UX]",
    "💡": "[INFO]",
    "⏳": "[WAIT]",
    "🛑": "[STOP]",
    "📝": "[DOC]",
    "🔍": "[SCAN]",
    "💾": "[SAVE]",
    "📸": "[PHOTO]",
    "📊": "[STAT]",
    "🏗️": "[SETUP]",
    "🔧": "[FIX]",
    "📁": "[DIR]",
    "💻": "[CODE]",
    "🧱": "[BLOCK]",
    "🧠": "[CORE]",
    "📍": "[TARGET]",
    "🔑": "[KEY]",
    "🎯": "[GOAL]",
    "➕": "[ADD]",
    "🧹": "[CLEAN]",
    "🚀": "[RUN]",
    "🧪": "[TEST]",
    "⚒️": "[FIX]",
    "🔨": "[FIX]",
    "🐛": "[BUG]",
    "⏮️": "[BACK]",
    "⏭️": "[SKIP]",
    "→": "->",
    "•": "-",
    "─": "-",
    "═": "=",
    "━": "=",
    "│": "|",
    "└": "+",
    "↳": "->",
    "É": "E",
    "é": "e",
    "è": "e",
    "ê": "e",
    "à": "a",
    "â": "a",
    "î": "i",
    "ô": "o",
    "û": "u",
    "ù": "u",
    "ç": "c",
    "ï": "i",
    "ë": "e"
}

def sanitize_file(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    for char, replacement in REPLACEMENTS.items():
        content = content.replace(char, replacement)

    # Final sweep for any remaining non-ASCII - replace with '?' if not in map
    sanitized = ""
    for c in content:
        if ord(c) > 127:
            # We already replaced those in REPLACEMENTS, but some might remain or be combined characters
            sanitized += "?"
        else:
            sanitized += c

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(sanitized)

if __name__ == "__main__":
    import sys
    sanitize_file(sys.argv[1], sys.argv[2])
