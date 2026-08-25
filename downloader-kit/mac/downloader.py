# -*- coding: utf-8 -*-
"""
影片下載器 v1.2（工具包通用版 Windows / macOS）
雙擊「start.bat」使用。貼上 FB / IG / TikTok / YouTube 影片網址即可下載。
v1.1：下載完可自動接「產逐字稿」（transcribe.py）與「轉H264」，貼完連結就能去忙別的。
v2  ：工具包自帶 Python（runtime\\ 或 bin/），不吃系統環境；ffmpeg 也在裡面。
v1.2：存檔位置可以自己換——網頁上按「換資料夾」用點的選（含開新資料夾），
      選過的會記住，下次打開還是同一個；另有「快速切換」與「開啟資料夾」。
"""
import os, sys, json, re, threading, subprocess, webbrowser, time, string
import urllib.request
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8765
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(SCRIPT_DIR, 'settings.json')

JOBS = []          # [{url, status, msg, file, outdir}]
LOCK = threading.Lock()
WORKING = False
WARN = ''          # 存檔位置有問題時顯示在網頁上的紅字（絕不偷偷改存到別的地方）


# ---------- 存檔位置 ----------

def desktop_dir():
    home = os.path.expanduser('~')
    for d in [os.path.join(home, 'Desktop'), os.path.join(home, 'OneDrive', 'Desktop'),
              os.path.join(home, 'OneDrive', '桌面')]:
        if os.path.isdir(d):
            return d
    return home


def default_outdir():
    out = os.path.join(desktop_dir(), '影片下載')
    try:
        os.makedirs(out, exist_ok=True)
    except Exception:
        pass
    return out


def norm(p):
    p = (p or '').strip().strip('"').strip("'")
    if not p:
        return ''
    return os.path.abspath(os.path.expanduser(p))


def check_dir(p):
    """能不能真的存檔到這裡。回 (True, '') 或 (False, 原因)。會實際試寫一個小檔再刪掉。"""
    if not p:
        return False, '沒有指定資料夾'
    try:
        os.makedirs(p, exist_ok=True)
    except Exception as e:
        return False, '建不出這個資料夾（' + str(e)[:70] + '）'
    if not os.path.isdir(p):
        return False, '這個路徑不是資料夾'
    t = os.path.join(p, '.downloader_write_test')
    try:
        with open(t, 'w', encoding='utf-8') as f:
            f.write('ok')
        os.remove(t)
    except Exception as e:
        return False, '這個資料夾沒辦法寫入（' + str(e)[:70] + '）'
    return True, ''


def load_settings():
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            s = json.load(f)
        return s if isinstance(s, dict) else {}
    except Exception:
        return {}


def save_settings():
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'outdir': OUTDIR, 'recent': RECENT}, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def push_recent(p):
    global RECENT
    low = p.lower()
    RECENT = [p] + [r for r in RECENT if r.lower() != low]
    RECENT = RECENT[:6]


DEFAULT_OUTDIR = default_outdir()
_s = load_settings()
RECENT = [r for r in _s.get('recent', []) if isinstance(r, str)][:6]
OUTDIR = norm(_s.get('outdir')) or DEFAULT_OUTDIR
_ok, _err = check_dir(OUTDIR)
if not _ok:
    # 存過的位置現在不能用（外接硬碟沒插、資料夾被搬走…）→ 明白講出來，不偷偷改存到桌面
    WARN = '現在的存檔位置「' + OUTDIR + '」不能用：' + _err + '。請按「換資料夾」重新選一個。'
push_recent(OUTDIR)


def quick_links():
    home = os.path.expanduser('~')
    cand = [('桌面', desktop_dir()),
            ('預設的影片下載', DEFAULT_OUTDIR),
            ('下載', os.path.join(home, 'Downloads')),
            ('文件', os.path.join(home, 'Documents')),
            ('影片', os.path.join(home, 'Movies') if sys.platform == 'darwin' else os.path.join(home, 'Videos'))]
    out, seen = [], set()
    for name, p in cand:
        if p and os.path.isdir(p) and p.lower() not in seen:
            seen.add(p.lower())
            out.append({'name': name, 'path': p})
    return out


