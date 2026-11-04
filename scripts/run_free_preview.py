"""One-command, private synthetic QWOMS preview. No office/Docker/paid editor needed."""
import os,subprocess,sys,time
from pathlib import Path
import httpx
root=Path(__file__).resolve().parent.parent
os.chdir(root)
os.environ['PYTHONPATH']=str(root)
try:
    httpx.get('http://127.0.0.1:8020/readyz',timeout=1)
except httpx.ConnectError:pass
except httpx.HTTPError:raise SystemExit('Cannot verify that local port8020 is free; keep the existing preview unchanged')
else:raise SystemExit('Port8020 already has a running service; open the existing preview instead')
server=subprocess.Popen([sys.executable,'scripts/run_excel_review.py','--engine','free'])
try:
    for _ in range(120):
        if server.poll() is not None:raise SystemExit('Synthetic preview server did not start')
        try:
            if httpx.get('http://127.0.0.1:8020/readyz',timeout=1).status_code==200:break
        except httpx.HTTPError:pass
        time.sleep(.25)
    else:raise SystemExit('Synthetic preview readiness timed out')
    if not (root/'work/excel-editor/workspace-fixture.json').exists():
        subprocess.run([sys.executable,'tests/browser/seed_workspace.py'],check=True)
    print('Open private forwarded port 8020. Review credentials: work/excel-editor/reviewer.credentials (never share its values).',flush=True)
    print('Quality workspace: /#work-order-2 · source originals and completed copies use isolated synthetic storage.',flush=True)
    server.wait()
except KeyboardInterrupt:pass
finally:
    if server.poll() is None:
        server.terminate()
        try:server.wait(timeout=10)
        except subprocess.TimeoutExpired:server.kill()
