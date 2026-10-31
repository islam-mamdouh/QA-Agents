#!/usr/bin/env python3
"""QA agents for the ZATCA project - command line.

  python3 run.py check                              test config, Claude Code login, Jira and Google Sheets access
  python3 run.py design [--jql "..."]               new run: stories -> analysis -> plan -> test cases (steps 1-13)
  python3 run.py resume [--run ID]                  continue a stopped run from its last checkpoint
  python3 run.py report [--run ID] [--results FILE] your results -> report -> Google Sheets (steps 14-15)
  python3 run.py status [--run ID]                  show steps, review rounds, tokens and incidents
  python3 run.py monthly [--month YYYY-MM]          monthly quality report: KPIs and trend, defect leakage,
                                                    control chart, Pareto, process audit

Config, credentials and runs live in projects/zatca/. Without --run, the latest run is used.
"""
import argparse
import sys
import traceback
from pathlib import Path

from qa_flow.config import DEFAULT_PROJECT, ConfigError, load_config, require
from qa_flow.llm import LLM
from qa_flow.orchestrator import Orchestrator
from qa_flow.store import RunStore


def cmd_check(cfg: dict) -> None:
    import gspread
    import requests

    def check(name, fn):
        try:
            fn()
            print(f"  OK    {name}")
        except Exception as error:  # noqa: BLE001 - report any problem
            print(f"  FAIL  {name}: {str(error)[:200]}")

    # One tiny real call per model through Claude Code, using your Claude login.
    # Its usage and incidents are kept in a separate "_checks" folder, not in a real run.
    llm = LLM(cfg, RunStore(Path(cfg["flow"]["runs_dir"]) / "_checks"))
    for role in ("main", "reviewer"):
        model = cfg["models"][role]
        check(f"Claude Code, {role} model ({model})",
              lambda: llm.ask_json(model, 'Reply with ONLY this JSON: {"ok":true}', "ping", "check"))

    def jira():
        r = requests.get(require(cfg, "jira.base_url").rstrip("/") + "/rest/api/3/myself", timeout=30,
                         auth=(require(cfg, "jira.email"), require(cfg, "jira.api_token")))
        r.raise_for_status()
    check("Jira login", jira)
    check("Google Sheet access", lambda: gspread.service_account(
        filename=require(cfg, "google_sheets.service_account_file")).open_by_key(require(cfg, "google_sheets.spreadsheet_id")))


def cmd_status(store: RunStore) -> None:
    s = store.state
    print(f"Run {s['run_id']}  phase={s['phase']}  status={s['status']}  current step={s.get('current_step')}")
    if s.get("last_error"):
        print(f"Last error: {s['last_error']}")
    for key, step in s["steps"].items():
        extra = f" round={step['round']} {step.get('phase')}" if "round" in step else ""
        print(f"  {key:<24} {step.get('status'):<8}{extra}")
    for model, u in s["usage"].items():
        print(f"  {model}: calls={u.get('calls', 0)} input={u.get('input', 0)} cache_write={u.get('cache_write', 0)} "
              f"cache_read={u.get('cache_read', 0)} output={u.get('output', 0)} "
              f"(API-equivalent cost ${u.get('cost_usd', 0)}, not billed on a subscription)")
    print(f"  incidents: {store.incidents.count()} (see {store.incidents.path})")


def cmd_monthly(cfg: dict, month: str | None) -> int:
    from qa_flow.monthly import build_monthly
    try:
        out = build_monthly(cfg, month)
    except ValueError as error:
        print(f"Monthly report error: {error}")
        return 2
    if not out["runs"]:
        print(f"No finished runs in {out['month']}. Escaped defects file: {out['escaped_file']}")
    print(f"Monthly report {out['month']} ({out['runs']} runs): {out['report']}")
    if out["url"]:
        print(f"Google Sheets: {out['url']}")
    print(f"Add bugs found after release to: {out['escaped_file']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["check", "design", "resume", "report", "status", "monthly"])
    parser.add_argument("--project", default=DEFAULT_PROJECT, help=argparse.SUPPRESS)  # folder under projects/
    parser.add_argument("--run", help="run id (folder name in projects/zatca/runs/); default: latest")
    parser.add_argument("--jql", help="override the JQL from config.md (design only)")
    parser.add_argument("--month", help="monthly only: YYYY-MM; default: the current month")
    parser.add_argument("--results", help="results file (report only); default: runs/<id>/results.csv")
    args = parser.parse_args()

    try:
        cfg = load_config(args.project)
    except ConfigError as error:
        print(f"Config error: {error}")
        return 2
    query = args.jql

    if args.command == "check":
        cmd_check(cfg)
        return 0
    if args.command == "monthly":
        return cmd_monthly(cfg, args.month)

    runs_dir = cfg["flow"]["runs_dir"]
    store = RunStore.create(runs_dir) if args.command == "design" else RunStore.open(runs_dir, args.run)
    if args.command == "status":
        cmd_status(store)
        return 0

    print(f"Run {store.dir.name}")
    orchestrator = Orchestrator(cfg, store)
    try:
        if args.command == "design":
            store.set(query=query)
            orchestrator.design(query)
        elif args.command == "report":
            orchestrator.report(args.results)
        else:  # resume: continue whatever phase was running
            if store.state["phase"] == "report":
                orchestrator.report(store.state.get("results_file"))
            elif store.state["status"] == "waiting_for_results":
                print("Design is finished. Fill in results.csv, then run: "
                      f"python3 run.py report --run {store.dir.name}")
            else:
                orchestrator.design(store.state.get("query", store.state.get("jql")))
        return 0
    except KeyboardInterrupt:
        store.set(status="stopped")
        print(f"\nStopped. Continue with: python3 run.py resume --run {store.dir.name}")
        return 130
    except Exception as error:  # noqa: BLE001 - every failure becomes an incident + resume hint
        step = store.state.get("current_step") or store.state["phase"]
        store.set(status="failed", last_error=f"{type(error).__name__}: {error}")
        store.incidents.log(step, "failure", f"{type(error).__name__}: {error}", "run stopped; fix and resume")
        (store.dir / "last_error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        print(f"\nFailed at {step}. Details: {store.dir / 'last_error.txt'}"
              f"\nFix the cause, then: python3 run.py resume --run {store.dir.name}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
