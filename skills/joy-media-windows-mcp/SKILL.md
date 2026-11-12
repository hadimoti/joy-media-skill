---
name: joy-media-windows-mcp
description: Drive the JOY Media (JOY Studio) Electron desktop app on Windows with the Windows-MCP tools. Launch an isolated test copy, make a project, import media, click Export MP4, save the Windows Save dialog, then check the result (ffprobe, full decode, colour patches, timings from the app's own database). Use when asked to test, run, time or verify an export in the JOY Media desktop app, or to compare builds.
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
  -ArgumentList @($app, '--user-data-dir=C:\jgp\<new-profile>', '--enable-logging=stderr') `
  -WorkingDirectory $app `
  -RedirectStandardOutput 'C:\jgp\run\stdout.log' -RedirectStandardError 'C:\jgp\run\stderr.log' -PassThru
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
- **One lock file for app launches** when two agents share the PC: `C:\jgp\LOCK-app-run.txt` (name, time, reason); delete your own when done.
- A startup error box "Failed to get 'documents' path" appears when a run uses a scratch `USERPROFILE` that has no Documents folder (a development build of folder projects). Set the build's projects-folder override, or give the scratch profile a Documents folder.

## 7. Report like this

State what was run (build, profile copy, layout), the numbers (phase times, peak memory, sizes, tags), the checks that passed (`joy://` key unchanged, folder diffs empty, decode clean), what was **not** verified, and the one decision you need from the owner. Say "one run per build" when that is all you have. For a manual run, list the checks done by hand separately from the ones a tool measured, and list what was not run. A manual run is not a substitute for a scripted receipt.
