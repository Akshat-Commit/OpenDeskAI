"""
OpenDesk Automated Test Suite
=============================
A comprehensive, interactive test runner for the OpenDesk AI agent.

Usage:
    python test_opendesk.py --all              Run all levels sequentially
    python test_opendesk.py --level 1          Run only a specific level
    python test_opendesk.py --category files   Run tests by category name
    python test_opendesk.py --test spotify     Run tests matching a keyword
    python test_opendesk.py --resume           Resume from last saved checkpoint
    python test_opendesk.py --fix              Re-run only previously failed tests
"""

import sys
import os
import json
import time
import signal
import argparse
import traceback
from datetime import datetime

# Ensure the project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ============================================================
# GLOBALS
# ============================================================
REPORT_FILE = os.path.join(PROJECT_ROOT, "test_report.json")
results = []
current_level = 0
interrupted = False

# ============================================================
# SIGNAL HANDLER — Graceful Ctrl+C
# ============================================================
def handle_interrupt(sig, frame):
    global interrupted
    interrupted = True
    print("\n\n\033[93m⚠️  Ctrl+C detected! Saving partial report...\033[0m")
    save_report()
    print(f"\033[92m✅ Report saved to {REPORT_FILE}\033[0m")
    print(f"\033[96m💡 Resume later with: python test_opendesk.py --resume\033[0m")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_interrupt)

# ============================================================
# ALL TEST LEVELS
# ============================================================
LEVELS = [
    {
        "number": 1,
        "name": "Basic Commands",
        "category": "basic",
        "tests": [
            ("what time is it", "get_time", "Get current time"),
            ("what is my battery level", "get_battery", "Get battery level"),
            ("what is my laptop name", "get_system_info", "Get laptop name"),
            ("what is my ip address", "get_ip", "Get IP address"),
            ("how much ram am i using", "get_ram", "Get RAM usage"),
            ("what is my cpu usage", "get_cpu", "Get CPU usage"),
        ],
    },
    {
        "number": 2,
        "name": "Volume & System",
        "category": "volume",
        "tests": [
            ("set volume to 50", "set_volume", "Set volume to 50%"),
            ("set volume to 0", "set_volume", "Set volume to 0%"),
            ("set volume to 100", "set_volume", "Set volume to 100%"),
            ("mute the volume", "control_media", "Mute volume"),
            ("unmute the volume", "control_media", "Unmute volume"),
            ("what is current volume level", "get_volume", "Get current volume"),
        ],
    },
    {
        "number": 3,
        "name": "File Operations",
        "category": "files",
        "tests": [
            ("list my desktop files", "list_files", "List desktop files"),
            ("list my downloads files", "list_files", "List downloads files"),
            ("create a file called test.txt with content hello world", "create_file", "Create test.txt"),
            ("read the file test.txt", "read_file", "Read test.txt"),
            ("find file ak.jpg", "find_file", "Find ak.jpg"),
            ("share file ak.jpg via telegram", "share_file", "Share ak.jpg"),
            ("delete file test.txt", "delete_file", "Delete test.txt"),
        ],
    },
    {
        "number": 4,
        "name": "App Control",
        "category": "apps",
        "tests": [
            ("open chrome", "open_app", "Open Chrome"),
            ("open notepad", "open_app", "Open Notepad"),
            ("open calculator", "open_app", "Open Calculator"),
            ("open spotify", "open_app", "Open Spotify"),
            ("close notepad", "close_app", "Close Notepad"),
            ("close calculator", "close_app", "Close Calculator"),
        ],
    },
    {
        "number": 5,
        "name": "Media Control",
        "category": "media",
        "tests": [
            ("play music on spotify", "play_spotify_music", "Play Spotify music"),
            ("pause the music", "control_media", "Pause music"),
            ("resume the music", "control_media", "Resume music"),
            ("next song", "control_media", "Next song"),
            ("previous song", "control_media", "Previous song"),
        ],
    },
    {
        "number": 6,
        "name": "Browser Control",
        "category": "browser",
        "tests": [
            ("search google for weather today", "browser_search", "Google search"),
            ("search youtube for lofi music", "browser_search", "YouTube search"),
            ("open youtube.com", "open_url", "Open YouTube"),
            ("open github.com", "open_url", "Open GitHub"),
        ],
    },
    {
        "number": 7,
        "name": "Screenshots",
        "category": "screenshot",
        "tests": [
            ("take a screenshot", "take_screenshot", "Take screenshot"),
            ("take screenshot and share it here", "take_screenshot", "Screenshot and share"),
        ],
    },
    {
        "number": 8,
        "name": "Document Creation",
        "category": "documents",
        "tests": [
            ("create a word document called meeting notes", "create_word_doc", "Create Word doc"),
            ("create an excel file with 3 rows and 2 columns", "create_excel_file", "Create Excel file"),
            ("create a presentation with 2 slides", "create_powerpoint", "Create PowerPoint"),
        ],
    },
    {
        "number": 9,
        "name": "Complex Multi-Step",
        "category": "complex",
        "tests": [
            ("open chrome and search for python tutorials", "multi_step", "Chrome + Google search"),
            ("take a screenshot and send it to me", "multi_step", "Screenshot + share"),
            ("find test.txt and share it via telegram", "multi_step", "Find + share file"),
            ("open notepad write hello world and save it", "multi_step", "Notepad write + save"),
        ],
    },
]

