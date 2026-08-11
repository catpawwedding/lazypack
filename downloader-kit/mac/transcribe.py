# -*- coding: utf-8 -*-
"""
喵爸逐字稿產生器 v1.1
把「影片檔 / 音檔 / 資料夾」拖到 transcribe.bat 上，
就會在原檔旁邊產出「檔名_逐字稿.txt」（繁體中文）。
引擎：faster-whisper (small / zh) + OpenCC 繁體化

v1.1 改了兩件事（為了長檔案，例如 3 小時錄音）：
1. 即時進度：每一段都印出「目前跑到幾分幾秒 / 總長多少（百分之幾）」，看得出它在動
2. 邊跑邊寫檔：先寫 .partial，跑完才改成正式檔名 → 中途斷掉前面的內容不會白跑
"""
import os
import sys
import subprocess
import tempfile
import time

# 保險：命令列是 cp950(Big5)，遇到印不出來的符號改成替代字，不要整支掛掉
try:
    sys.stdout.reconfigure(errors='replace')
    sys.stderr.reconfigure(errors='replace')
except Exception:
    pass

MEDIA_EXTS = {'.mp4', '.mkv', '.webm', '.mov', '.avi', '.m4v',
              '.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.opus'}


def collect_targets(paths):
    targets = []
    for p in paths:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                full = os.path.join(p, name)
                if os.path.isfile(full) and os.path.splitext(name)[1].lower() in MEDIA_EXTS:
                    targets.append(full)
        elif os.path.isfile(p) and os.path.splitext(p)[1].lower() in MEDIA_EXTS:
            targets.append(p)
    return targets


def extract_wav(src, tmpdir):
    """用 ffmpeg 抽出 16kHz 單聲道 wav（比直接餵影片穩）"""
    wav = os.path.join(tmpdir, 'audio.wav')
    cmd = ['ffmpeg', '-y', '-i', src, '-vn', '-ac', '1', '-ar', '16000',
           '-f', 'wav', wav]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0 or not os.path.isfile(wav):
        raise RuntimeError('ffmpeg 抽音軌失敗（檔案可能損毀或沒有聲音）')
    return wav


def hms(sec):
    sec = int(sec)
    return f'{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}'


def main():
    paths = sys.argv[1:]
    if not paths:
        print('用法：把「影片檔 / 音檔」或「整個資料夾」拖到 transcribe.bat 上放開即可。')
        print('支援：' + ' '.join(sorted(MEDIA_EXTS)))
        return

    targets = collect_targets(paths)
    if not targets:
        print('沒有找到可以轉的影片/音檔。')
        return

    print(f'共 {len(targets)} 個檔案要處理。')
    print('正在載入語音辨識模型（第一次會下載模型檔，之後就快了）…', flush=True)
    from faster_whisper import WhisperModel
    from opencc import OpenCC
    model = WhisperModel('small', device='cpu', compute_type='int8')
    cc = OpenCC('s2twp')

    done = skip = fail = 0
    for i, src in enumerate(targets, 1):
        base = os.path.splitext(os.path.basename(src))[0]
        out_txt = os.path.join(os.path.dirname(src), base + '_逐字稿.txt')
        partial = out_txt + '.partial'
        if os.path.isfile(out_txt):
            print(f'[{i}/{len(targets)}] [跳過] 已有逐字稿：{os.path.basename(src)}')
            skip += 1
            continue
        print(f'[{i}/{len(targets)}] === 轉逐字稿中：{os.path.basename(src)} ===', flush=True)
        t0 = time.time()
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                print('    抽音軌中…', flush=True)
                wav = extract_wav(src, tmpdir)
                segments, info = model.transcribe(
                    wav, language='zh', vad_filter=True,
                    initial_prompt='以下是繁體中文的逐字稿內容。')
                total = info.duration or 0
                print(f'    音檔長度 {hms(total)}，開始辨識（進度每 30 秒回報一次）', flush=True)

                chars = 0
                next_report = 0.0
                # 邊辨識邊寫 .partial，中途斷掉前面的不會白跑
                with open(partial, 'w', encoding='utf-8') as f:
                    for seg in segments:
                        f.write(cc.convert(seg.text))
                        f.flush()
                        chars += len(seg.text)
                        if seg.end >= next_report:
                            pct = (seg.end / total * 100) if total else 0
                            spent = time.time() - t0
                            eta = (spent / seg.end * (total - seg.end)) if seg.end > 0 else 0
                            print(f'    >> {hms(seg.end)} / {hms(total)}（{pct:.0f}%）'
                                  f' 已跑 {hms(spent)}，預估還要 {hms(eta)}，{chars} 字',
                                  flush=True)
                            next_report = seg.end + 30

            if chars == 0:
                raise RuntimeError('沒有辨識出任何內容（可能是無人聲或音量太小）')
            os.replace(partial, out_txt)
            print(f'    [完成] {os.path.basename(out_txt)}（{time.time() - t0:.0f} 秒，{chars} 字）', flush=True)
            done += 1
        except Exception as e:
            print(f'    [失敗] {e}', flush=True)
            if os.path.isfile(partial):
                print(f'    （已跑出來的內容保留在：{os.path.basename(partial)}）', flush=True)
            fail += 1

    print('')
    print('=' * 50)
    print(f' 全部處理完畢：成功 {done} 個，跳過 {skip} 個，失敗 {fail} 個')
    print(' 逐字稿存在各影片旁邊的「檔名_逐字稿.txt」')
    print('=' * 50)


if __name__ == '__main__':
    main()
