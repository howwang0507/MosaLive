import os,sys,subprocess,time,json,urllib.request,shutil,webbrowser,socket
from pathlib import Path
root=Path(__file__).resolve().parents[1]
os.chdir(root)
# Reopening the launcher should reuse this application's existing service.
try:
    with urllib.request.urlopen('http://127.0.0.1:8787/health',timeout=3) as response:
        existing=json.load(response)
    if existing.get('app')=='mosasub-live-local':
        print('MosaSub is already running.' if existing.get('ready') else 'MosaSub is running; models are not ready yet.',flush=True)
        if os.environ.get('MOSA_NO_BROWSER')!='1':webbrowser.open('http://localhost:8787')
        sys.exit(0)
except (OSError,ValueError):pass
for port in (8787,8790):
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1',port))==0:sys.exit(f'Port {port} busy. Close the previous MosaSub window first.')
# The desktop app passes its bundled Node (Electron with ELECTRON_RUN_AS_NODE=1) via MOSA_NODE.
node=os.environ.get('MOSA_NODE') or shutil.which('node')
if not node:sys.exit('Install Node.js 22+ and reopen this window.')
if int(subprocess.check_output([node,'-p','process.versions.node.split(".")[0]'],text=True).strip())<22:sys.exit('Node.js 22+ required.')
env=dict(os.environ,ASR_URL='http://127.0.0.1:8790/v1/audio/transcriptions',TRANSLATION_URL='http://127.0.0.1:8790/v1/chat/completions',LOCAL_MODELS='1',PORT='8787',PYTHONIOENCODING='utf-8')
# NVIDIA wheels in this interpreter's environment contain the required Windows DLLs.
dll_dirs=[Path(sys.prefix)/'Lib/site-packages/nvidia'/name/'bin' for name in ('cublas','cudnn')]
env['PATH']=os.pathsep.join([str(p) for p in dll_dirs if p.is_dir()]+[env.get('PATH','')])
# Lower-VRAM Ollama defaults so the translator stays fully on an 8 GB GPU.
# They apply only when this launcher starts Ollama; an already running Ollama keeps its own settings.
OLLAMA_SPEED={'OLLAMA_FLASH_ATTENTION':'1','OLLAMA_KV_CACHE_TYPE':'q8_0','OLLAMA_NUM_PARALLEL':'1','OLLAMA_MAX_LOADED_MODELS':'1'}
# Faster-Whisper aliases that may already be on disk. Nothing is downloaded: the project
# cache (.models/windows) and the user's Hugging Face cache are searched, and a missing
# model falls back to small with a clear message.
LOCAL_ASR_REPOS={'large-v3-turbo':'mobiuslabsgmbh/faster-whisper-large-v3-turbo'}
def resolve_asr(env,root=root,home=Path.home()):
    name=env.get('MOSA_ASR_MODEL','small')
    repo=LOCAL_ASR_REPOS.get(name)
    if not repo:return env
    folder='models--'+repo.replace('/','--')
    hub=env.get('HF_HUB_CACHE') or (str(Path(env['HF_HOME'])/'hub') if env.get('HF_HOME') else str(home/'.cache/huggingface/hub'))
    for base in (root/'.models/windows',Path(hub)):
        snapshots=sorted((base/folder/'snapshots').glob('*/model.bin'),key=lambda p:p.stat().st_mtime,reverse=True)
        if snapshots:
            env['MOSA_ASR_MODEL']=str(snapshots[0].parent);env.setdefault('MOSA_ASR_LABEL',name)
            print(f'ASR model: {name} ({snapshots[0].parent})',flush=True)
            return env
    print(f'ASR model {name} is not on this computer; using small instead. No model was downloaded.',flush=True)
    env['MOSA_ASR_MODEL']='small';env['MOSA_ASR_LABEL']='small (fallback: '+name+' not found)'
    return env

children=[]
try:
    if env.get('MOSA_NMT_ENGINE','ollama')=='ollama':
        try:
            with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=2) as response:available=json.load(response)
            if any(key not in os.environ for key in OLLAMA_SPEED):
                print('Ollama was already running, so its own VRAM settings apply. Run SET_OLLAMA_SPEED.bat once and restart Ollama for faster translation.',flush=True)
        except Exception:
            ollama=shutil.which('ollama')
            if not ollama:raise RuntimeError('Ollama is unavailable. Start or install Ollama before MosaSub.')
            # Ollama is shared infrastructure: leave it running when MosaSub exits.
            subprocess.Popen([ollama,'serve'],env=dict(os.environ,**{k:os.environ.get(k,v) for k,v in OLLAMA_SPEED.items()}),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            available=None
            for attempt in range(10):
                time.sleep(1)
                try:
                    with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=1) as response:available=json.load(response)
                    break
                except Exception:pass
            if available is None:raise RuntimeError('Ollama did not become available. Check its service before retrying.')
        selected=env.get('MOSA_NMT_MODEL','gemma3:4b')
        names={item.get('name') for item in available.get('models',[])}
        if selected not in names and selected+':latest' not in names:
            raise RuntimeError('Configured translation model is not installed: '+selected+'. No model was downloaded.')
    env=resolve_asr(env)
    children.append(subprocess.Popen([sys.executable,'-u','windows/models.py'],env=env))
    children.append(subprocess.Popen([node,'server.mjs'],env=env))
    opened=False
    commands=[[sys.executable,'-u','windows/models.py'],[node,'server.mjs']]
    retries=[0,0];restart_at=[0,0];started_at=[time.monotonic(),time.monotonic()]
    while True:
        now=time.monotonic()
        for i,child in enumerate(children):
            if child.poll() is None and now-started_at[i]>=300:retries[i]=0
            if child.poll() is not None:
                if not restart_at[i]:
                    if retries[i]>=5:raise RuntimeError('Service repeatedly failed. Check Ollama, model settings and available memory before restarting MosaSub.')
                    retries[i]+=1;restart_at[i]=now+min(8,2**min(retries[i]-1,3))
                    print(time.strftime('%Y-%m-%d %H:%M:%S')+f' {("models", "bridge")[i]} exited: code={child.returncode}, uptime={now-started_at[i]:.0f}s; restart attempt={retries[i]}.',flush=True)
                if now>=restart_at[i]:
                    children[i]=subprocess.Popen(commands[i],env=env);restart_at[i]=0;started_at[i]=now
        status={}
        try:
            with urllib.request.urlopen('http://127.0.0.1:8790/health',timeout=2) as r:status=json.load(r)
        except Exception:pass
        if status.get('error') and children[0].poll() is None:
            print('Models unavailable; retrying startup: '+status['error'],flush=True)
            children[0].terminate();children[0].wait(timeout=10)
        if status.get('ready') and not opened:
            print('READY: http://localhost:8787 - keep this window open',flush=True)
            if env.get('MOSA_NO_BROWSER')!='1':webbrowser.open('http://localhost:8787')
            opened=True
        time.sleep(2)
except KeyboardInterrupt:pass
except Exception as error:print('Startup stopped: '+str(error),flush=True)
finally:
    for c in children:
        if c.poll() is None:c.terminate()
    for c in children:
        try:c.wait(timeout=10)
        except subprocess.TimeoutExpired:c.kill()
