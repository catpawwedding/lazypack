#!/bin/bash
# =============================================================
#  影片下載＋逐字稿工具包　macOS 安裝程式
#  用法：打開「終端機」貼上這一行 —
#    curl -fsSL https://catpawwedding.github.io/lazypack/downloader-kit/mac/install.sh | bash
#
#  全部東西都裝在 ~/影片下載器/ 裡，不動系統 Python、不需要密碼、
#  不需要 Homebrew。不想要了，把那個資料夾丟垃圾桶就乾淨。
# =============================================================
set -u

DIR="$HOME/影片下載器"
LOG="$DIR/安裝紀錄.txt"
BASE="https://catpawwedding.github.io/lazypack/downloader-kit/mac"
PYTAG="20260807"
PYVER="3.12.13"
FFTAG="b6.1.1"
PY="$DIR/runtime/python/bin/python3"

# ---------- 小工具 ----------
say()      { echo "$1"; [ -d "$DIR" ] && echo "$(date '+%H:%M:%S')  $1" >>"$LOG" 2>/dev/null; }
logonly()  { [ -d "$DIR" ] && echo "$1" >>"$LOG" 2>/dev/null; }
box() { # box 訊息 標題
  osascript -e "display dialog \"$1\" with title \"$2\" buttons {\"好\"} default button 1" >/dev/null 2>&1
}
die() {
  say ""
  say "[安裝失敗] $1"
  logonly "--- 失敗結束 ---"
  box "安裝沒有完成。\n\n原因：$1\n\n把「個人／影片下載器」資料夾裡的\n【安裝紀錄.txt】傳給介紹你來的朋友，\n一看就知道卡在哪，不用你猜。\n\n（多數情況只要把同一行指令再貼一次\n就會過，它會從斷掉的地方接著裝。）" "安裝失敗"
  exit 1
}
grab() { # grab 網址 存檔路徑 說明
  say "  下載 $3 ..."
  if ! curl -fL --progress-bar --retry 3 --connect-timeout 30 -o "$2" "$1"; then
    logonly "curl 失敗：$1"
    return 1
  fi
  [ -s "$2" ] || return 1
  say "  完成（$(du -m "$2" | cut -f1) MB）"
  return 0
}

# ---------- 0. 環境檢查 ----------
if [ "$(uname -s)" != "Darwin" ]; then
  echo "這一份是 Mac 專用的。Windows 請改用："
  echo "https://catpawwedding.github.io/lazypack/downloader-kit/"
  exit 1
fi
if [ "$(id -u)" = "0" ]; then
  echo "請不要用 sudo 執行，直接貼指令就好。"
  exit 1
fi

# 真正的晶片（在 Rosetta 底下跑 uname -m 會說謊）
if [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" = "1" ]; then
  CHIP="arm64"; PYARCH="aarch64"; FFARCH="arm64"
else
  CHIP="x86_64"; PYARCH="x86_64"; FFARCH="x64"
fi

mkdir -p "$DIR/bin" || { echo "無法建立資料夾 $DIR"; exit 1; }
echo "==== 安裝紀錄 $(date '+%Y-%m-%d %H:%M:%S') ====" >"$LOG"
logonly "macOS：$(sw_vers -productVersion 2>/dev/null)　晶片：$CHIP"
logonly "資料夾：$DIR"

echo ""
echo "  ============================================"
echo "    影片下載＋逐字稿工具包　安裝中"
echo "  ============================================"
echo "  這台是 $( [ "$CHIP" = "arm64" ] && echo "Apple 晶片 (M 系列)" || echo "Intel 晶片" ) 的 Mac"
echo "  第一次安裝大約 5～15 分鐘（看網速）。"
echo "  下面會一直有進度條在跑，跑完會跳一個對話框。"
echo "  這中間可以去忙別的，不要關掉這個視窗。"
echo ""

# ---------- 1. 專用 Python ----------
if [ -x "$PY" ]; then
  say "[1/6] 專用 Python 已經在了，跳過"
else
  say "[1/6] 安裝專用 Python（只裝在這個資料夾，不影響你電腦原本的設定）"
  TARBALL="/tmp/kit-python.tar.gz"
  URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PYTAG}/cpython-${PYVER}+${PYTAG}-${PYARCH}-apple-darwin-install_only.tar.gz"
  logonly "Python 來源：$URL"
  grab "$URL" "$TARBALL" "Python（約 20 MB）" || die "下載 Python 失敗，請確認網路連線後再貼一次指令"
  rm -rf "$DIR/runtime"
  mkdir -p "$DIR/runtime"
  tar -xzf "$TARBALL" -C "$DIR/runtime" 2>>"$LOG" || die "解壓縮 Python 失敗，請再貼一次指令"
  rm -f "$TARBALL"
  [ -x "$PY" ] || die "Python 解壓縮後找不到執行檔，請再貼一次指令"
  say "  Python OK"
