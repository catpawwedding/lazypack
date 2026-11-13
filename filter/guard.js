/* 篩物件客戶頁的「下架守門」（2026-11-13，喵爸：所有的工具應該該下架就要下架）
 * 用法：<script src="guard.js" data-created="YYYY-MM-DD" data-days="14" defer></script>
 * ① 過期：做好超過 data-days 天（預設 14）→ 整頁換成「這份篩選表已過期」＋LINE 按鈕。
 *    原因：這種靜態頁永久留在網路上，物件早就可能成交下架，又沒辦法逐間確認。
 * ② 吉富物件：卡片 <div class="card" data-jifu="<attest 內部 id>"> → 打開時問 591 系統 DB
 *    jifu_status_by_attest_id（同 591 站「吉富查無」規則），gone＝卡片蓋上「已成交或下架」。
 *    查不到／斷線＝不動（寧可漏標不誤標）。
 */
(function () {
  var me = document.currentScript;
  var created = (me && me.getAttribute('data-created')) || '';
  var days = +((me && me.getAttribute('data-days')) || 14);
  var LINE = 'https://line.me/ti/p/M-tek5DmH6';

  function expire() {
    var w = document.querySelector('.wrap') || document.body;
    w.innerHTML = '<div class="card" style="text-align:center;padding:28px 20px;line-height:1.8">'
      + '<div style="font-size:20px;font-weight:900;margin-bottom:6px">這份篩選表已過期</div>'
      + '<div style="color:#666">裡面的物件可能已經成交或下架。<br>跟我說一聲，我幫您重新篩一份最新的。</div>'
      + '<div style="margin-top:16px"><a class="btn line" href="' + LINE + '">💬 幫我重新篩</a></div></div>';
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(created)) {
    var age = (Date.now() - new Date(created + 'T00:00:00+08:00').getTime()) / 86400000;
    if (age > days) { if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', expire); else expire(); return; }
  }

  function check() {
    var K = 'sb_publishable_sQCYgXGyKsijPERjkdCoMw_gevrBaDR';
    var cards = document.querySelectorAll('.card[data-jifu]');
    Array.prototype.forEach.call(cards, function (c) {
      var id = c.getAttribute('data-jifu');
      if (!/^\d{1,9}$/.test(id || '')) return;
      fetch('https://pkkywkugrjqacuapcdyw.supabase.co/rest/v1/rpc/jifu_status_by_attest_id', {
        method: 'POST', headers: { apikey: K, Authorization: 'Bearer ' + K, 'Content-Type': 'application/json' },
        body: JSON.stringify({ p_id: id })
      }).then(function (r) { return r.ok ? r.json() : null; }).then(function (v) {
        if (v !== 'gone') return;
        c.style.opacity = '.45'; c.style.filter = 'grayscale(1)';
        c.querySelectorAll('.acts').forEach(function (a) { a.style.display = 'none'; });
        var tag = document.createElement('div');
        tag.style.cssText = 'font-weight:900;color:#b42318;margin:6px 0';
        tag.textContent = '這間已成交或下架';
        c.insertBefore(tag, c.firstChild);
      }).catch(function () {});
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', check); else check();
})();
