"""Counterfactual proof: delete the lines, run the tests, see what breaks.
DANGER: runs repository code. Only enable (ENABLE_PROOF=1) inside an isolated sandbox (Docker/gVisor/E2B), never on a shared host."""
import os, shlex, subprocess


def counterfactual(d, path, s, e):
    if os.getenv("ENABLE_PROOF") != "1":
        return {"status": "disabled", "note": "Set ENABLE_PROOF=1 inside an isolated sandbox to enable."}
    cmd, to = shlex.split(os.getenv("PROOF_CMD", "python -m pytest -x -q")), int(os.getenv("PROOF_TIMEOUT", "120"))
    run = lambda: subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=to)
    try:
        subprocess.run(["git", "checkout", "-q", "HEAD", "--", "."], cwd=d, timeout=180, check=True)
        if run().returncode != 0:
            return {"status": "baseline_failing", "note": "Tests do not pass on the original code in this environment."}
        f = os.path.join(d, path)
        lines = open(f, encoding="utf-8").read().splitlines(True)
        open(f, "w", encoding="utf-8").write("".join(lines[:s - 1] + lines[e:]))
        r = run()
        subprocess.run(["git", "checkout", "-q", "--", path], cwd=d)
        return {"status": "broke" if r.returncode else "no_effect", "output": (r.stdout + r.stderr)[-1200:]}
    except Exception as ex:
        return {"status": "error", "note": str(ex)[:200]}
