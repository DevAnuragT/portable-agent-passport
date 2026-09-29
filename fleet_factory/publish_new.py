#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; FLEET=ROOT/'passport-fleet'; OWNER='DevAnuragT'
def run(*args,cwd=None,check=True): return subprocess.run(args,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=check).stdout.strip()
def publish(root,m):
    slug=m['slug']; repo=f'agent-{slug}'; full=f'{OWNER}/{repo}'
    if not (root/'.git').exists():
        run('git','init','-b','main',cwd=root); run('git','add','.',cwd=root); run('git','-c','user.name=Anurag Thakur','-c','user.email=anuragthakur2102@gmail.com','commit','-m','feat: add evidence-driven portable agent',cwd=root)
    view=run('gh','repo','view',full,'--json','url,isPrivate',check=False)
    if '"url"' not in view:
        out=run('gh','repo','create',full,'--public','--source',str(root),'--remote','origin','--description',m['title'],check=False)
        if 'failed' in out.lower() or 'error' in out.lower(): raise RuntimeError(out)
        time.sleep(2)
    else:
        rem=run('git','remote','get-url','origin',cwd=root,check=False)
        if not rem: run('git','remote','add','origin',f'https://github.com/{full}.git',cwd=root)
    push=run('git','push','-u','origin','main',cwd=root,check=False)
    if 'fatal:' in push.lower() or 'error:' in push.lower(): raise RuntimeError(push)
    return {'slug':slug,'repo':full,'url':f'https://github.com/{full}','title':m['title']}
def main():
    published=[]; failed=[]
    for root in sorted(FLEET.iterdir()):
        meta=root/'metadata.json'
        if not root.is_dir() or not meta.exists(): continue
        m=json.loads(meta.read_text())
        try:
            item=publish(root,m); published.append(item); print('published',item['repo'])
        except Exception as exc:
            failed.append({'slug':m['slug'],'error':str(exc)}); print('FAILED',m['slug'],exc)
    (ROOT/'fleet_factory'/'second_batch_published.json').write_text(json.dumps(published,indent=2)+'\n')
    (ROOT/'fleet_factory'/'second_batch_publish_failures.json').write_text(json.dumps(failed,indent=2)+'\n')
    print('published total',len(published),'failed',len(failed))
if __name__=='__main__': main()