# ============================================================
# AGENT WRAPPER — calls the async langchain_agent.run()
# ============================================================
def call_agent(command: str):
    """Calls the OpenDesk agent with a command and returns (response_text, attachments)."""
    import asyncio
    from opendesk.ollama_agent.langchain_agent import run as agent_run
    # Run the async agent function in a new event loop for each test
    return asyncio.run(agent_run(command, memory_history=""))


# ============================================================
# TEST RUNNER
# ============================================================
def test_command(command, expected_tool, description, level):
    """Runs a single test command against the agent."""
    print(f"\n  \033[96m🔹 Testing:\033[0m {description}")
    print(f"     Command: \033[93m\"{command}\"\033[0m")

    start_time = time.time()
    try:
        is_error = False
        response_text, attachments = call_agent(command)
        elapsed = round(float(time.time() - start_time), 2)
        if response_text and isinstance(response_text, str):
            is_error = ("error" in response_text.lower() and "agent stopped" in response_text.lower())

        if response_text and not is_error:
            result_entry = {
                "level": level,
                "test": description,
                "command": command,
                "expected_tool": expected_tool,
                "status": "PASS",
                "response": str(response_text)[:300],
                "attachments": attachments,
                "elapsed_s": elapsed,
                "timestamp": str(datetime.now()),
            }
            results.append(result_entry)
            print(f"     \033[92m✅ PASS\033[0m ({elapsed}s)")
            if response_text:
                # Show a short preview of the response
                preview = str(response_text)[:120].replace("\n", " ")
                print(f"     Response: {preview}...")
            return True
        else:
            result_entry = {
                "level": level,
                "test": description,
                "command": command,
                "expected_tool": expected_tool,
                "status": "FAIL",
                "response": str(response_text)[:500] if response_text else "No response",
                "attachments": attachments,
                "elapsed_s": elapsed,
                "timestamp": str(datetime.now()),
            }
            results.append(result_entry)
            print(f"     \033[91m❌ FAIL\033[0m ({elapsed}s)")
            print(f"     Response: {str(response_text)[:200] if response_text else 'Empty'}")
            return False

    except Exception as e:
        elapsed = round(float(time.time() - start_time), 2)
        result_entry = {
            "level": level,
            "test": description,
            "command": command,
            "expected_tool": expected_tool,
            "status": "ERROR",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "elapsed_s": elapsed,
            "timestamp": str(datetime.now()),
        }
        results.append(result_entry)
        print(f"     \033[91m💥 ERROR\033[0m ({elapsed}s)")
        print(f"     {str(e)[:200]}")
        
    # ANTI-RATE LIMIT PAUSE
    print("     \033[90m⏳ Waiting 35s to prevent API rate limits...\033[0m")
    time.sleep(35)
    
    return not is_error and response_text