fi
logonly "$("$PY" -c 'import sys;print("python",sys.version)' 2>&1)"

# ---------- 2. pip ----------
if "$PY" -m pip --version >/dev/null 2>&1; then
  say "[2/6] pip 已經在了，跳過"
else
  say "[2/6] 安裝套件管理員 pip"
  grab "https://bootstrap.pypa.io/get-pip.py" "/tmp/get-pip.py" "get-pip（約 2 MB）" || die "下載 pip 失敗"
  "$PY" /tmp/get-pip.py --no-warn-script-location >>"$LOG" 2>&1
  rm -f /tmp/get-pip.py
  "$PY" -m pip --version >/dev/null 2>&1 || die "pip 安裝失敗，請再貼一次指令"
  say "  pip OK"
fi

# ---------- 3. 下載／轉錄引擎 ----------
MISSING=""
for m in yt_dlp faster_whisper opencc truststore; do
  "$PY" -c "import $m" >/dev/null 2>&1 || MISSING="$MISSING $m"
done
if [ -z "$MISSING" ]; then
  say "[3/6] 下載／轉錄引擎已經在了，跳過"
else
  say "[3/6] 安裝下載＋轉錄引擎（這步最久，約 3～10 分鐘，請耐心等）"
  "$PY" -m pip install --no-warn-script-location --disable-pip-version-check -U \
      yt-dlp faster-whisper opencc-python-reimplemented truststore 2>&1 |
      tee -a "$LOG" | grep -E '^(Collecting|Installing|Successfully|ERROR)' | sed 's/^/    /'
  BAD=""
  for m in yt_dlp faster_whisper opencc truststore; do
    "$PY" -c "import $m" >/dev/null 2>&1 || BAD="$BAD $m"
  done
  [ -z "$BAD" ] || die "這些引擎沒裝成功：$BAD（多半是網路中斷，再貼一次指令通常就好）"
  say "  引擎 OK"
fi

# ---------- 4. ffmpeg ----------
if [ -x "$DIR/bin/ffmpeg" ] && [ -x "$DIR/bin/ffprobe" ]; then
  say "[4/6] ffmpeg 已經在了，跳過"
else
  say "[4/6] 安裝影音處理程式 ffmpeg（約 37 MB，下面有進度條）"
  for exe in ffmpeg ffprobe; do
    URL="https://github.com/eugeneware/ffmpeg-static/releases/download/${FFTAG}/${exe}-darwin-${FFARCH}.gz"
    logonly "$exe 來源：$URL"
    grab "$URL" "/tmp/kit-$exe.gz" "$exe" || die "下載 $exe 失敗，請確認網路（或關掉 VPN）後再貼一次指令"
    gunzip -f -c "/tmp/kit-$exe.gz" >"$DIR/bin/$exe" 2>>"$LOG" || die "解壓縮 $exe 失敗"
    chmod +x "$DIR/bin/$exe"
    rm -f "/tmp/kit-$exe.gz"
  done
  # 自己 curl 下來的檔案沒有隔離屬性，但保險起見再清一次
  xattr -dr com.apple.quarantine "$DIR/bin" 2>/dev/null
  "$DIR/bin/ffmpeg" -version >/dev/null 2>&1 || die "ffmpeg 裝好了但跑不起來（可能是晶片版本不符），請把安裝紀錄.txt 傳給朋友"
  say "  ffmpeg OK"
fi

# ---------- 5. 程式本體與桌面捷徑 ----------
say "[5/6] 安裝程式本體"
for f in downloader.py transcribe.py; do
  grab "$BASE/$f" "$DIR/$f" "$f" || die "下載 $f 失敗"
done

mkdir -p "$HOME/Desktop"