def list_drives():
    if os.name != 'nt':
        return [os.path.expanduser('~'), '/']
    out = []
    for c in string.ascii_uppercase:
        d = c + ':\\'
        if os.path.exists(d):
            out.append(d)
    return out


def list_subdirs(p):
    """列出資料夾底下的子資料夾（跳過系統的、看不到的、沒權限的）"""
    dirs = []
    try:
        with os.scandir(p) as it:
            for e in it:
                if len(dirs) >= 500:
                    break
                name = e.name
                if name.startswith('.') or name.startswith('$') or name == 'System Volume Information':
                    continue
                try:
                    if e.is_dir():
                        dirs.append({'name': name, 'path': os.path.join(p, name)})
                except Exception:
                    continue
    except Exception as e:
        return None, str(e)[:80]
    dirs.sort(key=lambda d: d['name'].lower())
    return dirs, ''


# ---------- 下載 ----------

def extract_urls(text):
    urls = re.findall(r'https?://[^\s"\'<>，、]+', text)
    seen, out = set(), []
    for u in urls:
        u = u.rstrip('.,;)')
        if u not in seen:
            seen.add(u); out.append(u)
    return out


def run_transcribe(filepath):
    """下載完自動產逐字稿：先找存檔資料夾、再找工具包資料夾、最後找預設的「影片下載」"""
    script = None
    for d in [os.path.dirname(filepath), OUTDIR, SCRIPT_DIR, DEFAULT_OUTDIR]:
        cand = os.path.join(d, 'transcribe.py')
        if os.path.isfile(cand):
            script = cand; break
    if not script:
        return False, '找不到 transcribe.py（請確認它還在工具包資料夾裡）'
    p = subprocess.run([sys.executable, script, filepath],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1800)
    base = os.path.splitext(os.path.basename(filepath))[0]
    txt = os.path.join(os.path.dirname(filepath), base + '_逐字稿.txt')
    if os.path.isfile(txt):
        return True, os.path.basename(txt)
    err = (p.stdout or '').strip().splitlines()
    return False, ('逐字稿失敗：' + err[-1][:100] if err else '逐字稿失敗')


