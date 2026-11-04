# joy-media-skill

An agent skill for driving the **JOY Media** desktop app (Electron, Windows) with the **Windows-MCP** tools: launch an isolated test copy, click through the editor, export, save, and check the result with facts (ffprobe, full decode, colour patches, phase times from the app's own database).

JOY Media: https://github.com/hadimoti/joy-media

## What is in here

```
skills/joy-media-windows-mcp/
  SKILL.md                 the skill (method, safety rules, coordinates, pitfalls)
  scripts/
    list-tree.ps1          list a folder tree (path, length, mtime) to prove nothing changed
    sampler.ps1            per-process memory / CPU / NVENC / GPU sampler, once a second
    export-times.py        phase times and staged sizes per export from a COPY of the app database
    fxgen.py               build colour-patch test videos with ffmpeg (BT.709, BT.601, full range, rotated, VFR, 10-bit, HEVC, VP9, AV1, interlaced, ...)
    fxcheck.py             self-check of those videos
    fxplace.py             find where a clip landed in an export and score the patch colours
```

## Install

Copy the folder `skills/joy-media-windows-mcp` into your agent's skills folder (for Claude Code: `~/.claude/skills/`, or a project's `.claude/skills/`). The agent needs the Windows-MCP server, PowerShell, `ffmpeg`/`ffprobe` on PATH, and Python 3 with `numpy` for the pixel scripts (run them with `python -I`).

## Safety in one line

Use a separate unpacked app copy and a **new** `--user-data-dir`; never touch the installed app; check the `joy://` registry key before and after; delete nothing; ask the owner before every run.

## Status

Written from real test runs on JOY Media 1.1.0 development builds. Screen coordinates are for one 4920x2160 layout and are a starting map only. Findings in the skill (for example, the first export after launch is BT.709 and later ones BT.601 on the tested machine) are observations from that machine, not guarantees.

## License

MIT. See `LICENSE`.
