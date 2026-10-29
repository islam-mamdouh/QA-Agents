"""Simple incident log: one markdown table per run (runs/<id>/incidents.md)."""
from datetime import datetime
from pathlib import Path

HEADER = (
    "# Incidents\n\n"
    "| Time | Step | Type | What happened | Action taken |\n"
    "|------|------|------|---------------|--------------|\n"
)

# Types used in the project:
#   retry         - network / rate limit / server error, the call is retried
#   fire_back     - an agent reply was unusable, the agent was asked to fix it
#   review_limit  - reviewer still had major issues after the last round
#   data          - something odd in the input data (dependency cycle, unknown test id...)
#   failure       - the run stopped; fix the cause and resume


class Incidents:
    def __init__(self, path: Path):
        self.path = path

    def log(self, step: str, kind: str, message: str, action: str = "") -> None:
        if not self.path.exists():
            self.path.write_text(HEADER, encoding="utf-8")
        clean = lambda s: str(s).replace("|", "/").replace("\n", " ").strip()[:500]
        time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.path.open("a", encoding="utf-8") as f:
            f.write(f"| {time} | {step} | {kind} | {clean(message)} | {clean(action)} |\n")
        print(f"  [incident:{kind}] {step}: {clean(message)}" + (f" -> {clean(action)}" if action else ""))

    def count(self) -> int:
        if not self.path.exists():
            return 0
        return max(0, len(self.path.read_text(encoding="utf-8").splitlines()) - 4)