def run_convert(filepath):
    """下載完自動轉 H264：跟 convert-h264.ps1 同一組 ffmpeg 參數，存進「轉好H264」"""
    outdir = os.path.join(os.path.dirname(filepath), '轉好H264')
    os.makedirs(outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(filepath))[0]
    outfile = os.path.join(outdir, base + '.mp4')
    if os.path.isfile(outfile):
        return True, '轉好H264 / ' + os.path.basename(outfile)
    p = subprocess.run(['ffmpeg', '-y', '-i', filepath,
                        '-c:v', 'libx264', '-crf', '20', '-preset', 'medium',
                        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', outfile],
                       capture_output=True, timeout=1800)
    if p.returncode == 0 and os.path.isfile(outfile):
        return True, '轉好H264 / ' + os.path.basename(outfile)
    return False, '轉檔失敗（可能缺 ffmpeg）'


def run_download(job):
    url = job['url']
    outdir = job.get('outdir') or OUTDIR   # 存檔位置在「按下載那一刻」就定好，之後換資料夾不影響排隊中的
    with LOCK:
        job['status'] = 'downloading'; job['msg'] = '下載中…'
    ok, err = check_dir(outdir)
    if not ok:
        with LOCK:
            job['status'] = 'error'; job['msg'] = '存檔位置有問題：' + err
        return
    before = set(os.listdir(outdir))
    # 用 truststore 走系統憑證庫，避開部分機器 python SSL 憑證驗證失敗的老毛病
    boot = ('import sys;'
            'import truststore; truststore.inject_into_ssl();'
            'from yt_dlp import main; main(sys.argv[1:])')
    cmd = [sys.executable, '-c', boot,
           '-o', os.path.join(outdir, '%(id)s.%(ext)s'),
           '--no-playlist', '--restrict-filenames',
           '--merge-output-format', 'mp4',
           url]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
        new_files = [f for f in (set(os.listdir(outdir)) - before) if not f.endswith(('.part', '.ytdl'))]
        if p.returncode == 0:
            fname = new_files[0] if new_files else ''
            if not fname:
                # 之前下載過的話 yt-dlp 會直接跳過，資料夾不會多出新檔案，
                # 從它的輸出把檔名撈回來，才不會顯示「完成 →（空白）」讓人以為壞了
                m = re.search(r'\[download\] (.+?) has already been downloaded',
                              (p.stdout or '') + (p.stderr or ''))
                if m:
                    cand = os.path.basename(m.group(1).strip())
                    if os.path.isfile(os.path.join(outdir, cand)):
                        fname = cand
            filepath = os.path.join(outdir, fname) if fname else ''
            with LOCK:
                job['status'] = 'done'
                job['file'] = fname
                job['msg'] = ('完成 → ' + fname) if fname else '完成（這支之前就下載過了）'
            extras = []
            if filepath and job.get('transcribe'):
                with LOCK:
                    job['status'] = 'transcribing'; job['msg'] = '影片好了，產逐字稿中…'
                ok, msg = run_transcribe(filepath)
                extras.append(('逐字稿 ✔ ' + msg) if ok else ('逐字稿 ✘ ' + msg))
            if filepath and job.get('convert'):
                with LOCK:
                    job['status'] = 'converting'; job['msg'] = '轉H264中…'
                ok, msg = run_convert(filepath)
                extras.append(('H264 ✔ ' + msg) if ok else ('H264 ✘ ' + msg))
            with LOCK:
                job['status'] = 'done'
                job['msg'] = (('完成 → ' + fname) if fname else '完成（這支之前就下載過了）') \
                             + (('　｜　' + '　'.join(extras)) if extras else '')
        else:
            err = (p.stderr or '').strip().splitlines()
            last = err[-1] if err else '未知錯誤'
            if 'login' in last.lower() or 'cookies' in last.lower() or 'private' in last.lower():
                last = '這支影片需要登入或是私人影片，抓不到（公開影片才能下載）'
            with LOCK:
                job['status'] = 'error'; job['msg'] = last[:160]
    except subprocess.TimeoutExpired:
        with LOCK:
            job['status'] = 'error'; job['msg'] = '下載逾時（超過10分鐘），請重試'
    except Exception as e:
        with LOCK:
            job['status'] = 'error'; job['msg'] = str(e)[:160]


def worker():
    global WORKING
    while True:
        job = None
        with LOCK:
            for j in JOBS:
                if j['status'] == 'queued':
                    job = j; break
            WORKING = job is not None
        if job is None:
            time.sleep(0.5); continue
        run_download(job)


HTML = """<!DOCTYPE html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>影片下載器</title>
<style>
  body{font-family:"Microsoft JhengHei","PingFang TC",sans-serif;background:#f5f7f5;margin:0;padding:24px;color:#222}
  .box{max-width:760px;margin:0 auto;background:#fff;border-radius:14px;padding:28px;box-shadow:0 2px 12px rgba(0,0,0,.08)}
  h1{font-size:22px;margin:0 0 4px}
  .sub{color:#777;font-size:13px;margin-bottom:16px}
  textarea{width:100%;height:130px;box-sizing:border-box;font-size:14px;padding:12px;border:2px solid #cfd8cf;border-radius:10px;resize:vertical}
  button{margin-top:12px;width:100%;padding:14px;font-size:17px;font-weight:bold;color:#fff;background:#2e7d32;border:0;border-radius:10px;cursor:pointer}
  button:disabled{background:#9e9e9e}
  .job{display:flex;gap:10px;align-items:flex-start;padding:10px 4px;border-bottom:1px solid #eee;font-size:13px}
  .st{flex:0 0 64px;text-align:center;border-radius:6px;padding:3px 0;font-weight:bold}
  .queued{background:#eceff1;color:#607d8b}.downloading{background:#fff3e0;color:#ef6c00}
  .transcribing{background:#e3f2fd;color:#1565c0}.converting{background:#ede7f6;color:#5e35b1}
  .done{background:#e8f5e9;color:#2e7d32}.error{background:#ffebee;color:#c62828}
  .opts{margin-top:10px;font-size:14px;color:#444;display:flex;gap:22px;flex-wrap:wrap}
  .opts label{cursor:pointer;user-select:none}
  .opts input{transform:scale(1.3);margin-right:6px;vertical-align:middle}
  .u{word-break:break-all;color:#555;flex:1}
  .m{color:#333}
  .jd{color:#8d6e63;font-size:12px;margin-top:2px}
  code{background:#f0f0f0;padding:2px 6px;border-radius:4px;word-break:break-all}
  .dirbox{margin-top:16px;background:#f7f9f7;border:1px solid #e0e6e0;border-radius:10px;padding:12px 14px;font-size:13px;color:#555}
  .dirrow{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  .dirrow .lbl{color:#666;flex:0 0 auto}
  .dirrow code{flex:1;min-width:200px}
  .mini{margin:0;width:auto;padding:7px 12px;font-size:13px;font-weight:normal;border-radius:8px}
  .ghost{background:#fff;color:#2e7d32;border:1px solid #a5c8a7}
  .recent{margin-top:8px;display:flex;gap:6px;flex-wrap:wrap;align-items:center}
  .chip{background:#fff;border:1px solid #cfd8cf;border-radius:20px;padding:4px 11px;font-size:12px;cursor:pointer;color:#444}
  .chip:hover{border-color:#2e7d32;color:#2e7d32}
  .warn{margin-top:10px;background:#ffebee;border:1px solid #ef9a9a;color:#c62828;border-radius:8px;padding:9px 12px;font-size:13px;display:none}
  .mask{position:fixed;inset:0;background:rgba(0,0,0,.45);display:none;align-items:center;justify-content:center;padding:16px;z-index:9}
  .modal{background:#fff;border-radius:14px;width:100%;max-width:560px;padding:20px;box-sizing:border-box}
  .modal h2{font-size:17px;margin:0 0 10px}
  .pathbar{display:flex;gap:6px;margin-bottom:8px}
  .pathbar input{flex:1;font-size:13px;padding:8px 10px;border:1px solid #cfd8cf;border-radius:8px}
  .drives{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}
  .flist{border:1px solid #e0e6e0;border-radius:8px;height:260px;overflow:auto;background:#fafcfa}
  .fitem{padding:9px 12px;font-size:13px;cursor:pointer;border-bottom:1px solid #eef2ee}
  .fitem:hover{background:#e8f5e9}
  .mkrow{display:flex;gap:6px;margin-top:10px}
  .mkrow input{flex:1;font-size:13px;padding:8px 10px;border:1px solid #cfd8cf;border-radius:8px}
  .btns{display:flex;gap:8px;margin-top:12px}
  .btns button{flex:1;margin-top:0;padding:12px}
  .err{color:#c62828;font-size:12px;margin-top:6px;min-height:16px}
</style></head><body>
<div class="box">
  <h1>🎬 影片下載器</h1>
  <div class="sub">FB / IG / TikTok / YouTube 公開影片網址貼進來，一行一個或整坨貼都可以</div>
  <textarea id="urls" placeholder="https://www.facebook.com/reel/xxxx
https://www.instagram.com/reel/xxxx
https://www.tiktok.com/@xxx/video/xxxx"></textarea>
  <div class="opts">
    <label><input type="checkbox" id="opt_ts" checked> 下載完自動產逐字稿</label>
    <label><input type="checkbox" id="opt_cv"> 順便轉H264（要拿去剪的才勾）</label>
  </div>
  <button id="go" onclick="go()">下載</button>

  <div class="dirbox">
    <div class="dirrow">
      <span class="lbl">存檔位置：</span>
      <code id="dir">讀取中…</code>
      <button class="mini" onclick="openPicker()">換資料夾</button>
      <button class="mini ghost" onclick="openFolder()">開啟資料夾</button>
    </div>
    <div class="recent" id="recent"></div>
  </div>
  <div class="warn" id="warn"></div>
  <div id="list"></div>
</div>

<div class="mask" id="mask">
  <div class="modal">
    <h2>選一個存檔資料夾</h2>
    <div class="pathbar">
      <button class="mini ghost" style="flex:0 0 auto" onclick="up()">⬆ 上一層</button>
      <input id="pathin" onkeydown="if(event.key==='Enter')browse(this.value)">
      <button class="mini ghost" style="flex:0 0 auto" onclick="browse(document.getElementById('pathin').value)">前往</button>
    </div>
    <div class="drives" id="drives"></div>
    <div class="flist" id="flist"></div>
    <div class="mkrow">
      <input id="newname" placeholder="要在這裡開一個新資料夾就打名字">
      <button class="mini ghost" style="flex:0 0 auto" onclick="mk()">＋ 建立</button>
    </div>
    <div class="err" id="perr"></div>
    <div class="btns">
      <button onclick="pick()">就存這裡</button>
      <button style="background:#eceff1;color:#546e7a" onclick="closePicker()">取消</button>
    </div>
  </div>
</div>

<script>
let CURDIR = '', BROWSE = '';
function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
async function go(){
  const t = document.getElementById('urls').value.trim();
  if(!t) return;
  document.getElementById('go').disabled = true;
  const r = await fetch('/download',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({text:t,
      transcribe:document.getElementById('opt_ts').checked,
      convert:document.getElementById('opt_cv').checked})});
  const js = await r.json();
  document.getElementById('go').disabled = false;
  if(js.err){ alert(js.err); return; }
  document.getElementById('urls').value='';
}
function openFolder(){ fetch('/open',{method:'POST'}); }
function openPicker(){ document.getElementById('mask').style.display='flex'; browse(CURDIR); }
function closePicker(){ document.getElementById('mask').style.display='none'; }
function up(){ if(BROWSE) browse(BROWSE + '/..'); }
async function browse(p){
  const r = await fetch('/browse?path=' + encodeURIComponent(p||''));
  const js = await r.json();
  BROWSE = js.path;
  document.getElementById('pathin').value = js.path;
  document.getElementById('perr').textContent = js.err || '';
  document.getElementById('drives').innerHTML = js.drives.map(d=>
    '<span class="chip" data-p="' + esc(d) + '" onclick="browse(this.dataset.p)">' + esc(d) + '</span>').join('');
  const f = document.getElementById('flist');
  f.innerHTML = js.dirs.length
    ? js.dirs.map(d=>'<div class="fitem" data-p="' + esc(d.path) + '" onclick="browse(this.dataset.p)">📁 ' + esc(d.name) + '</div>').join('')
    : '<div class="fitem" style="color:#999;cursor:default">（這裡面沒有子資料夾，可以直接按「就存這裡」）</div>';
  f.scrollTop = 0;
}
async function mk(){
  const n = document.getElementById('newname').value.trim();
  if(!n) return;
  const r = await fetch('/mkdir',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({path:BROWSE, name:n})});
  const js = await r.json();
  if(!js.ok){ document.getElementById('perr').textContent = js.err; return; }
  document.getElementById('newname').value='';
  browse(js.path);
}
async function pick(){
  const p = document.getElementById('pathin').value.trim() || BROWSE;
  const r = await fetch('/setdir',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({path:p})});
  const js = await r.json();
  if(!js.ok){ document.getElementById('perr').textContent = js.err; return; }
  closePicker();
}
async function quick(p){
  const r = await fetch('/setdir',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:p})});
  const js = await r.json();
  if(!js.ok) alert(js.err);
}
const names={queued:'排隊中',downloading:'下載中',transcribing:'逐字稿',converting:'轉檔中',done:'完成',error:'失敗'};
async function poll(){
  try{
    const r = await fetch('/status'); const js = await r.json();
    CURDIR = js.dir;
    document.getElementById('dir').textContent = js.dir;
    const w = document.getElementById('warn');
    if(js.warn){ w.style.display='block'; w.textContent = '⚠️ ' + js.warn; } else { w.style.display='none'; }
    const items = (js.quick||[]).slice()
      .concat((js.recent||[]).map(p=>({name:p.split(/[\\/]/).filter(Boolean).pop()||p, path:p})));
    const seen = new Set([js.dir.toLowerCase()]);
    const chips = items.filter(i=>{
        const k=i.path.toLowerCase(); if(seen.has(k)) return false; seen.add(k); return true;
      }).map(i=>'<span class="chip" title="' + esc(i.path) + '" data-p="' + esc(i.path) + '" onclick="quick(this.dataset.p)">' + esc(i.name) + '</span>').join('');
    document.getElementById('recent').innerHTML =
      '<span style="color:#888;font-size:12px">快速切換：</span>' + (chips || '<span style="color:#aaa;font-size:12px">（還沒有其他資料夾）</span>');
    document.getElementById('list').innerHTML = js.jobs.map(j=>
      '<div class="job"><div class="st ' + j.status + '">' + names[j.status] + '</div>' +
      '<div class="u">' + esc(j.url) + '<div class="m">' + esc(j.msg||'') + '</div>' +
      ((j.dir && j.dir.toLowerCase()!==js.dir.toLowerCase()) ? '<div class="jd">📁 存到：' + esc(j.dir) + '</div>' : '') +
      '</div></div>').join('');
  }catch(e){}
  setTimeout(poll, 1200);
}
poll();
</script></body></html>"""


class Server(HTTPServer):
    # Windows 上預設的 SO_REUSEADDR 會讓兩個下載器綁同一個 port 互搶、不報錯，關掉它
    allow_reuse_address = False


def already_running():
    """啟動前先敲門：8765 上是不是已經有一個下載器在跑"""
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d/status' % PORT, timeout=2) as r:
            return r.read(1) == b'{'
    except Exception:
        return False


def open_page(url):
    """Windows 優先用 Chrome 開：很多人的「預設瀏覽器」是平常沒在用的 Edge，
    網頁開在那裡等於沒開。macOS 用 open 交給預設瀏覽器就好。"""
    if sys.platform == 'darwin':
        try:
            subprocess.Popen(['open', url])
            return
        except Exception:
            pass
    else:
        for p in [os.path.expandvars(r'%ProgramFiles%\Google\Chrome\Application\chrome.exe'),
                  os.path.expandvars(r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe'),
                  os.path.expandvars(r'%LocalAppData%\Google\Chrome\Application\chrome.exe')]:
            if os.path.isfile(p):
                subprocess.Popen([p, url])
                return
    webbrowser.open(url)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype='application/json'):
        data = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype + '; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _body(self):
        n = int(self.headers.get('Content-Length', 0))
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode('utf-8'))
        except Exception:
            return {}

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/status':
            with LOCK:
                self._json({'jobs': JOBS[::-1], 'dir': OUTDIR, 'recent': RECENT,
                            'quick': quick_links(), 'warn': WARN})
        elif path == '/browse':
            q = parse_qs(urlparse(self.path).query)
            p = norm((q.get('path') or [''])[0]) or OUTDIR
            if not os.path.isdir(p):
                p = OUTDIR if os.path.isdir(OUTDIR) else desktop_dir()
            dirs, err = list_subdirs(p)
            self._json({'path': p, 'dirs': dirs or [], 'drives': list_drives(),
                        'err': ('打不開這個資料夾：' + err) if err else ''})
        else:
            self._send(200, HTML, 'text/html')

    def do_POST(self):
        global OUTDIR, WARN
        path = urlparse(self.path).path
        if path == '/download':
            body = self._body()
            with LOCK:
                cur = OUTDIR
            ok, err = check_dir(cur)
            if not ok:
                WARN = '現在的存檔位置「' + cur + '」不能用：' + err + '。請按「換資料夾」重新選一個。'
                self._json({'added': 0, 'err': '沒有開始下載——' + WARN})
                return
            WARN = ''
            urls = extract_urls(body.get('text', ''))
            ts = bool(body.get('transcribe', True))
            cv = bool(body.get('convert', False))
            with LOCK:
                for u in urls:
                    JOBS.append({'url': u, 'status': 'queued', 'msg': '', 'file': '',
                                 'transcribe': ts, 'convert': cv, 'outdir': cur, 'dir': cur})
            self._json({'added': len(urls)})

        elif path == '/setdir':
            p = norm(self._body().get('path'))
            ok, err = check_dir(p)
            if not ok:
                self._json({'ok': False, 'err': err})
                return
            with LOCK:
                OUTDIR = p
                push_recent(p)
                WARN = ''
            save_settings()
            print('存檔位置已改成：' + OUTDIR)
            self._json({'ok': True, 'dir': OUTDIR})

        elif path == '/mkdir':
            b = self._body()
            base, name = norm(b.get('path')), (b.get('name') or '').strip()
            if not name or set(name) & set('\\/:*?"<>|'):
                self._json({'ok': False, 'err': '資料夾名稱不能空白，也不能有 \\ / : * ? " < > |'})
                return
            newp = os.path.join(base, name)
            try:
                os.makedirs(newp, exist_ok=True)
            except Exception as e:
                self._json({'ok': False, 'err': '建不出來：' + str(e)[:80]})
                return
            self._json({'ok': True, 'path': newp})

        elif path == '/open':
            try:
                if os.name == 'nt':
                    os.startfile(OUTDIR)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', OUTDIR])
                else:
                    subprocess.Popen(['xdg-open', OUTDIR])
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'err': str(e)[:80]})
        else:
            self._send(404, '{}')