# ============================================================
# LEVEL REPORT
# ============================================================
def show_level_report(level_name, level_results):
    total = len(level_results)
    passed = sum(1 for r in level_results if r["status"] == "PASS")
    failed = total - passed

    print(f"\n  {'─' * 46}")
    print(f"  📊 {level_name} — {passed}/{total} passed", end="")
    if failed > 0:
        print(f" | \033[91m{failed} failed\033[0m")
        for r in level_results:
            if r["status"] != "PASS":
                print(f"     ❌ {r['test']}: {r.get('error', r.get('response', '?'))[:80]}")
    else:
        print(f" | \033[92mAll clear!\033[0m")
    print(f"  {'─' * 46}")


# ============================================================
# INTERACTIVE PROMPT
# ============================================================
def ask_continue(level_name, has_failures):
    if has_failures:
        answer = input(
            f"\n  \033[93m⚠️  Some tests failed in {level_name}.\033[0m"
            f"\n  Fix failures before continuing? (y/n): "
        ).strip().lower()
        if answer == "y":
            print("  Please fix the issues, then press Enter to retest this level...")
            input()
            return "retest"

    answer = input(f"\n  Continue to next level? (y/n): ").strip().lower()
    return "continue" if answer == "y" else "stop"


# ============================================================
# REPORT PERSISTENCE
# ============================================================
def save_report():
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")

    report = {
        "timestamp": str(datetime.now()),
        "score": f"{passed}/{total}",
        "last_level": current_level,
        "summary": {"total": total, "passed": passed, "failed": total - passed},
        "results": results,
    }

    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)


def load_report():
    if os.path.exists(REPORT_FILE):
        with open(REPORT_FILE, "r") as f:
            return json.load(f)
    return None


# ============================================================
# MAIN LEVEL RUNNER
# ============================================================
def run_level(level_info):
    global current_level
    level_number = level_info["number"]
    level_name = level_info["name"]
    tests = level_info["tests"]
    current_level = level_number

    print(f"\n{'=' * 50}")
    print(f"  LEVEL {level_number}: {level_name}")
    print(f"  ({len(tests)} tests)")
    print(f"{'=' * 50}")

    level_results = []

    for command, tool, description in tests:
        if interrupted:
            break
        test_command(command, tool, description, level_number)
        level_results.append(results[-1])
        # Small delay between tests to avoid rate limits
        time.sleep(2)

    has_failures = any(r["status"] != "PASS" for r in level_results)
    show_level_report(level_name, level_results)
    save_report()

    return ask_continue(level_name, has_failures)


# ============================================================
# ENTRY POINTS
# ============================================================
def run_all():
    print("=" * 50)
    print("  🚀 OpenDesk Automated Test Suite")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  Press Ctrl+C anytime to stop & save")
    print("=" * 50)

    for level_info in LEVELS:
        if interrupted:
            break

        action = run_level(level_info)

        if action == "stop":
            print("\n  ⏸️  Tests paused by user.")
            break
        elif action == "retest":
            run_level(level_info)

    show_final_report()


def run_single_level(level_number):
    level_info = next((l for l in LEVELS if l["number"] == level_number), None)
    if not level_info:
        print(f"\033[91m❌ Level {level_number} not found. Valid levels: 1-{len(LEVELS)}\033[0m")
        return
    print("=" * 50)
    print(f"  🚀 Running Level {level_number}: {level_info['name']}")
    print("=" * 50)
    run_level(level_info)
    show_final_report()


def run_category(category_name):
    category_name = category_name.lower()
    matching = [l for l in LEVELS if category_name in l["category"]]
    if not matching:
        all_cats = ", ".join(l["category"] for l in LEVELS)
        print(f"\033[91m❌ Category '{category_name}' not found. Available: {all_cats}\033[0m")
        return
    print("=" * 50)
    print(f"  🚀 Running category: {category_name}")
    print("=" * 50)
    for level_info in matching:
        if interrupted:
            break
        run_level(level_info)
    show_final_report()


def run_keyword(keyword):
    keyword = keyword.lower()
    matched_tests = []
    for level_info in LEVELS:
        for command, tool, description in level_info["tests"]:
            if keyword in command.lower() or keyword in description.lower() or keyword in tool.lower():
                matched_tests.append((level_info["number"], command, tool, description))

    if not matched_tests:
        print(f"\033[91m❌ No tests matching '{keyword}'\033[0m")
        return

    print("=" * 50)
    print(f"  🚀 Running {len(matched_tests)} tests matching: '{keyword}'")
    print("=" * 50)

    for level_num, command, tool, description in matched_tests:
        if interrupted:
            break
        test_command(command, tool, description, level_num)
        time.sleep(2)

    show_final_report()


