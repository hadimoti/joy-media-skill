---
name: joy-media-windows-mcp
description: Drive the JOY Media (JOY Studio) Electron desktop app on Windows with the Windows-MCP tools. Launch an isolated test copy, make a project, import media, click Export MP4, save the Windows Save dialog, then check the result (ffprobe, full decode, colour patches, timings from the app's own database). Also covers the repo's live QA driver, the app lock, Windows Sandbox install and upgrade receipts, QC and provider checks, and the draft release upload. Use when asked to test, run, time or verify an export in the JOY Media desktop app, run its live QA rows, check a release candidate, or compare builds.
---

# Driving JOY Media with Windows-MCP

This skill is a method, learned on JOY Media 1.1.0 builds (Electron 44.3.0, Windows 11). It tells an agent how to run the desktop app **without touching the user's real install or data**, click through the editor with the Windows-MCP tools, and judge an export by facts instead of looks.

Tools used: `Snapshot`, `Screenshot`, `Click`, `Type`, `App`, `Wait` (Windows-MCP), plus PowerShell for launching, file checks and `ffmpeg`/`ffprobe`.

## 0. Ground rules (do not skip)

- **Ask the owner first, every run.** Launching the app, importing and exporting need the owner at the PC and a clear "go" for that run. One run at a time. Never launch against the user's real profile.
- **Never touch the installed app** (its folder, its installer scripts, its uninstaller). Run a separate unpacked copy instead (section 1).
- **Isolate data**: always pass a **new** `--user-data-dir`. To reuse an existing project, close the app, then `robocopy /E` the old profile to a new folder (no `/MIR`, no purge) and launch on the copy.
- **Keep the real asset library untouched.** A new profile points at the user's default asset library. Before any import, switch the profile to a scratch library (section 3b), and count the real library's files before and after the run.
- **The `joy://` registration key** (`HKCU\Software\Classes\joy`) must not change. Export it to a new file with `reg export` before launch, after launch and after close, and compare SHA-256. If it differs, stop and tell the owner; restore only on their word.
- **Delete nothing** while testing (copies, profiles, exports are evidence). Chromium may clean its own temporary files inside the *new* test profile; that is fine.
- **Stop on crash evidence** (GPU process exits, Application Error events, driver resets): keep everything, do not rerun over it, tell the owner.
- **Manual runs are partial evidence.** A run driven by hand gives visual results. Label it that way, and never present it as a scripted pass or as a gate receipt.
- Never type secrets into the app or put tokens in notes.

## 1. Get an app copy that is safe to run

Build or unpack the commit you want into a short path (under 260 characters), for example `C:\jg\app-<sha>`:

1. `git archive <sha>` to a tar, extract to `C:\jg\<name>`.
2. `pnpm install --offline --frozen-lockfile` (needs a warm pnpm store).
3. Copy the Electron `dist` folder and `path.txt` from an existing copy's `node_modules\.pnpm\electron@<ver>\node_modules\electron` (offline installs do not download Electron). Check the `electron.exe` SHA-256. If no copy has it, unzip the cached runtime instead: `%LOCALAPPDATA%\electron\Cache\<hash>\electron-v<ver>-win32-x64.zip` into a scratch folder (no download). Do not call the `electron` package's path helper in a fresh worktree: it starts a download when `dist` is missing. To make tools that resolve `electron` (Playwright specs, scripts) use the unzipped runtime, set `ELECTRON_OVERRIDE_DIST_PATH` to that folder.
4. `pnpm build`, then `pnpm --filter @joy-media/desktop package:unpacked`.
5. `robocopy apps\desktop\dist\joy-media-unpacked C:\jg\app-<sha> /E`.
6. Check that `resources\app\node_modules\playwright-core` exists. Without it the Worker dies and every export waits at "Waiting for Worker export verification". Copy the folder from a working copy if it is missing.

An unpacked copy runs with `isPackaged = false`, so it does **not** register the `joy://` protocol. Check the key anyway.

## 2. Launch it (PowerShell)

```powershell
$env:NODE_ENV = 'production'
$app = 'C:\jg\app-<sha>'
Start-Process -FilePath '<path to>\electron.exe' `
  -ArgumentList @($app, '--user-data-dir=<scratch root>\<new-profile>', '--enable-logging=stderr') `
  -WorkingDirectory $app `
  -RedirectStandardOutput '<scratch root>\run\stdout.log' -RedirectStandardError '<scratch root>\run\stderr.log' -PassThru
```

`--enable-logging=stderr` puts renderer `console.*` lines into the stderr file (useful for temporary diagnostics). Check that no process command line contains `--joy-media-gpu-encode-fallback` (that would be the fallback relaunch, not a default launch). The window title is `JOY Studio`. On a new profile the app opens the Projects page; on a copied profile it restores the last project.

## 3. Drive the window with Windows-MCP

**Scale**: screenshots are about 2.56 times smaller than the real screen. Always click **real** coordinates from `Snapshot`, never screenshot pixels. Take a small `Screenshot` (`scale` 0.4) after each page change.

**Order**: issue window actions **one at a time**. A batch sent right after an export once made clicks and typing land in the wrong project. `App switch "JOY Studio"` sometimes fails with "Invalid window handle"; if the window is already in front, continue.

Coordinates below are from a 4920x2160 screen with the JOY window at its default size and position. They are a starting map, not a promise: take a `Snapshot` and use the element list when anything looks different.

| Action | Where (real coordinates) |
|---|---|
| File menu | (910, 288) |
| File > Projects Library | (1077, 358) |
| New project button | (3023, 311), then click the name field (1165, 727), `Type` the name with `press_enter`. If Enter does not submit (seen on a later build), click the tick next to the box, about (1400, 729) |
| Left panel: import media, then confirm | upload icon in the media panel (about 753, 505), then "Choose file" (about 907, 715) opens the open dialog; type the full path and Enter; the file is queued in the "Import media" box, so click its **tick** (about 1230, 715) to finish; the card then shows a "+" (add to timeline) button |
| First project card | (1680, 873) |
| Timeline "Import media" (empty timeline) | (2199, 1312) |
| Open-file dialog: name box / Open | (1587, 1208) / (2268, 1264) |
| Export MP4 | (2672, 288) |
| Select the clip, check Scale | click the clip bar (1762, 1349); the inspector shows Scale X/Y |
| Close the app window | (3143, 288) |
| Save dialog: name box / Save | about (1717, 1058) / (2283, 1266) |

Recipe for one case: Projects Library > New project > name > Import media > type the full file path > Open (the clip lands on the timeline) > check the preview > Export MP4 > wait > save the dialog > verify.

**The Save dialog.** Export ends in a normal Windows Save dialog (default folder Downloads, a suggested name without extension). The file reaches the Desktop only after someone saves it, so a delay between "worker finished" and "file on the Desktop" is just that dialog waiting. Take a screenshot when the worker should be done; either the owner saves, or (with their OK) type the full target path `...\Desktop\<suggested-name>.mp4` into the name box and click Save. Job timings in the app database are not affected by the wait.

**The folder rule.** A save or open dialog refuses a path whose folder does not exist ("Path does not exist"). Create the folder first (PowerShell), then type the full path and click **Save**. Export MP4 starts encoding at once; the Save dialog appears after the encode finishes. Cancelling leaves no file in Downloads; the encoded file stays in the profile's `worker\derivatives` folder. A temporary `.tmp` file can appear in Downloads while a dialog is open, and it is removed when the dialog closes.

### 3b. Asset library and fresh profiles

A new profile uses the user's default asset library (`%USERPROFILE%\joy-media-assets`). Before any import:

1. Open **Edit > Asset Library Folder...**. The dialog "Asset Library Storage" shows the current folder.
2. Type the scratch folder into the Local Assets Folder box, then click **Apply Path**. The folder must exist first.
3. Click the refresh icon. A new empty folder reports "Incomplete: no catalog.json". Write a minimal catalog yourself: `{"version": 1, "generatedAt": "<ISO time>", "counts": {"total": 0, "audio": 0, "image": 0, "video": 0}, "assets": []}`. Never copy another library's catalog.
4. Confirm "Connected & Ready" with the expected count, then click **Done**.

The setting is per profile, so a fresh profile needs the same switch, including before an editable-project import. It is stored in the profile, so a relaunch on the same profile keeps the scratch library (check the media panel count on every launch). After you switch, the media panel can keep the old library's counts until you click refresh or reopen the project; do not import until the panel shows the scratch counts. Count the real library's files before and after the run (hash a sorted `path|length` listing and compare).

Coordinates from one 4920x2160 run (check with a screenshot): Edit (972, 288); Asset Library Folder... (1076, 620); path box (1792, 958); Apply Path (1453, 1030); refresh (1866, 974); Done (1430, 1399). The Edit menu sometimes needs a second click, because the first click only highlights it.

### Editable project route (fresh-profile check)

File > Export Editable Project... writes `<name>.joyproject.json` through a Save dialog (type the full path into a folder that exists). Then, in a new empty profile with the library switched (3b), use File > Import Editable Project... and type the full path. The clip appears on the timeline and the monitor shows its frame. This shows that a project saved in one process opens and renders in a fresh profile. It is a visual check, not a scripted persistence test.

### Missing media relink check

Shows the Missing media section and the relink rules on a build that has them. Use the scratch profile and library from 3b.

1. In a project with one imported clip on the timeline, File > Export Editable Project... and save to a scratch folder (the package holds the media as base64, `media[].status` = `embedded`).
2. With a script, copy the package and set every `media` entry to `{ "asset": <same asset>, "status": "missing", "missingReason": "unavailable" }`.
3. Delete the clip from the scratch library (its card's trash icon, confirm). It must be gone from the library or the app will still find it.
4. File > Import Editable Project... and type the path of the stripped copy. The Assets panel shows **Missing media (1)** with the file name, kind and size, and a **Relink** button.
5. Relink with a **different** file: expect a refusal such as "The chosen file has a different size from the original. Choose the original file. The original is unchanged.", the card stays, and a "Use different file" choice appears.
6. Relink with the **original** file: expect **Missing media (0)** and "Relinked <name>.", and the preview shows the clip.
7. Close the app, relaunch on the same profile: the project opens with no Missing media section and the clip still on the timeline.

8. **Cancel check:** click Relink, then Cancel in the file picker. Expect no change, no error and an empty scratch library.
9. **Override and Undo:** after the refusal in step 5, click **Use different file** (a second picker opens), choose the wrong file. Expect the section to read "Missing media (0)" with "<name> is now a separate asset; 1 clip(s) use it. The original is unchanged. Undo reverses this.", and the preview shows the new clip's picture. Click the **undo arrow** in the title bar (about 2196, 288 on a 4920x2160 screen). Expect "Missing media (1)" again with the original card and its Relink button, and the preview empty. The redo arrow becomes active.

On the tested build the relinked or override file was not added as a card in the media list, and the scratch library folder still held only its catalog.json afterwards (the media is held with the project). A relinked original is not re-added as a card in the media list on the tested build.

## 4. Before, during and after a run

Before: `reg export` the `joy://` key and hash it; list the user's real profile folder and any evidence folders (`scripts/list-tree.ps1`) so you can prove nothing changed.

During (long exports): start `scripts/sampler.ps1 -Pattern '*<profile>*' -Out <csv> -Stop <stopfile>` in the background. It records, once a second, working set, private bytes, CPU seconds, NVENC sessions and GPU use per Electron process. Create the stop file to end it.

After: close the app (the Close window button), confirm no `electron` process is left, export the key again, list the folders again and diff, check there are no `*.upload` leftovers in the profile, and look for Application Error/WER and Display/nvlddmkm events (ignore unrelated noise such as Docker).

## 5. Judge the export by facts

- `ffprobe -show_streams`: codec, size, frames, duration, **colour tags** (`color_space`, `color_primaries`, `color_transfer`, `color_range`).
- Full decode must be clean: `ffmpeg -v error -i out.mp4 -f null -` and exit code 0.
- Hash the file (`Get-FileHash`); identical layouts from different builds should give identical hashes when the code path is the same.
- **Phase times from the app's own database** (a *copy* of `joy-media.sqlite3` plus its `-wal`/`-shm`, opened read-only): `scripts/export-times.py <copy>` prints, per export, the browser phase (click stamp to staged original), staged bytes and worker time. The click stamp is the 13-digit number in the file name.
- **Colour accuracy**: build fixtures with `scripts/fxgen.py <folder>` (flat colour patches with known sRGB values plus a binary frame counter; BT.709, BT.601, untagged SD, full range, rotated, VFR, 10-bit, HEVC, VP9, AV1, interlaced, a transition pair and audio-rate pair), check them with `scripts/fxcheck.py <folder>`, then score an export with `JOY_FX_DIR=<folder> python -I scripts/fxplace.py <export.mp4> <fixture-file-name> [frame]`. It finds where the clip landed (clips smaller than the canvas sit 1:1 at the top-left, not scaled) and prints the worst/mean deviation under four matrix/range readings; the right reading should be within about 3 levels.
- Audio: pitch via `astats` zero-crossing rate, level via RMS; mono sources become stereo (about 3 dB lower per channel).
- Quick audio level: `ffmpeg -hide_banner -i out.mp4 -map 0:a -af volumedetect -f null -` prints the mean and max volume. Compare with the source.
- First frame: `ffmpeg -hide_banner -loglevel error -y -i out.mp4 -frames:v 1 frame0.png`, then open the PNG and compare it with the source's first frame.
- Timing: the same timeline should give the same frame count and duration as the source.

## 6. Known behaviour worth remembering (JOY Media 1.1.0 builds)

- **Run every colour test in a fresh app session.** On the tested machine (RTX 5070 Ti, Electron 44.3.0) the **first** export after launch is encoded BT.709 (tag bt709); **later** exports in the same session are encoded BT.601 (tag smpte170m), come out larger and slower on a long layout, and have different bytes. A diagnostic build showed the capture canvas frame is RGBA (GPU-backed) the first time and BGRA (CPU-backed) afterwards; the app sets no colour space itself. Converting to NV12 BT.709 inside the app made every export identical.
- Untagged SD video is read as BT.709 (colours shift up to about 20 levels).
- A source without an audio track exports a silent stereo AAC track.
- Compare builds only on equal footing: same layout, same position in the session (first export vs first export), window in front and focused (an unfocused window can be around 30 percent slower), a copy of the same profile.
- Other agents or chat windows on the same desktop can steal focus: screenshot before you click.
- The first click on a window may only focus it.
- The Export status line reads "Encoding preview-equivalent H.264/AAC". The worker also has a GPU preview host (`apps/worker/src/gpu-preview-host.ts` in the JOY Media repo). The logs do not show whether a given export used it. If the owner has a no-GPU rule, ask before exporting.
- On the 1.1.0 build from ded976c8, an unpacked copy did not change the `joy://` key at launch, after close, or on relaunch. Keep checking it on every launch.
- `Snapshot` lists only desktop icons and the taskbar for the JOY window; the editor's own controls are not exposed. Use screenshots and the coordinate table.
- A dialog can fade out for a few seconds with its path still in the box. Wait 3 to 5 seconds and take a new screenshot before the next click.
- **Export leaves a staged copy in the asset library** on the tested line: a card named `<export name>.mp4.stage` (about the size of the encode) stays next to your imported clips after an export. It is listed in the media panel and counted in the catalog. Expect it in the scratch library, and do not treat it as an import you made.
- **`reg export` from Git Bash**: the `/y` flag is rewritten as a path and the command fails (or writes a wrong file). Run it from PowerShell. Read the exported file's `shell\open\command` line, not just its hash, so you can say which exe the key names.
- **The `joy://` key can be changed by another agent's build on the same PC** (another session launching its own unpacked or test copy). If the first export of a run already differs from the expected value, say so, note which path it names, and do not restore it yourself. Only the owner decides a restore. A differing value at the start is not evidence that your run changed it: export again at the end and compare both to the baseline.
- A sample project that ships with a fresh profile has placeholder clips whose media does not exist. Exporting it fails with "Clip ... cannot resolve visual asset". Test exports in a new project with your own clip.
- A 4-second 1280x720 video-only clip exported at the 1080x1920 preset in about 25 seconds, with the Save dialog appearing after the encode ("Encoding preview-equivalent H.264/AAC ... n/120 frames" in the status line). The output was H.264 plus a silent AAC track, 120 frames, clean full decode.

## 6b. Running the repo's Playwright desktop specs

The JOY Media repo has packaged-app specs under `tests/desktop`. Facts from running them against an unpacked copy:

- They launch the app with `--joy-media-test-mode` and wait for a download in a test folder. A build without that hook opens the real Windows Save dialog and the spec hangs until it times out. Check that the build has the hook before you start. A native dialog on screen during a spec run means this.
- Specs open the user's default asset library through the home folder. Run them with a scratch `USERPROFILE`/`HOME`, and scratch `TEMP`/`TMP`, so nothing reaches the real library. Set `PLAYWRIGHT_BASE_URL` to an unused address when the specs are Electron-only so no dev web server starts. Count the real library before and after.
- Set `ELECTRON_OVERRIDE_DIST_PATH` (section 1) so the specs use the cached runtime.
- To stop a hung run, stop the runner, then end **only** the processes whose command line names your scratch paths (the Playwright node processes and their Electron tree). Do not end other Electron or JOY processes.
- A spec that passes proves only what it asserts. Report passes, failures and the tests that never ran separately.

## 6c. Windows Sandbox and scripted attended runs (v1.1.0 release work)

- **Windows Sandbox runs one instance at a time.** Close the window of the first run before the next one starts. With Windows-MCP: switch to the "Windows Sandbox" window, then click its close button and OK. The scripts in the repo (`tooling/release/sandbox/run-sandbox.ps1 -Kind lifecycle|upgrade`) start the Sandbox with networking off, wait for the result and copy the receipt out. Wait up to 60 seconds after an uninstall: the uninstaller removes its folder in the background.
- **Sandbox scripts run on Windows PowerShell 5**, so receipts have a UTF-8 byte-order mark. Strip it before `JSON.parse`, by char code (`text.charCodeAt(0) === 0xfeff`), not with a raw BOM character in source (lint refuses it).
- **PATH bug in the v1.0.x install script**: it glued the install folder onto the last PATH entry. The v1.1.0 setup repairs it. When you test an upgrade over v1.0.2, check `PATH` for a glued entry before and after.
- **Icon cache**: Windows can show the old icon after an install over an older build. This is the shell cache, not the exe. Judge the icon from the exe, not from the shortcut.
- **Scripted attended receipts**: `tooling/release/attended/run-scenario.mjs --scenario desktop.app.restart-save-export|project.persistence.fresh-process`. Unzip the release zip into a scratch folder (it already carries playwright-core), pass `--candidate <40-hex>`, `--expected-exe-sha256`, `--owner-library-files <count>`, a scratch library, and a new run folder for every dry run and every launch. The restart scenario's `--project` is the project id from the profile database (`project_documents.project_id`, a `project-...` value), not the id inside the document. Dry run first; then `--launch`. Check the `joy://` key before and after.
- **One lock file for app launches** when two agents share the PC: the lock file at `JOY_QA_LOCK` (section 7), or a lock file you agree on with the other agent (name, time, reason); delete your own when done.
- A startup error box "Failed to get 'documents' path" appears when a run uses a scratch `USERPROFILE` that has no Documents folder (a development build of folder projects). Set the build's projects-folder override, or give the scratch profile a Documents folder.

## 7. Live test driver (`tooling/qa/live`, JOY Media repo)

The live driver runs numbered test rows against an unpacked copy of the app. It drives the app through Playwright over the Chrome DevTools port. Run it from the **JOY Media repo root**, not from this skill's folder.

```
node tooling/qa/live/run.mjs --tests D-000,D-001 --app <unpacked dir> [--media <fixture file>] [--out <new empty dir>] [--needs-sign-in] [--simulate-wrong-joy-hash]
```

Arguments:

- `--tests`: comma-separated row IDs. `D-M*` expands to every known ID with that prefix. An unknown ID is refused, and the error lists the known IDs. Take IDs from the driver files; do not guess them.
- `--app`: absolute path to the unpacked app folder. It must hold `joy-media.exe` and `resources\app\node_modules\playwright-core`. The installed app is refused.
- `--media`: a fixture file inside the fixtures folder (`<root>\fixtures`). Needed by `D-002`, the `D-A10` export rows, and the monitor cases that need a clip on the timeline. Without it those rows report `blocked`.
- `--out`: the evidence folder. Default `<root>\evidence\<task>\<run id>`. It must be new or empty.
- `--needs-sign-in`: see the sign-in rule below.
- `--simulate-wrong-joy-hash`: a test of the registry guard. The run must refuse before the app starts.

Exit codes: `0` all rows passed (or `not-reachable`), `1` a row failed or was `blocked`, `2` refused before the app ran, or the after-run safety check failed. Each row writes `<out>\<id>\result.json` and a screenshot. The console prints one `<id>: <status> <message>` line per row.

Roots and environment. Set these; do not edit the code:

- `JOY_QA_ROOT`: the run root. It holds `fixtures`, `evidence`, `codex` (profiles and libraries) and `dnd`. Use a scratch folder outside the worktree and outside the owner's folders.
- `JOY_QA_LOCK`: the path of the app lock file.
- `JOY_QA_EXPECTED_JOY_HASH`: the SHA-256 of the exported `joy://` key, or the word `absent` on a machine with no such key.
- `JOY_QA_APP_LOG`: optional app log path. It is refused inside a protected owner folder.

Guards. Each one stops a run before the app starts unless noted:

1. **`joy://` key guard.** The driver exports `HKCU\Software\Classes\joy` to a temporary `.reg` file and hashes it. It refuses when the hash is not the approved value. It checks again after the run and fails the run if the key changed. If the key differs, stop and tell the owner. Do not restore it yourself; restore only on the owner's word.
2. **App lock.** One lock file at `JOY_QA_LOCK`, created exclusively at launch. It holds a name, a time, a reason and the run ID. A lock younger than 30 minutes refuses the run. An older lock is stale and is removed. The lock is released at the end of the run, unless the app is still running; then it stays, and the next run is refused. Delete only your own lock.
3. **No other app.** A JOY Media or Electron process already running refuses the run.
4. **Owner library count.** The driver counts the files in the owner's default asset library before and after the run. A change fails the run.
5. **Folders.** Each run gets a new profile and a new scratch library (`codex\profiles\<run id>`, `codex\libraries\<run id>`). The run paths must not overlap each other, the worktree or a protected owner folder, and must not contain a link or junction.

Scratch launch and sign-in launch:

- Default: every folder is scratch (user data, `USERPROFILE`, `HOME`, `APPDATA`, `TEMP`, `LOCALAPPDATA`, `JOY_MEDIA_HOME`). The live rows never see the owner's real folders.
- `--needs-sign-in`: the first launch keeps the real `LOCALAPPDATA`, so a provider's sign-in page opens in the normal browser profile. The driver records that page, closes the app, and runs the rows on a scratch launch of the same profile. Use it only with the owner at the PC, a scratch profile and a scratch library. Never use it for the rows alone.

What each driver covers. Take the row IDs from the `id` fields in these files; the run refuses an ID it does not know and prints the known list.

| Area | Driver files (`tooling/qa/live/`) | Rows |
|---|---|---|
| Smoke and setup | `run.mjs` | `D-000` window opens, `D-001` new project, `D-002` import `--media` |
| Monitor | `monitor-suite-steps.mjs`, `monitor-hand-steps.mjs`, `monitor-keyboard-steps.mjs`, `monitor-select-steps.mjs`, `monitor-transform-steps.mjs`, `monitor-transform-b-steps.mjs` | `D-M01` to `D-M10` (`--tests "D-M*"`) and sub-steps |
| Colour | `color-matrix-rows.mjs`, `color-panel-steps.mjs`, `color-wheels-steps.mjs`, `color-curves-steps.mjs`, `color-hsl-steps.mjs`, `color-persistence-steps.mjs` | `D-K01` to `D-K04` and colour persistence |
| Effects, looks, clip audio | `effects-looks-steps.mjs` | `D-057`, `D-058`, `D-070` |
| Left panels | `left-panels-steps.mjs` | `D-065` to `D-069` (Text, Captions, Audio, Templates) |
| Menus and palette | `actions.mjs` | `D-071` to `D-080` |
| Projects, import, libraries | `desktop-projects-import-steps.mjs` (row matrix, `--tests "D-A05*"`) | `D-A05-01` to `D-A05-60`; `D-A05-60` exports the sample project |
| Timeline, undo, redo | `desktop-timeline-steps.mjs` (row matrix, `--tests "D-A06*"`) | `D-A06-01` to `D-A06-50` |
| Persistence and missing media | `desktop-persistence-steps.mjs` (row matrix, `--tests "D-A09*"`) | `D-A09-01` to `D-A09-05` |
| Export and formats | `export-matrix-steps.mjs` with `export-probe.mjs` and `export-preset-spec.mjs`; `export-missing-steps.mjs`; `export-recorder-fallback-steps.mjs` | `D-A10-*` (presets, ffprobe and frame checks, needs `--media`); missing-media export rows; recorder fallback rows |
| Drag and drop | `timeline-dnd-steps.mjs`; `timeline-dnd-h04-scripted-rows.mjs`; `timeline-dnd-h04-rows.mjs` | scripted drop rows `D-H01` to `D-H10`; the rows that need a real Explorer drag need a person at the mouse |
| Provider settings | `provider-settings-run.mjs` (its own runner), `provider-settings-steps.mjs`, `provider-settings-fake-page.mjs`, `provider-settings-seed.mjs` | `D-087` to `D-094` and sub-cases; uses a local stub model; `--dry-run` uses a fake page |
| Library thumbnails | `desktop-library-thumb-steps.mjs` | `D-A11-01`: a library-only image and video show decoded thumbnails on their cards |

Several driver headers still say **NOT RUN: written without launching the app**. Their selectors were read from the source. The first live pass is the confirmation, and it often fails on a selector. Read the screenshot and `result.json` before you change a test. Cases that need a feature the build does not have throw `BLOCKED <id>`; that counts as a failure in the exit code.

Steps for one run:

1. Get an app copy that is safe to run (section 1). Check `playwright-core` and the `joy://` key.
2. Set `JOY_QA_ROOT`, `JOY_QA_LOCK` and `JOY_QA_EXPECTED_JOY_HASH` for this machine.
3. Check the lock file and the running processes. Check with the owner (section 8).
4. Run the rows with a new `--out`. Read each `result.json`.
5. When you change the guard setup, run once with `--simulate-wrong-joy-hash`. The run must refuse.
6. After the run: the lock is gone, no JOY process is left, the key hash matches, and the owner library count is unchanged.

Pitfalls:

- `--media` must be inside the fixtures folder. Any other path is refused.
- A `blocked` row is not a pass.
- A pass proves only what that row asserts. Report passed, failed, blocked and never-run rows separately.
- Never reuse an `--out` folder, a profile or a library. Each run needs new ones.
- Do not use `--needs-sign-in` for a routine run. It gives the first launch the real `LOCALAPPDATA`.

## 8. Lanes and the lock rule

Generic rules for any agent or helper on the same PC:

- **One live run at a time.** The lock file enforces it. Two agents never run the app at once.
- **The orchestrator runs live harnesses.** Helper agents (code, review, research, log reading) never launch the app, never run the live driver and never take the lock.
- **Not while the owner is busy.** No live run while the owner is at the PC playing a game or doing heavy work (encoding, big builds, screen recording, calls). Wait, or ask.
- **Attended runs need a go that names the run.** Anything that needs the owner at the PC, a sign-in page or a native dialog needs a clear yes for that run. A yes for one run does not cover the next.
- **Evidence stays where it was written.** Each run has its own folder. Never write over another run's output.
- **Note the lock holder.** When you take the lock, the file says who and why. Delete only your own lock when your run ends.
- Stop on crash evidence and keep everything (section 0).

## 9. Windows Sandbox lifecycle receipts and upgrades

The release gate reads receipts from clean Windows Sandbox runs with networking off. The scripts are in `tooling/release/sandbox/`, and the full table is in its `README.md`.

| Run | Script | Receipt |
|---|---|---|
| Clean install, open, close, uninstall (also offline smoke) | `lifecycle.ps1` | `sandbox-lifecycle.json`, `offline-smoke.json` |
| Upgrade from v1.0.2 (zip) | `upgrade.ps1` | `sandbox-upgrade.json` |
| Upgrade from the previous setup exe | `upgrade.ps1` | `sandbox-upgrade-from-1.1.0.json` (for 1.1.0) |

Steps:

1. **Dry run first.** `run-sandbox.ps1 -Kind lifecycle -SetupExe <any file> -OutDir <new folder> -Receipt <path> -DryRun`. It prints the plan, validates fake receipts and does not start Windows Sandbox. It supports the lifecycle run only.
2. **One Sandbox at a time.** The script refuses to start while a Sandbox runs. Close the old window first.
3. **Live run.** Pass the candidate setup exe and a new output folder. The script waits for the run, copies the receipt out and prints the path. Then close the Sandbox window yourself; the script does not close it, and its contents are discarded.
4. **Upgrades.** Pass the candidate version with `-ToVersion x.y.z`. Never assume it. Use `-V102Zip` for the v1.0.2 zip, or `-FromSetupExe`, `-FromVersion` and `-FromSha256` for the previous setup exe. The exe's own hash must match `-FromSha256`, or the script refuses.
5. **Check the receipt.** Each upgrade receipt must end on the candidate version. The clean run also needs the `joy` and `joy-media` version checks and a render manifest from the bundled offline-smoke project.

What the gate accepts:

- the setup the Sandbox installed has the same SHA-256 as the candidate's `joy-media-setup.exe` in `SHA256SUMS.txt`;
- every required step passed and no step is an error;
- after uninstall, the install folder, the uninstall entry, the user PATH entry and the shortcuts are gone;
- after an upgrade, the app data folder and its files survive the upgrade and the uninstall.

Offline: the Sandbox is configured with networking disabled, and the run records whether any network adapter was visible. Zero outside traffic counts only when the receipt says why the count is zero by construction.

**Application Control can block the installer.** A policy can refuse an unsigned installer in the Sandbox. The lifecycle run saves the last 25 entries of the CodeIntegrity and AppLocker event logs into its output folder (`Microsoft-Windows-CodeIntegrity-Operational.txt`, `Microsoft-Windows-AppLocker-EXE-and-DLL.txt`). Read them. If the policy blocks the installer, the run cannot pass.

- **Never work around the policy.** Do not turn it off or edit it, add an exclusion, sign with a test certificate to get past it, or edit a receipt.
- **A waiver is not a pass.** The release gate reports the check as `waived` only with the owner's written decision for this candidate (`sandbox-waiver.json`: schema `joy-media.sandbox-waiver/1`, `candidateSha`, `owner`, `decidedAt`, `ownerWords`, `reason`). The report then says "not passed" and lists every blocker. Without the waiver the check fails.

Pitfalls:

- The Sandbox scripts run in Windows PowerShell 5, so receipts start with a UTF-8 byte-order mark. Strip it before `JSON.parse` (section 6c).
- The uninstaller removes its folder in the background. Wait up to 60 seconds after uninstall before you read the state.
- The script refuses an existing output folder. Use a new one for every run.

## 10. QC and provider acceptance

**Technical QC of one file.** `joy-media qc <file> --json` runs the Worker's own media checks in this process. It uses no model, no network and no paid service.

- Exit codes: `0` clean; `1` a fault finding or a failure; `2` a usage error (exactly one file).
- A `scene-cut` is information. It never fails a file.
- With `--json`, stdout holds only the report (`findings`, `technical`, `technical.checksRun`, `technical.truncated`). Logs go to stderr.
- A missing file exits `1` with `{ "ok": false, "error": ... }`.
- Pitfall: a clean exit with a non-empty `technical.truncated` is not a full pass. Report which checks did not run.

**Provider acceptance: one short call per provider.** Run this once per provider, not in a loop.

1. **Sign in or add a key.** Use OAuth (`joy-media agent provider add <name> --oauth --provider <chatgpt|kimi|xai>`) or the app's provider settings. For a key on the command line, pipe it on stdin with `--api-key -`. Never put a key in argv, chat, notes or a log. If a provider shows a browser check or a sign-in page, the owner does that step. Do not try to pass it.
2. **Load models.** `joy-media agent models <provider>` (network) or the model list in settings. `joy-media agent probe` checks the configured provider's capabilities.
3. **Ask one short question** (for example: reply with the single word "ok"). Read the answer text itself. A non-empty JSON envelope or a 200 status is not an answer.
4. **Record the result per provider.**
   - Pass: the answer text was read.
   - Blocked: HTTP 429 means a usage limit. Record it as a limit, not as an app failure. Do not retry in a loop.
   - Failed: paste the error line with keys and tokens removed.
5. Do not repeat a paid or limited call without a new reason.

## 11. Release upload and checks

`tooling/release/upload-release.ps1 -Tag <vX.Y.Z> -Dir <folder> [-Repo <owner>/<repo>] [-MaxTries 120] [-WaitSeconds 30]`

- **Draft only.** It finds the draft release with the tag and refuses when there is none. It never publishes and never touches a published release. It never deletes a file from the local folder.
- **One file per call,** in name order. A file already in state `uploaded` is skipped. Otherwise the script removes a half-uploaded asset of the same name, uploads the file, checks its state, and waits 30 seconds before the next try. It stops after 120 tries per file and lists the names it could not upload.
- **Read the list it prints** (name, size, state) and check that every file is `uploaded`.

Then verify the draft:

1. Download into an **empty new folder**: `gh release download <tag> --repo <owner>/<repo> --dir <empty folder>`.
2. Hash every file (`Get-FileHash -Algorithm SHA256`) and compare each with `SHA256SUMS.txt`. Every file must match, and the folder must hold no extra file.
3. **Logged-out download check.** After the release is published, download one asset in a browser window with no GitHub session, and hash it. A draft is not visible without access, so this check applies only to a published release.

Pitfalls:

- Filter the release list on parsed JSON, not on text passed to `gh`. The script does this; copy the pattern if you write your own.
- A retry that finds the file already `uploaded` skips it. Check the final list, not the number of tries.

## 12. The Antigravity helper method

Use a helper agent through its browser tab or its desktop app (one of the two, not both at once).

- **One conversation per task.** Start a new one for each task so old context does not leak in.
- **Text-only prompts.** Say "do not edit files; answer in text". Name the files to read by path.
- **Long patches:** paste with a real keystroke paste (Ctrl+V), then check the pasted text is complete before you send it.
- **Long answers:** read them with the Copy button, then read the clipboard. The page view can cut them short.
- **"Connecting to instance"** in the web tab means the desktop instance is offline. Open the desktop app, then reload the tab.
- **Its answers are advice.** Verify each claim against the code before you act on it. Some are wrong.
- Keep the answer and the conversation name with the task's notes.

## 13. New pitfalls (November 2026)

- **Isolated CLI tests.** Point `APPDATA`, `LOCALAPPDATA`, `USERPROFILE`, `HOME`, `TEMP` and `JOY_MEDIA_HOME` at a scratch folder. The CLI's project database follows `APPDATA`, not `JOY_MEDIA_HOME`, so setting only `JOY_MEDIA_HOME` still writes to the real profile.
- **Vitest in a restricted sandbox** may need `--configLoader runner`. The repo's plans use it for the editor and the touched packages.
- **PowerShell 7 child processes.** A child Windows PowerShell (for `Get-FileHash` and similar) can load the wrong modules when it inherits the PowerShell 7 `PSModulePath`. Start it with a clean `PSModulePath`.
- **Native command arguments with embedded quotes** are fragile in PowerShell. Pass the arguments as an array, or through a file, and check the command line the child process received.
- **A driver marked NOT RUN** has never passed on the app. Do not report its rows as tested.

## 14. Report like this

State what was run (build, profile copy, layout), the numbers (phase times, peak memory, sizes, tags), the checks that passed (`joy://` key unchanged, folder diffs empty, decode clean), what was **not** verified, and the one decision you need from the owner. Say "one run per build" when that is all you have. For a manual run, list the checks done by hand separately from the ones a tool measured, and list what was not run. A manual run is not a substitute for a scripted receipt.
