"""
Maps applications and web platforms to a small set of categories.

How categorisation works:
  - Web platforms (from Slopper) are always "Slop".
  - Desktop apps are matched against a set of rules by substring, so both
    "Visual Studio Code" and "code.exe" land in "Programming".
  - The built-in rules (BUILTIN_RULES) seed the common apps.
  - When an unknown app appears, it is categorised as "Other" and remembered in
    data/learned_categories.csv, so it stays put and can be changed later.
"""

import csv
from pathlib import Path

# --- The categories SlopBoard uses ---
SLOP: str = "Slop"
BROWSING: str = "Browsing"
GAMING: str = "Media - Gaming"
VIDEOS: str = "Media - Videos"
MUSIC: str = "Media - Music"
SOCIAL: str = "Social"
PROGRAMMING: str = "Programming"
WORK: str = "Work"
OTHER: str = "Other"

# The order categories should appear in, with Slop first.
CATEGORY_ORDER: list[str] = [
    SLOP, BROWSING, GAMING, VIDEOS, MUSIC, SOCIAL, PROGRAMMING, WORK, OTHER,
]

# A distinct colour for each category, used for headers and underlines.
CATEGORY_COLORS: dict[str, str] = {
    SLOP: "#E1306C",         # pink
    BROWSING: "#5B8DEF",     # blue
    GAMING: "#8E7CC3",       # purple
    VIDEOS: "#E8A13A",       # amber
    MUSIC: "#1DB954",        # green
    SOCIAL: "#5865F2",       # indigo
    PROGRAMMING: "#22A699",  # teal
    WORK: "#D6604D",         # red-orange
    OTHER: "#6B7280",        # grey
}


def color_for_category(category: str) -> str:
    """Return the colour for a category, or grey if it's unknown."""
    return CATEGORY_COLORS.get(category, "#6B7280")

# Built-in rules: a substring found in the (lowercased) app name -> category.
# When several could match, the first one wins.
BUILTIN_RULES: dict[str, str] = {
    # Browsing
    "chrome": BROWSING,
    "firefox": BROWSING,
    "msedge": BROWSING,
    "edge": BROWSING,
    "opera": BROWSING,
    "brave": BROWSING,
    # Gaming
    "steam": GAMING,
    "sc2": GAMING,
    "starcraft": GAMING,
    "minecraft": GAMING,
    "league of legends": GAMING,
    "leagueclient": GAMING,
    "epicgames": GAMING,
    "battle.net": GAMING,
    "battlenet": GAMING,
    "wow": GAMING,                 # World of Warcraft
    "runelite": GAMING,            # Old School RuneScape
    "gonefishing": GAMING,
    "gonefishin": GAMING,
    "eft": GAMING,                 # Escape from Tarkov
    "escapefromtarkov": GAMING,
    "bsglauncher": GAMING,
    "schedule i": GAMING,
    "schedulei": GAMING,
    # Videos
    "netflix": VIDEOS,
    "prime video": VIDEOS,
    "amazon prime": VIDEOS,
    "vlc": VIDEOS,
    "disney": VIDEOS,
    # Music
    "spotify": MUSIC,
    "youtube music": MUSIC,
    "itunes": MUSIC,
    "musicbee": MUSIC,
    # Social
    "discord": SOCIAL,
    "whatsapp": SOCIAL,
    "telegram": SOCIAL,
    "slack": SOCIAL,
    "signal": SOCIAL,
    # Programming
    "code": PROGRAMMING,
    "visual studio": PROGRAMMING,
    "pycharm": PROGRAMMING,
    "intellij": PROGRAMMING,
    "terminal": PROGRAMMING,
    "powershell": PROGRAMMING,
    "cmd": PROGRAMMING,
    # Work
    "teams": WORK,
    "outlook": WORK,
    "word": WORK,
    "excel": WORK,
    "powerpoint": WORK,
    "onenote": WORK,
}


def _clean(name: str) -> str:
    """Lowercase a name and drop a trailing '.exe' for easier matching."""
    clean = name.lower().strip()
    if clean.endswith(".exe"):
        clean = clean[:-4]
    return clean


def load_learned(csv_path: str | Path) -> dict[str, str]:
    """Return the learned rules from data/learned_categories.csv.

    These are apps SlopBoard has seen before (columns: app,category). Returns an
    empty dict if the file doesn't exist yet.
    """
    rules: dict[str, str] = {}
    path = Path(csv_path)
    if not path.exists():
        return rules

    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            app = _clean((row.get("app") or ""))     # same cleaning everywhere
            category = (row.get("category") or "").strip()
            if app and category:
                rules[app] = category
    return rules


def save_learned(learned: dict[str, str], csv_path: str | Path) -> None:
    """Write the whole learned-rules dict back to the CSV, one row per app.

    Keys are already normalised by load_learned (lowercased, ".exe" stripped),
    so writing them straight back collapses any old duplicate rows into a single
    row per app. Rows are sorted to keep the file tidy and diff-friendly.
    """
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["app", "category"])
        writer.writeheader()
        for app, category in sorted(learned.items()):
            writer.writerow({"app": app, "category": category})


def remember(app: str, category: str, csv_path: str | Path) -> None:
    """Record one app's category, updating it in place (never duplicating a row).

    Loads the current rules (which normalises every key), sets this app's
    category - overwriting any previous entry - and writes everything back.
    """
    learned = load_learned(csv_path)
    learned[_clean(app)] = category      # same cleaning used everywhere
    save_learned(learned, csv_path)


def category_for(name: str, learned: dict[str, str], is_web: bool = False,
                 display: str = "") -> str:
    """Work out the category for one app or platform name.

    Web platforms are always Slop. For desktop apps we check, in order:
    a "[game]" tag on the display name (set by the tracker for Steam/Epic/GOG
    apps), then a *meaningful* learned rule, then the built-in rules, and finally
    "Other". A learned value of "Other" is treated as "not decided yet", so it
    never blocks a better match from the built-in rules or game detection.
    """
    if is_web:
        return SLOP

    # The tracker tags games it detects by their install folder.
    if "[game]" in display.lower():
        return GAMING

    clean = _clean(name)

    # 1. A learned rule wins - but only if it's a real choice, not "Other".
    learned_choice = learned.get(clean)
    if learned_choice and learned_choice != OTHER:
        return learned_choice

    # 2. Does it match one of the built-in substring rules?
    for match, category in BUILTIN_RULES.items():
        if match in clean:
            return category

    # 3. Unknown - it belongs in "Other".
    return OTHER