def run_resume():
    report = load_report()
    if not report:
        print("\033[91m❌ No previous report found. Run --all first.\033[0m")
        return

    last_level = report.get("last_level", 0)
    print("=" * 50)
    print(f"  🔄 Resuming from Level {last_level + 1}")
    print(f"  Previous score: {report['score']}")
    print("=" * 50)

    # Load previous results
    global results
    results = report.get("results", [])

    for level_info in LEVELS:
        if level_info["number"] <= last_level:
            continue
        if interrupted:
            break
        action = run_level(level_info)
        if action == "stop":
            break
        elif action == "retest":
            run_level(level_info)

    show_final_report()


def run_fix():
    report = load_report()
    if not report:
        print("\033[91m❌ No previous report found. Run --all first.\033[0m")
        return

    failed_tests = [r for r in report.get("results", []) if r["status"] != "PASS"]
    if not failed_tests:
        print("\033[92m✅ No failed tests to fix! Everything passed.\033[0m")
        return

    print("=" * 50)
    print(f"  🔧 Re-running {len(failed_tests)} failed tests")
    print("=" * 50)

    for failed in failed_tests:
        if interrupted:
            break
        test_command(
            failed["command"],
            failed.get("expected_tool", "unknown"),
            failed["test"],
            failed["level"],
        )
        time.sleep(2)

    show_final_report()


# ============================================================
# FINAL REPORT
# ============================================================
def show_final_report():
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = total - passed

    print(f"\n{'=' * 50}")
    print("  📋 FINAL TEST REPORT")
    print(f"{'=' * 50}")
    print(f"  Total Tests:  {total}")
    print(f"  \033[92m✅ Passed:     {passed}\033[0m")
    if failed > 0:
        print(f"  \033[91m❌ Failed:     {failed}\033[0m")
    print(f"  Score:        {passed}/{total}")
    print(f"{'=' * 50}")

    if failed > 0:
        print(f"\n  \033[91mFailed Tests:\033[0m")
        for r in results:
            if r["status"] != "PASS":
                print(f"\n  ❌ [{r.get('level', '?')}] {r['test']}")
                print(f"     Command:  {r['command']}")
                print(f"     Error:    {r.get('error', r.get('response', '?'))[:150]}")

    save_report()
    print(f"\n  💾 Full report saved to: {REPORT_FILE}")
    print(f"  💡 Re-run failures with: python test_opendesk.py --fix")
    print(f"  💡 Resume from last level: python test_opendesk.py --resume\n")


# ============================================================
# CLI ENTRY
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenDesk Automated Test Suite")
    parser.add_argument("--all", action="store_true", help="Run all test levels")
    parser.add_argument("--level", type=int, help="Run a specific level (1-9)")
    parser.add_argument("--category", type=str, help="Run tests by category (basic, volume, files, apps, media, browser, screenshot, documents, complex)")
    parser.add_argument("--test", type=str, help="Run tests matching a keyword")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--fix", action="store_true", help="Re-run only previously failed tests")
    args = parser.parse_args()

    if args.level:
        run_single_level(args.level)
    elif args.category:
        run_category(args.category)
    elif args.test:
        run_keyword(args.test)
    elif args.resume:
        run_resume()
    elif args.fix:
        run_fix()
    elif args.all:
        run_all()
    else:
        # Default: interactive mode
        print("\033[96m")
        print("  OpenDesk Test Suite — Choose an option:")
        print("  ─────────────────────────────────────────")
        print("  1. Run ALL levels")
        print("  2. Run a specific level (1-9)")
        print("  3. Resume from last checkpoint")
        print("  4. Re-run failed tests only")
        print("\033[0m")
        choice = input("  Enter choice (1-4): ").strip()
        
        if choice == "1":
            run_all()
        elif choice == "2":
            level = input("  Enter level number (1-9): ").strip()
            run_single_level(int(level))
        elif choice == "3":
            run_resume()
        elif choice == "4":
            run_fix()
        else:
            print("  Invalid choice. Run with --help for options.")
