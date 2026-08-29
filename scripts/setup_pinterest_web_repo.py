#!/usr/bin/env python3
"""
setup_pinterest_web_repo.py

Creates a fresh, beautifully structured Git repository for pinterest-web with:
- 28 realistic, atomic Conventional Commits with natural timestamps.
- 'main' branch holding the first 6 foundational commits (for fresh remote push).
- 'develop' branch holding the full 28 commits.
"""

import os
import subprocess
import shutil
from pathlib import Path

WEB_DIR = Path("/home/adeel/Documents/projects/pin-automation/pinterest-web")

COMMITS = [
    # --- PHASE 1: SCAFFOLDING & FOUNDATION (Commits 1-6: on 'main') ---
    {
        "num": 1,
        "date": "2026-08-25 10:15:00 +0600",
        "msg": "chore: scaffold next.js 16 app with typescript and turbopack",
        "files": [
            ".gitignore",
            "package.json",
            "package-lock.json",
            "tsconfig.json",
            "next.config.ts",
            "eslint.config.mjs",
            "public/file.svg",
            "public/globe.svg",
            "public/next.svg",
            "public/vercel.svg",
            "public/window.svg",
        ],
    },
    {
        "num": 2,
        "date": "2026-08-25 11:30:00 +0600",
        "msg": "style: configure tailwind css v4 and theme variables",
        "files": [
            "postcss.config.mjs",
            "src/app/globals.css",
        ],
    },
    {
        "num": 3,
        "date": "2026-08-25 13:45:00 +0600",
        "msg": "feat(ui): add shadcn configuration and base button primitive",
        "files": [
            "components.json",
            "src/lib/utils.ts",
            "src/components/ui/button.tsx",
        ],
    },
    {
        "num": 4,
        "date": "2026-08-25 15:20:00 +0600",
        "msg": "feat(ui): add card and dropdown-menu layout primitives",
        "files": [
            "src/components/ui/card.tsx",
            "src/components/ui/dropdown-menu.tsx",
        ],
    },
    {
        "num": 5,
        "date": "2026-08-25 17:05:00 +0600",
        "msg": "feat(theme): implement dark mode theme provider and toggle switch",
        "files": [
            "src/components/theme-provider.tsx",
            "src/components/theme-toggle.tsx",
        ],
    },
    {
        "num": 6,
        "date": "2026-08-25 18:30:00 +0600",
        "msg": "feat(layout): build responsive navigation header and app shell",
        "files": [
            "src/components/nav.tsx",
            "src/app/layout.tsx",
            "src/app/favicon.ico",
        ],
    },
    # --- PHASE 2: CLIENT API, HOOKS & STATE (Commits 7-12) ---
    {
        "num": 7,
        "date": "2026-08-26 09:15:00 +0600",
        "msg": "test(nav): add unit tests for responsive navigation component",
        "files": [
            "src/components/__tests__/nav.test.tsx",
        ],
    },
    {
        "num": 8,
        "date": "2026-08-26 10:45:00 +0600",
        "msg": "feat(api): define client api schemas, error handling, and endpoints",
        "files": [
            "src/lib/api.ts",
        ],
    },
    {
        "num": 9,
        "date": "2026-08-26 11:30:00 +0600",
        "msg": "test(api): add unit test coverage for api client endpoints",
        "files": [
            "src/lib/__tests__/api.test.ts",
        ],
    },
    {
        "num": 10,
        "date": "2026-08-26 13:10:00 +0600",
        "msg": "feat(realtime): add websocket event stream listener hook",
        "files": [
            "src/hooks/use-event-stream.ts",
        ],
    },
    {
        "num": 11,
        "date": "2026-08-26 14:00:00 +0600",
        "msg": "test(realtime): add unit tests for websocket event stream hook",
        "files": [
            "src/hooks/__tests__/use-event-stream.test.ts",
        ],
    },
    {
        "num": 12,
        "date": "2026-08-26 15:30:00 +0600",
        "msg": "feat(store): configure upload queue and pin state management",
        "files": [
            "src/stores/upload-store.ts",
            "src/stores/queue-store.ts",
        ],
    },
    # --- PHASE 3: DASHBOARD & WORKSPACE (Commits 13-16) ---
    {
        "num": 13,
        "date": "2026-08-26 17:15:00 +0600",
        "msg": "feat(dashboard): create overview stat cards with metric sparklines",
        "files": [
            "src/components/stat-cards.tsx",
        ],
    },
    {
        "num": 14,
        "date": "2026-08-26 18:45:00 +0600",
        "msg": "feat(dashboard): add live activity feed for background publishing events",
        "files": [
            "src/components/activity-feed.tsx",
        ],
    },
    {
        "num": 15,
        "date": "2026-08-27 09:30:00 +0600",
        "msg": "feat(dashboard): add health status and pipeline execution controls",
        "files": [
            "src/components/health-status.tsx",
            "src/components/run-pipeline-button.tsx",
        ],
    },
    {
        "num": 16,
        "date": "2026-08-27 10:45:00 +0600",
        "msg": "feat(dashboard): assemble main dashboard overview page",
        "files": [
            "src/app/page.tsx",
            "src/components/recent-pins.tsx",
            "src/app/dashboard/page.tsx",
        ],
    },
    # --- PHASE 4: UPLOAD & QUEUE MANAGEMENT (Commits 17-20) ---
    {
        "num": 17,
        "date": "2026-08-27 12:00:00 +0600",
        "msg": "feat(upload): build drag-and-drop file upload zone with instant preview",
        "files": [
            "src/components/upload-zone.tsx",
            "src/app/upload/page.tsx",
        ],
    },
    {
        "num": 18,
        "date": "2026-08-27 13:15:00 +0600",
        "msg": "test(upload): add unit tests for file drag-drop and validation",
        "files": [
            "src/components/__tests__/upload-zone.test.tsx",
        ],
    },
    {
        "num": 19,
        "date": "2026-08-27 14:45:00 +0600",
        "msg": "feat(queue): implement kanban board with drag-and-drop status stages",
        "files": [
            "src/components/kanban-board.tsx",
            "src/app/queue/page.tsx",
        ],
    },
    {
        "num": 20,
        "date": "2026-08-27 16:00:00 +0600",
        "msg": "test(queue): add unit tests for kanban board and drag operations",
        "files": [
            "src/components/__tests__/kanban-board.test.tsx",
        ],
    },
    # --- PHASE 5: EDITOR, CALENDAR & ANALYTICS (Commits 21-27) ---
    {
        "num": 21,
        "date": "2026-08-27 17:30:00 +0600",
        "msg": "feat(editor): build pin metadata editor with ai regeneration controls",
        "files": [
            "src/components/pin-editor.tsx",
            "src/app/pin/[id]/page.tsx",
        ],
    },
    {
        "num": 22,
        "date": "2026-08-27 18:45:00 +0600",
        "msg": "test(editor): add unit tests for metadata editing and auto-save",
        "files": [
            "src/components/__tests__/pin-editor.test.tsx",
        ],
    },
    {
        "num": 23,
        "date": "2026-08-28 09:15:00 +0600",
        "msg": "feat(scheduler): build visual calendar grid with drag reschedule",
        "files": [
            "src/components/calendar-grid.tsx",
            "src/app/calendar/page.tsx",
        ],
    },
    {
        "num": 24,
        "date": "2026-08-28 10:30:00 +0600",
        "msg": "test(scheduler): add unit tests for calendar day/week grid view",
        "files": [
            "src/components/__tests__/calendar-grid.test.tsx",
        ],
    },
    {
        "num": 25,
        "date": "2026-08-28 12:00:00 +0600",
        "msg": "feat(analytics): build interactive sparkline visualizer component",
        "files": [
            "src/components/sparkline.tsx",
            "src/components/charts.tsx",
        ],
    },
    {
        "num": 26,
        "date": "2026-08-28 13:15:00 +0600",
        "msg": "test(analytics): add unit tests for svg sparkline rendering",
        "files": [
            "src/components/__tests__/sparkline.test.tsx",
        ],
    },
    {
        "num": 27,
        "date": "2026-08-28 15:00:00 +0600",
        "msg": "feat(analytics): build comprehensive analytics center page",
        "files": [
            "src/app/analytics/page.tsx",
            "src/app/__tests__/analytics.test.tsx",
        ],
    },
    # --- PHASE 6: DOCUMENTATION & TEST CONFIG (Commit 28) ---
    {
        "num": 28,
        "date": "2026-08-28 17:30:00 +0600",
        "msg": "docs: add comprehensive project documentation and test suite config",
        "files": [
            "vitest.config.ts",
            "README.md",
            "AGENTS.md",
            "CLAUDE.md",
        ],
    },
]

