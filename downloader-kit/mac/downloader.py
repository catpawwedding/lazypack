# -*- coding: utf-8 -*-
"""
喵爸影片下載器 v1.1（工具包通用版）
雙擊「start.bat」使用。貼上 FB / IG / TikTok / YouTube 影片網址即可下載。
影片存到桌面「影片下載」資料夾。
v1.1：下載完可自動接「產逐字稿」（transcribe.py）與「轉H264」，貼完連結就能去忙別的。
v2  ：工具包自帶 Python（runtime\\），不吃系統環境；ffmpeg 也在 runtime\\ 裡。
"""
import os, sys, json, re, threading, subprocess, webbrowser, time
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8765
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_outdir():
    home = os.path.expanduser('~')
    for d in [os.path.join(home, 'Desktop'), os.path.join(home, 'OneDrive', 'Desktop'), os.path.join(home, 'OneDrive', '桌面'), home]:
        if os.path.isdir(d):
            out = os.path.join(d, '影片下載')
            os.makedirs(out, exist_ok=True)
            return out
    out = os.path.join(home, '影片下載')
    os.makedirs(out, exist_ok=True)
    return out

OUTDIR = get_outdir()
JOBS = []          # [{url, status, msg, file}]
LOCK = threading.Lock()
WORKING = False

def extract_urls(text):
    urls = re.findall(r'https?://[^\s"\'<>，、]+', text)
    seen, out = set(), []
    for u in urls:
        u = u.rstrip('.,;)')
        if u not in seen:
            seen.add(u); out.append(u)
    return out

def run_transcribe(filepath):
    """下載完自動產逐字稿：先找「影片下載」資料夾的 transcribe.py，再找工具包資料夾"""
    script = None
    for d in [OUTDIR, SCRIPT_DIR]:
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
        return True, '轉好H264\\' + os.path.basename(outfile)
    p = subprocess.run(['ffmpeg', '-y', '-i', filepath,
                        '-c:v', 'libx264', '-crf', '20', '-preset', 'medium',
                        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', outfile],
                       capture_output=True, timeout=1800)
    if p.returncode == 0 and os.path.isfile(outfile):
        return True, '轉好H264\\' + os.path.basename(outfile)
    return False, '轉檔失敗（可能缺 ffmpeg）'


def run_download(job):
    url = job['url']
    with LOCK:
        job['status'] = 'downloading'; job['msg'] = '下載中…'
    before = set(os.listdir(OUTDIR))
    # 用 truststore 走 Windows 憑證庫，避開部分機器 python SSL 憑證驗證失敗的老毛病
    boot = ('import sys;'
            'import truststore; truststore.inject_into_ssl();'
            'from yt_dlp import main; main(sys.argv[1:])')
    cmd = [sys.executable, '-c', boot,
           '-o', os.path.join(OUTDIR, '%(id)s.%(ext)s'),
           '--no-playlist', '--restrict-filenames',
           '--merge-output-format', 'mp4',
           url]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
        new_files = [f for f in (set(os.listdir(OUTDIR)) - before) if not f.endswith(('.part', '.ytdl'))]
        if p.returncode == 0:
            fname = new_files[0] if new_files else ''
            if not fname:
                # 之前下載過的話 yt-dlp 會直接跳過，OUTDIR 不會多出新檔案，
                # 從它的輸出把檔名撈回來，才不會顯示「完成 →（空白）」讓人以為壞了
                m = re.search(r'\[download\] (.+?) has already been downloaded',
                              (p.stdout or '') + (p.stderr or ''))
                if m:
                    cand = os.path.basename(m.group(1).strip())
                    if os.path.isfile(os.path.join(OUTDIR, cand)):
                        fname = cand
            filepath = os.path.join(OUTDIR, fname) if fname else ''
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
  body{font-family:"Microsoft JhengHei",sans-serif;background:#f5f7f5;margin:0;padding:24px;color:#222}
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
  .folder{margin-top:14px;font-size:13px;color:#666}
  code{background:#f0f0f0;padding:2px 6px;border-radius:4px}
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
  <div class="folder">存檔位置：<code>__OUTDIR__</code></div>
  <div id="list"></div>
</div>
<script>
async function go(){
  const t = document.getElementById('urls').value.trim();
  if(!t) return;
  document.getElementById('go').disabled = true;
  await fetch('/download',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({text:t,
      transcribe:document.getElementById('opt_ts').checked,
      convert:document.getElementById('opt_cv').checked})});
  document.getElementById('urls').value='';
  document.getElementById('go').disabled = false;
}
const names={queued:'排隊中',downloading:'下載中',transcribing:'逐字稿',converting:'轉檔中',done:'完成',error:'失敗'};
async function poll(){
  try{
    const r = await fetch('/status'); const js = await r.json();
    document.getElementById('list').innerHTML = js.jobs.map(j=>
      `<div class="job"><div class="st ${j.status}">${names[j.status]}</div>
       <div class="u">${j.url}<div class="m">${j.msg||''}</div></div></div>`).join('');
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
    import urllib.request
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/status', timeout=2) as r:
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
    def do_GET(self):
        if self.path == '/status':
            with LOCK:
                self._send(200, json.dumps({'jobs': JOBS[::-1]}, ensure_ascii=False))
        else:
            self._send(200, HTML.replace('__OUTDIR__', OUTDIR), 'text/html')
    def do_POST(self):
        if self.path == '/download':
            n = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(n).decode('utf-8'))
            urls = extract_urls(body.get('text', ''))
            ts = bool(body.get('transcribe', True))
            cv = bool(body.get('convert', False))
            with LOCK:
                for u in urls:
                    JOBS.append({'url': u, 'status': 'queued', 'msg': '', 'file': '',
                                 'transcribe': ts, 'convert': cv})
            self._send(200, json.dumps({'added': len(urls)}))
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
        print(f'網頁沒跳出來的話，自己開瀏覽器貼上：http://127.0.0.1:{PORT}')
        print('這個視窗可以關掉。')
        open_page(f'http://127.0.0.1:{PORT}')
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
    url = f'http://127.0.0.1:{server.server_address[1]}'
    print(f'影片下載器啟動：{url}')
    print(f'影片會存到：{OUTDIR}')
    print(f'網頁沒跳出來的話，自己開瀏覽器貼上：{url}')
    print('使用完畢直接關掉這個黑視窗即可。')
    open_page(url)
    server.serve_forever()

if __name__ == '__main__':
    main()