def main():
    # 讓 yt-dlp / 轉檔優先用工具包自己帶的 ffmpeg
    # （Windows 放在 runtime\；macOS 放在 bin/）
    mine = [os.path.join(SCRIPT_DIR, 'runtime'),
            os.path.join(SCRIPT_DIR, 'bin'),
            SCRIPT_DIR]
    os.environ['PATH'] = os.pathsep.join(mine) + os.pathsep + os.environ.get('PATH', '')
    # 先敲門：已經有一個下載器開著就直接開那頁，不再多開一份
    if already_running():
        print('下載器已經開著了（可能還有另一個黑視窗），直接幫你開網頁。')
        print('網頁沒跳出來的話，自己開瀏覽器貼上：http://127.0.0.1:%d' % PORT)
        print('這個視窗可以關掉。')
        open_page('http://127.0.0.1:%d' % PORT)
        time.sleep(3)
        return
    # 確認 yt-dlp / truststore 存在，不存在就自動安裝
    print('檢查下載引擎中…')
    try:
        subprocess.run([sys.executable, '-c', 'import yt_dlp, truststore'], capture_output=True, timeout=30, check=True)
    except Exception:
        print('第一次使用，正在安裝 yt-dlp / truststore …（要等一兩分鐘）')
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-U', 'yt-dlp', 'truststore', '-q'])
    threading.Thread(target=worker, daemon=True).start()
    try:
        server = Server(('127.0.0.1', PORT), H)
    except OSError:
        # 8765 被別的程式佔走：自動換一個空的 port
        server = Server(('127.0.0.1', 0), H)
    url = 'http://127.0.0.1:%d' % server.server_address[1]
    print('影片下載器啟動：' + url)
    print('影片會存到：' + OUTDIR + '（要換位置：網頁上按「換資料夾」）')
    if WARN:
        print('注意：' + WARN)
    print('網頁沒跳出來的話，自己開瀏覽器貼上：' + url)
    print('使用完畢直接關掉這個黑視窗即可。')
    open_page(url)
    server.serve_forever()


if __name__ == '__main__':
    main()
