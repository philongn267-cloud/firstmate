import os, pathlib, subprocess, time, json
root=pathlib.Path.cwd(); tmp=root/'.test-bounded-live'; ev=pathlib.Path('/Users/longnguyen/.no-mistakes/evidence/01M3ZN0S1Q3YZYV0921FM7STQB')
env=os.environ.copy()
for k in list(env):
    if k.startswith(('FM_', 'TASKS_AXI_')): env.pop(k)
env['TMPDIR']=str(tmp); env['TASKS_AXI_BACKEND']='markdown'
records=[]
def run(name,cmd,expected=0,extra=None):
    t=time.monotonic(); p=subprocess.run(cmd,cwd=root,env={**env,**(extra or {})},text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
    rec={'scenario':name,'command':cmd,'exit_status':p.returncode,'elapsed_seconds':round(time.monotonic()-t,3),'output':p.stdout}
    records.append(rec); print(json.dumps(rec),flush=True)
    assert p.returncode==expected,(name,p.returncode,p.stdout)
    return p.stdout
run('Host Bash has no BASHPID',['/bin/bash','-uc','printf "Bash=%s BASHPID=%s\\n" "$BASH_VERSION" "${BASHPID-unavailable}"'])
base=subprocess.check_output(['git','show','d719ef3d9abdd11b0a8aea57c74de074feca99b9:bin/fm-timeout-lib.sh'],text=True)
(tmp/'base-timeout.sh').write_text(base)
code='set -u; . "$1"; fm_exec_timed 5 1 /bin/bash -c "echo bounded-under-legacy-bash; exit 7"'
out=run('Before fix: bounded command aborts before launch',['/bin/bash','-c',code,'_',str(tmp/'base-timeout.sh')],127)
assert 'BASHPID: unbound variable' in out
out=run('After fix: stdout and status pass through',['/bin/bash','-c',code,'_',str(root/'bin/fm-timeout-lib.sh')],7)
assert out.strip()=='bounded-under-legacy-bash'
# Execute the existing regression and compatible targeted behavior cases in isolation,
# avoiding previously declined BASHPID assumptions in unrelated suite cases.
src=(root/'tests/fm-timeout-lib.test.sh').read_text().split('\ntest_passes_the_command_status_and_output_through\n')[0]
src=src.replace('. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"','. "'+str(root/'tests/lib.sh')+'"')
cases=['test_bounds_a_command_under_a_bash_without_basphpid','test_passes_the_command_status_and_output_through','test_term_ends_a_cooperative_command_at_the_bound','test_kill_ends_a_term_ignoring_command_after_the_grace','test_a_descendant_holding_the_output_cannot_outlast_the_bound','test_rejects_malformed_bounds_before_running_anything','test_refuses_rather_than_running_unbounded']
(tmp/'selected-tests.sh').write_text(src+'\n'+'\n'.join(cases)+'\n')
run('Existing regression and targeted bounds behavior',['/bin/bash',str(tmp/'selected-tests.sh')])
home=tmp/'home'
for part in ['data','state','config']: (home/part).mkdir(parents=True,exist_ok=True)
(home/'.tasks.toml').write_text((root/'.tasks.toml').read_text())
fixture={'FM_HOME':str(home),'FM_DATA_OVERRIDE':str(home/'data')}
run('Create isolated queued backlog item',['/bin/bash','bin/fm-tasks-axi.sh','add','legacy-live','Legacy bash bounded dispatch','--kind','ship'],extra=fixture)
run('Show queued item',['/bin/bash','bin/fm-tasks-axi.sh','show','legacy-live'],extra=fixture)
(home/'state/legacy-live.meta').write_text('kind=ship\nspawn_gen=legacy-live-proof\n')
transition='''set -u
. "$1/bin/fm-tasks-axi-lib.sh"
. "$1/bin/fm-backlog-transition-lib.sh"
FM_TASKS_AXI_TIMEOUT=5
fm_backlog_atomic_transition dispatch "$2/state/legacy-live.meta" "$2/data" legacy-live "$2/state" || { printf 'transition error: %s\\n' "$FM_BACKLOG_TRANSITION_ERROR"; exit 1; }
fm_backlog_row_probe "$2/data" legacy-live || exit 2
printf 'row after bounded dispatch: %s\\n' "$FM_BACKLOG_ROW_STATE"
[ "$FM_BACKLOG_ROW_STATE" = 'in_flight no no' ]
'''
run('Real bounded dispatch transaction on Bash 3.2',['/bin/bash','-c',transition,'_',str(root),str(home)],extra=fixture)
run('Persisted item now In flight',['/bin/bash','bin/fm-tasks-axi.sh','show','legacy-live'],extra=fixture)
(ev/'bounded-live-transcript.json').write_text(json.dumps(records,indent=2)+'\n')
(ev/'bounded-live-driver.py').write_text(pathlib.Path(__file__).read_text())
print('All live checks completed; evidence saved.',flush=True)
