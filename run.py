#!/usr/bin/env python3
"""QA agents for the ZATCA Customs Clearance project (Fasah) - command line.

One run = one Change Request (CR). Paste the CR text from Jira into projects/zatca/crs/<CR-ID>.md
first; there is no Jira integration.

  python3 run.py check                          test config and the Claude Code login
  python3 run.py design --cr CR-ID [--file F]   CR analysis -> test plan -> test cases (test_cases.xlsx)
  python3 run.py resume [--run ID | --cr CR-ID] continue a stopped run from its last checkpoint
  python3 run.py report [--run ID | --cr CR-ID] [--results FILE]
                                                your results -> POT, bug reports, UAT summary, quality report
  python3 run.py status [--run ID | --cr CR-ID] show steps, review rounds, tokens and incidents
  python3 run.py monthly [--month YYYY-MM]      monthly quality report: KPIs and trend, defect leakage,
                                                control chart per build, Pareto, process audit

Without --run or --cr, the latest run is used. Everything lives in projects/zatca/.
"""
import argparse
import sys
import traceback
from pathlib import Path

from qa_flow.config import ConfigError, load_config
from qa_flow.intake import IntakeError, cr_path
from qa_flow.llm import LLM
from qa_flow.orchestrator import Orchestrator
from qa_flow.store import RunStore


def cmd_check(cfg: dict) -> None:
    def check(name, fn):
        try:
            result = fn()
            print(f"  OK    {name}" + (f": {result}" if isinstance(result, str) else ""))
        except Exception as error:  # noqa: BLE001 - report any problem
            print(f"  FAIL  {name}: {str(error)[:200]}")

    # One tiny real call per model through Claude Code, using your Claude login.
    # Its usage and incidents are kept in a separate "_checks" folder, not in a real run.
    llm = LLM(cfg, RunStore(Path(cfg["flow"]["runs_dir"]) / "_checks"))
    for role in ("main", "reviewer"):
        model = cfg["models"][role]
        check(f"Claude Code, {role} model ({model})",
              lambda: llm.ask_json(model, 'Reply with ONLY this JSON: {"ok":true}', "ping", "check"))

    def crs():
        folder = Path(cfg["inputs"]["crs_dir"])
        if not folder.is_dir():
            raise FileNotFoundError(f"{folder} does not exist; create it and add one <CR-ID>.md per CR")
        return f"{len(list(folder.glob('*.md')))} CR file(s) in {folder}"
    check("CR folder", crs)
    check("System knowledge", lambda: f"{len(cfg['knowledge'])} characters loaded from {cfg['inputs']['knowledge_dir']}"
          if cfg["knowledge"] else "none (optional: add *.md files to the knowledge folder)")


def cmd_status(store: RunStore) -> None:
    s = store.state
    print(f"Run {s['run_id']}  CR={s.get('cr')}  phase={s['phase']}  status={s['status']}  "
          f"current step={s.get('current_step')}")
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
        print(f"No finished CR reports in {out['month']}.")
    print(f"Monthly report {out['month']} ({out['runs']} CR runs): {out['report']}\nExcel: {out['excel']}")
    print(f"Add defects found after release (with root cause and 5 Whys) to: {out['escaped_file']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["check", "design", "resume", "report", "status", "monthly"])
    parser.add_argument("--cr", help="CR id, e.g. CR-1234 (design: required; other commands: its latest run)")
    parser.add_argument("--file", help="design only: CR text file; default: projects/zatca/crs/<CR-ID>.md")
    parser.add_argument("--run", help="run id (folder name in projects/zatca/runs/); default: latest")
    parser.add_argument("--month", help="monthly only: YYYY-MM; default: the current month")
    parser.add_argument("--results", help="report only: results file; default: runs/<id>/results.csv")
    args = parser.parse_args()

    try:
        cfg = load_config()
    except ConfigError as error:
        print(f"Config error: {error}")
        return 2

    if args.command == "check":
        cmd_check(cfg)
        return 0
    if args.command == "monthly":
        return cmd_monthly(cfg, args.month)

    runs_dir = cfg["flow"]["runs_dir"]
    try:
        if args.command == "design":
            if not args.cr:
                print("design needs --cr, e.g. python3 run.py design --cr CR-1234")
                return 2
            path = Path(args.file) if args.file else cr_path(cfg["inputs"]["crs_dir"], args.cr)
            if not path.exists():
                print(f"CR file not found: {path}\nCopy the CR text from Jira into it, then run again.")
                return 2
            store = RunStore.create(runs_dir, args.cr)
        else:
            store = RunStore.open(runs_dir, args.run, args.cr)
    except (FileNotFoundError, IntakeError) as error:
        print(error)
        return 2
    if args.command == "status":
        cmd_status(store)
        return 0

    print(f"Run {store.dir.name}")
    orchestrator = Orchestrator(cfg, store)
    try:
        if args.command == "design":
            store.set(cr_file=args.file)
            orchestrator.design(args.cr, args.file)
        elif args.command == "report":
            orchestrator.report(args.results)
        else:  # resume: continue whatever phase was running
            if store.state["phase"] == "report":
                orchestrator.report(store.state.get("results_file"))
            elif store.state["status"] == "waiting_for_results":
                print("Design is finished. Run the test cases, fill in results.csv, then run: "
                      f"python3 run.py report --run {store.dir.name}")
            else:
                orchestrator.design(store.state["cr"], store.state.get("cr_file"))
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
