# SlopBoard

A local dashboard for your screen-time habits. It combines two sources:

- **Web slop** — the JSON files exported by the [Slopper](https://chromewebstore.google.com/detail/slopper-brainrotslop-stop/agdjpbclibfpgkmhjmhjmopogmmnmmac) Chrome extension ([source](https://github.com/Rick9117/slopper)) — YouTube Shorts, TikTok, Reels, etc.
- **Desktop apps** — a small tracker that records the app in your **active (focused) window**; apps left running in the background aren't counted

…and shows where your time actually goes, per day and per week. Everything runs
locally on your machine. There are no accounts, no servers, and no SQL database —
all data lives in plain **CSV files** on disk.

## Screens

- **Overview** — this week's web slop: totals, top platforms, time per day
- **Everything** — desktop apps and web slop together, including how much of your
  browser time was slop, plus a category breakdown
- **Weekly** — daily bars for any week you have data for
- **Settings** — choose the Slopper folder, start/stop the tracker, turn on
  auto-start, and switch between dark and light themes

It works with built-in **sample data** on first run, so you can see the whole
dashboard before installing Slopper or starting the tracker.

## Run it (the easy way)

Double-click **`run_slopboard.bat`**. It starts the desktop tracker and the
dashboard in the background — no console window — and opens the dashboard in its
own app window (no address bar or tabs). This is the way to hand it to someone
non-technical.

If nothing opens or you want to see what's happening, run **`debug_slopboard.bat`**
instead: it starts the dashboard visibly and prints any errors.

## Run it (manually, for development)

```bash
py -m streamlit run slopboard.py
```

This opens in a normal browser tab at `http://localhost:8501` and does **not**
start the tracker. Use `run_slopboard.bat` for the full app experience.

## Run the desktop tracker on its own

`run_slopboard.bat` starts it for you, but you can also run it directly:

```bash
py tracker/app_tracker.py            # real tracking (Windows)
py tracker/app_tracker.py --simulate # fake data, any OS, for testing
```

Only one tracker runs at a time — launching it again exits quietly, so your data
can't be double-counted.

## Requirements & install

Requires Python 3, plus Chrome or Edge for the app window (both are standard on
Windows). In the project folder:

```bash
py -m pip install -r requirements.txt
```

## Settings & features

- **Slopper folder** — where SlopBoard reads Slopper's exported files. If no
  Slopper data is found, the sidebar and Settings show a link to install the
  extension.
- **Desktop tracker** — start it by launching SlopBoard, or stop it from
  Settings. Every few seconds it records the app in your active (focused)
  window, so time counts only while an app is the one you're actually using —
  a game or app left running in the background isn't counted. It never counts
  SlopBoard's own window.
- **Start tracking automatically** — adds a shortcut to your Windows Startup
  folder so the tracker runs on boot. It's an ordinary shortcut you can see and
  delete yourself; nothing is hidden in the registry. Because the tracker is a
  singleton, the boot copy and a manual launch never produce two trackers.
- **Task Manager names** — the dashboard and tracker show up as `SlopBoard` and
  `SlopBoard tracker` (in the Details tab) instead of `pythonw`. This is done by
  launching through renamed copies of the Python interpreter, created next to
  your Python install. To disable it, set `FRIENDLY_TASK_MANAGER_NAMES = False`
  at the top of `launcher.pyw`.

## How it works

```
Slopper JSON files ┐
                   ├─► data_loader ─► combined CSV ─► dashboard (Streamlit)
App tracker CSV ───┘      (+ categories)
```

- `tracker/app_tracker.py` — samples the foreground window, writes app CSV
- `core/data_loader.py` — reads both sources, combines them, writes the combined CSV
- `core/categories.py` — maps app/platform names to categories (Work, Media, …)
- `core/common.py` — shared paths, colours, caching, and chart helpers
- `slopboard.py` + `pages/` — the four dashboard pages

## Project layout

```
SlopBoard/
├── slopboard.py          # main entry / router (sets up the sidebar menu)
├── launcher.pyw          # starts tracker + dashboard, opens the app window
├── run_slopboard.bat     # double-click this to launch (no console window)
├── debug_slopboard.bat   # visible launch that prints errors, for troubleshooting
├── requirements.txt
├── .streamlit/
│   └── config.toml       # theme (written by the Settings page)
├── tracker/
│   └── app_tracker.py    # desktop activity tracker
├── core/
│   ├── data_loader.py    # reads + combines the sources
│   ├── categories.py     # app → category rules
│   ├── common.py         # shared helpers
│   ├── startup.py        # the "start on boot" Startup-folder shortcut
│   └── procname.py       # friendly Task Manager names
├── pages/
│   ├── Overview.py
│   ├── Everything.py
│   ├── Weekly.py
│   └── Settings.py
└── data/                 # all data lives here — created at runtime, git-ignored
    ├── app_activity.csv  # written by the tracker
    ├── slopboard.csv     # the combined dataset
    ├── learned_categories.csv  # remembered app → category choices
    ├── *.log             # launcher / dashboard / tracker logs
    └── .browser-profile/ # private browser profile for the app window
```