cat >"$DIR/影片下載器.command" <<'LAUNCH'
#!/bin/bash
DIR="$HOME/影片下載器"
cd "$DIR" || exit 1
export PATH="$DIR/bin:$PATH"
export PYTHONIOENCODING=utf-8
if [ ! -x "$DIR/runtime/python/bin/python3" ]; then
  osascript -e 'display dialog "還沒安裝完成。請重新執行安裝指令。" with title "請先安裝" buttons {"好"}' >/dev/null 2>&1
  exit 1
fi
"$DIR/runtime/python/bin/python3" -u "$DIR/downloader.py"
echo ""
echo "（可以關掉這個視窗了）"
LAUNCH

cat >"$DIR/轉逐字稿.command" <<'LAUNCH'
#!/bin/bash
DIR="$HOME/影片下載器"
cd "$DIR" || exit 1
export PATH="$DIR/bin:$PATH"
export PYTHONIOENCODING=utf-8
if [ ! -x "$DIR/runtime/python/bin/python3" ]; then
  osascript -e 'display dialog "還沒安裝完成。請重新執行安裝指令。" with title "請先安裝" buttons {"好"}' >/dev/null 2>&1
  exit 1
fi
if [ "$#" -gt 0 ]; then
  "$DIR/runtime/python/bin/python3" "$DIR/transcribe.py" "$@"
else
  PICKED=$(osascript <<'APPLE'
try
  set theItems to choose file with prompt "選要轉逐字稿的影片或錄音檔（可以按住 command 多選）" with multiple selections allowed
  set out to {}
  repeat with f in theItems
    set end of out to POSIX path of f
  end repeat
  set AppleScript's text item delimiters to linefeed
  return out as text
on error number -128
  return ""
end try
APPLE
)
  if [ -z "$PICKED" ]; then echo "沒有選檔案，結束。"; exit 0; fi
  OLDIFS="$IFS"; IFS=$'\n'
  # shellcheck disable=SC2206
  FILES=($PICKED)
  IFS="$OLDIFS"
  "$DIR/runtime/python/bin/python3" "$DIR/transcribe.py" "${FILES[@]}"
fi
echo ""
read -r -p "按 Enter 關閉這個視窗 " _
LAUNCH