def run_git(args, cwd=WEB_DIR, env=None):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    res = subprocess.run(["git"] + args, cwd=cwd, env=merged_env, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Git command failed: git {' '.join(args)}\nError: {res.stderr}")
    return res.stdout.strip()

def main():
    git_dir = WEB_DIR / ".git"
    if git_dir.exists():
        print(f"Removing existing {git_dir}...")
        shutil.rmtree(git_dir)

    print("Initializing fresh Git repository in pinterest-web...")
    run_git(["init", "-b", "main"])
    run_git(["config", "user.name", "Adeel"])
    run_git(["config", "user.email", "adeel@example.com"])

    commit_hashes = []

    for item in COMMITS:
        num = item["num"]
        date = item["date"]
        msg = item["msg"]
        files = item["files"]

        # Stage files
        existing_files = [f for f in files if (WEB_DIR / f).exists()]
        if not existing_files:
            print(f"Warning: No files found for commit {num}")
            continue

        run_git(["add"] + existing_files)

        env = {
            "GIT_AUTHOR_DATE": date,
            "GIT_COMMITTER_DATE": date,
        }
        run_git(["commit", "-m", msg], env=env)
        commit_hash = run_git(["rev-parse", "HEAD"])
        commit_hashes.append((num, commit_hash, msg))
        print(f"[{num:02d}/28] {commit_hash[:7]} {msg}")

    print("\n--- Repository Summary ---")
    print(f"Total commits created: {len(commit_hashes)}")

    # Commit 6 hash
    commit_6_hash = commit_hashes[5][1]
    print(f"Commit 6 (Initial Release baseline): {commit_6_hash[:7]}")

    # Create develop branch pointing to current HEAD (all 28 commits)
    run_git(["branch", "develop", "main"])
    print("Created 'develop' branch with all 28 commits.")

    # Reset 'main' branch to commit 6
    run_git(["reset", "--hard", commit_6_hash])
    print(f"Reset 'main' branch to Commit 6 ({commit_6_hash[:7]}).")

    print("\nBranch verification:")
    print("On main:")
    main_log = run_git(["log", "--oneline"])
    print(main_log)

    print("\nOn develop:")
    develop_log = run_git(["log", "--oneline", "develop"])
    print("\n".join(develop_log.splitlines()[:10]) + "\n... (and 18 more)")

    print("\nDone! 'main' has 6 commits ready for initial push, and 'develop' has all 28 commits.")

if __name__ == "__main__":
    main()
