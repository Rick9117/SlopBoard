<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/slopboard-logo-dark.png">
  <img src="assets/slopboard-logo.png" alt="SlopBoard" width="420">
</picture>

**A local, private dashboard for your screen-time habits — version 0.3.**

SlopBoard shows where your time actually goes, day by day and week by week, by
combining two sources:

- **Web slop** — the JSON files exported by the [Slopper](https://chromewebstore.google.com/detail/slopper-brainrotslop-stop/agdjpbclibfpgkmhjmhjmopogmmnmmac) browser extension ([source](https://github.com/Rick9117/slopper)): YouTube Shorts, TikTok, Reels, and the like.
- **Desktop apps** — a small tracker that records the app in your **active (focused) window**. Apps left running in the background don't count.

Everything runs locally on your machine. No accounts, no servers, no database —
your data lives in plain CSV files on disk.

## Get SlopBoard

There are two ways in, depending on what you want:

- **Just want to use it?** Download the **installer** from the
  [latest release](https://github.com/Rick9117/SlopBoard/releases/latest). 
  Run it, choose where to install, and SlopBoard sets itself up like a normal Windows program —
  a Start-menu entry, an optional desktop shortcut, and its own uninstaller. Nothing
  else needs to be installed; the download already includes everything it needs.
- **Want the code?** You're looking at it. This repository is the source, for
  developers who'd like to build or change SlopBoard themselves — see
  [Running from source](#running-from-source) below.

## Screens

- **Overview** — this week's web slop: totals, top platforms, and time per day.
- **Everything** — desktop apps and web slop together, how much of your browsing
  was slop, plus a category breakdown.
- **Weekly** — daily bars for any week you have data for.
- **Settings** — choose the Slopper folder, start or stop the tracker, turn on
  auto-start, and switch between dark and light themes.

On first launch it shows built-in **sample data**, so you can explore the whole
dashboard before installing Slopper or starting the tracker.

## Running from source

SlopBoard is a [Streamlit](https://streamlit.io) dashboard plus a small desktop
tracker. Running from source needs Python 3 on Windows (the tracker and the app
window are Windows-only). Install the dependencies once:

```bash
py -m pip install -r requirements.txt
```

Then run the dashboard directly (opens in a browser tab; this does **not** start
the tracker):

```bash
py -m streamlit run slopboard.py
```

You can also run the tracker on its own:

```bash
py tracker/app_tracker.py            # real tracking (Windows)
py tracker/app_tracker.py --simulate # fake data, any OS, for a quick test
```

Only one tracker runs at a time — launching it again exits quietly, so your data
can't be double-counted.

For a one-click launch of the full app (tracker + dashboard + window), double-click
**`SlopBoard.bat`**. If you've built the self-contained runtime with `py build.py`,
it uses that (so it stays self-contained and doesn't touch your system Python);
otherwise it falls back to the Python you have installed. For everyday use, though,
open the installed SlopBoard from the Start menu rather than running from source.

## Building a release

`py build.py` bundles a private copy of Python and every dependency into
`dist/SlopBoard/` — a folder that runs on any Windows PC with no Python installed
— compiles the `SlopBoard.exe` launcher, and zips the result. `SlopBoard.iss` then
wraps that folder into `SlopBoard-Setup.exe` using
[Inno Setup](https://jrsoftware.org/isinfo.php). Both are large, generated
artifacts, so they're shared through GitHub **Releases** rather than committed to
the repository.

A couple of practical notes: the build must run on Windows, and it's easiest in a
Python 3.12/3.13 environment if a dependency doesn't yet have wheels for the very
newest Python — whoever installs SlopBoard gets whichever version you build with.
Unsigned executables show a one-time Windows SmartScreen prompt ("More info → Run
anyway"); that's expected for an unsigned hobby project.

## Settings & features

- **Slopper folder** — where SlopBoard reads Slopper's exported files. If none are
  found, the sidebar and Settings show a link to install the extension.
- **Desktop tracker** — records the app in your active (focused) window every few
  seconds, so time counts only while you're actually using something. A game or
  app left running in the background isn't counted, and SlopBoard never counts its
  own window.
- **Start tracking automatically** — adds a shortcut to your Windows Startup
  folder so the tracker runs on boot. It's an ordinary shortcut you can see and
  remove; nothing is hidden in the registry. The tracker is a singleton, so the
  boot copy and a manual launch never produce two trackers.
- **Task Manager names & icon** — the dashboard and tracker appear as `SlopBoard`
  and `SlopBoard tracker`, with the SlopBoard icon, instead of `python`. To turn
  this off, set `FRIENDLY_TASK_MANAGER_NAMES = False` at the top of `launcher.pyw`.

## How it works

```
Slopper JSON files ┐
                   ├─► data_loader ─► combined CSV ─► dashboard (Streamlit)
App tracker CSV ───┘      (+ categories)
```

- `tracker/app_tracker.py` — samples the foreground window and writes the app CSV.
- `core/data_loader.py` — reads both sources, combines them, writes the combined CSV.
- `core/categories.py` — maps app and platform names to categories (Work, Media, …).
- `core/common.py` — shared paths, colours, caching, and chart helpers.
- `slopboard.py` and `pages/` — the four dashboard pages.

## Project layout

```
SlopBoard/
├── slopboard.py          # main entry / router (sets up the sidebar menu)
├── slopboard_app.py      # compiled to SlopBoard.exe by build.py (PyInstaller)
├── launcher.pyw          # starts tracker + dashboard, opens the app window
├── build.py              # builds the self-contained release (py build.py)
├── SlopBoard.iss         # Inno Setup script → SlopBoard-Setup.exe
├── requirements.txt
├── assets/               # app icon, tab icon, and README logos
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
└── data/                 # created at runtime, git-ignored (CSVs, logs, profile)
```

`build.py` also creates `dist/` and the installer lands in `installer/`; both are
git-ignored, since they're large generated artifacts shared through Releases.