cat >"$DIR/體檢.command" <<'LAUNCH'
#!/bin/bash
DIR="$HOME/影片下載器"
REP="$DIR/診斷報告.txt"
PY="$DIR/runtime/python/bin/python3"
{
  echo "==== 工具包診斷報告 $(date '+%Y-%m-%d %H:%M:%S') ===="
  echo "macOS：$(sw_vers -productVersion 2>/dev/null)"
  if [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" = "1" ]; then echo "晶片：Apple (arm64)"; else echo "晶片：Intel (x86_64)"; fi
  echo "資料夾：$DIR"
  echo ""
  echo "--- 1. 專用 Python ---"
  if [ -x "$PY" ]; then echo "  OK  $("$PY" -c 'import sys;print(sys.version.split()[0])' 2>&1)"; else echo "  沒有！請重跑安裝指令"; fi
  echo ""
  echo "--- 2. 下載／轉錄引擎 ---"
  for m in yt_dlp faster_whisper opencc truststore; do
    if [ -x "$PY" ] && "$PY" -c "import $m" >/dev/null 2>&1; then echo "  OK      $m"; else echo "  缺少！   $m"; fi
  done
  echo ""
  echo "--- 3. ffmpeg ---"
  if [ -x "$DIR/bin/ffmpeg" ] && "$DIR/bin/ffmpeg" -version >/dev/null 2>&1; then echo "  OK"; else echo "  沒有或跑不起來！請重跑安裝指令"; fi
  echo ""
  echo "--- 4. 語音模型 ---"
  if ls "$HOME/.cache/huggingface/hub" 2>/dev/null | grep -qi 'whisper.*small'; then
    echo "  OK  （已下載，第一次轉稿不用等）"
  else
    echo "  還沒下載（第一次轉逐字稿時會自動抓，約 500MB）"
  fi
  echo ""
  echo "--- 5. 下載器有沒有已經開著 ---"
  if lsof -nP -iTCP:8765 -sTCP:LISTEN 2>/dev/null | tail -n +2 | head -3; then :; fi
  echo "  （上面有東西＝已經開著；空的＝沒開，正常）"
  echo ""
  echo "--- 6. 網路連線 ---"
  for h in www.python.org pypi.org www.youtube.com; do
    if curl -sfI -m 8 "https://$h" >/dev/null 2>&1; then echo "  $h  通"; else echo "  $h  不通（可能被防火牆或 VPN 擋住）"; fi
  done
  echo ""
  echo "--- 7. 上次安裝紀錄（最後 40 行）---"
  if [ -f "$DIR/安裝紀錄.txt" ]; then tail -40 "$DIR/安裝紀錄.txt" | sed 's/^/  /'; else echo "  找不到安裝紀錄.txt"; fi
} | tee "$REP"
echo ""
echo "報告已存成：$REP"
osascript -e 'display dialog "體檢完成。\n\n「影片下載器」資料夾裡多了一個\n【診斷報告.txt】\n\n把它傳給介紹你來的朋友，\n他一看就知道卡在哪。\n\n（按好會幫你打開這個檔）" with title "體檢完成" buttons {"好"} default button 1' >/dev/null 2>&1
open -e "$REP"
LAUNCH

chmod +x "$DIR"/*.command
xattr -dr com.apple.quarantine "$DIR" 2>/dev/null

# 桌面捷徑：用「複製」不用符號連結——Finder 對指向 .command 的 symlink
# 不保證會乖乖用終端機開啟；這兩個檔本來就只是薄薄的啟動器，複製過去不會過期。
cp -f "$DIR/影片下載器.command" "$HOME/Desktop/影片下載器.command"
cp -f "$DIR/轉逐字稿.command"   "$HOME/Desktop/轉逐字稿.command"
chmod +x "$HOME/Desktop/影片下載器.command" "$HOME/Desktop/轉逐字稿.command"
xattr -dr com.apple.quarantine "$HOME/Desktop/影片下載器.command" "$HOME/Desktop/轉逐字稿.command" 2>/dev/null
say "  程式本體與桌面捷徑 OK"

# ---------- 6. 語音模型 ----------
say "[6/6] 先下載語音辨識模型（約 500 MB，只有這一次）"
cat >/tmp/kit-model.py <<'PYEOF'
try:
    from faster_whisper import WhisperModel
    WhisperModel("small", device="cpu", compute_type="int8")
    print("MODEL_OK")
except Exception as e:
    print("MODEL_FAIL:" + str(e)[:300])
PYEOF
HUB="$HOME/.cache/huggingface"
BASE_MB=$(du -sm "$HUB" 2>/dev/null | cut -f1); BASE_MB=${BASE_MB:-0}
"$PY" /tmp/kit-model.py >/tmp/kit-model.out 2>&1 &
MPID=$!
T0=$(date +%s)
while kill -0 "$MPID" 2>/dev/null; do
  sleep 6
  NOW_MB=$(du -sm "$HUB" 2>/dev/null | cut -f1); NOW_MB=${NOW_MB:-0}
  GOT=$(( NOW_MB - BASE_MB )); [ "$GOT" -lt 0 ] && GOT=0
  echo "      已下載約 ${GOT} MB / 約 480 MB　（已經 $(( ($(date +%s) - T0) / 60 )) 分 $(( ($(date +%s) - T0) % 60 )) 秒）"
done
wait "$MPID" 2>/dev/null
MOUT=$(cat /tmp/kit-model.out 2>/dev/null)
logonly "$MOUT"
rm -f /tmp/kit-model.py /tmp/kit-model.out
if echo "$MOUT" | grep -q MODEL_OK; then
  say "  語音模型 OK"; MODEL_NOTE=""
else
  say "  語音模型這次沒抓成功（不影響安裝，第一次轉逐字稿時會自動再抓一次）"
  MODEL_NOTE="\n\n（語音模型這次沒抓下來，不影響使用，\n第一次轉逐字稿時會自動再抓，那一次會慢一點。）"
fi

# ---------- 收工 ----------
logonly "--- 安裝成功 ---"
echo ""
echo "  ============================================"
echo "    安裝完成"
echo "  ============================================"
echo ""
box "安裝完成，可以用了！\n\n桌面上多了兩個東西：\n【影片下載器】點兩下 → 跳出下載器網頁，\n　　貼影片網址就能下載\n【轉逐字稿】點兩下 → 選檔案 → 產逐字稿\n\n影片會存到桌面的「影片下載」資料夾，\n旁邊會附一份打好的繁體逐字稿。\n\n這個安裝指令以後都不用再貼了。$MODEL_NOTE" "安裝完成"
open "$HOME/Desktop" 2>/dev/null
exit 0
