import json, os, subprocess, sys, tempfile
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
def run(args, env=None):
    e = dict(os.environ); e.update(env or {})
    return subprocess.run([sys.executable,"-m","dashboard_adapter.publish_latest",*args],
                          cwd=REPO, env=e, capture_output=True, text=True)
def main():
    tmp = Path(tempfile.mkdtemp()); fails=[]
    good = tmp/"good.json"; good.write_text(json.dumps(
        {"pipelineStatus":"ok","businessDate":"2026-07-15","runId":"r","sections":[]}))
    bad = tmp/"bad.json"; bad.write_text(json.dumps(
        {"pipelineStatus":"failed","businessDate":"2026-07-15","runId":"r"}))
    dst = tmp/"pub"/"latest.json"
    # 1 good local publish
    r = run(["--mode","local","--src",str(good),"--dst",str(dst)])
    if r.returncode!=0 or not dst.is_file(): fails.append("good local publish")
    # 2 second publish makes .bak
    run(["--mode","local","--src",str(good),"--dst",str(dst)])
    if not dst.with_suffix(".json.bak").is_file(): fails.append("backup not created")
    # 3 failed payload refused
    r = run(["--mode","local","--src",str(bad),"--dst",str(dst)])
    if r.returncode!=2: fails.append("failed payload not refused")
    # 4 hosted without internal refused
    r = run(["--mode","hosted","--src",str(good)],
            {"IGS_PUBLISH_ENDPOINT":"https://x","IGS_PUBLISH_AUTH_TOKEN":"t"})
    if r.returncode!=2: fails.append("hosted non-internal not refused")
    # 5 VITE_ auth refused
    r = run(["--mode","hosted","--src",str(good)],
            {"VITE_PUBLISH_AUTH_TOKEN":"t","IGS_PUBLISH_ENDPOINT":"https://x",
             "IGS_PUBLISH_AUTH_TOKEN":"t","IGS_PUBLISH_ENDPOINT_INTERNAL":"1",
             "IGS_PUBLISH_ALLOW_SENSITIVE":"1"})
    if r.returncode!=2: fails.append("VITE_ auth not refused")
    # 6 rollback
    r = run(["--rollback","--dst",str(dst)])
    if r.returncode!=0: fails.append("rollback failed")
    print("FAILURES:", fails if fails else "NONE - 6/6 PASS")
    return 1 if fails else 0
if __name__=="__main__": raise SystemExit(main())
