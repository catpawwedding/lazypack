/* 賀榜產生器核心：訊息解析 + 投影片規格（版型逆向自既有「賀榜 - 11xxxxx.pptx」） */
(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) module.exports = factory();
  else root.HebangCore = factory();
})(typeof self !== 'undefined' ? self : this, function () {

  var TYPE_KEYWORDS = [
    ['透店', '透店'],
    ['店面', '透店'],
    ['透天', '透天'],
    ['套房', '套房'],
    ['美寓', '公寓'],
    ['公寓', '公寓'],
    ['華廈', '華廈'],
    ['土地', '土地'],
  ];
  var TYPES = ['大樓', '公寓', '透天', '透店', '套房', '華廈', '土地'];

  function guessType(title) {
    for (var i = 0; i < TYPE_KEYWORDS.length; i++) {
      if (title.indexOf(TYPE_KEYWORDS[i][0]) !== -1) return TYPE_KEYWORDS[i][1];
    }
    return '大樓';
  }

  function bandText(type) {
    return type === '土地' ? '成交土地乙筆' : '成交' + type + '乙戶';
  }

  // 把好幾封主管訊息拆成一筆一筆成交
  function parseMessages(raw) {
    var lines = String(raw || '').replace(/\r/g, '').split('\n');
    var cases = [];
    var cur = null;

    function ensure() { if (!cur) cur = { title: '', dev: '', sell: '', extra: [] }; return cur; }
    function commit() {
      if (cur && (cur.title || cur.dev || cur.sell)) {
        if (!cur.type) cur.type = guessType(cur.title);
        cases.push(cur);
      }
      cur = null;
    }

    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim();
      if (!line) { continue; } // 空行不強制斷筆，靠「開發：」重複出現斷

      var norm = line.replace(/[:]/g, '：');
      var m;
      if ((m = norm.match(/^開\s*發：\s*(.*)$/))) {
        if (cur && cur.dev) commit(); // 又一個「開發：」＝下一筆
        ensure().dev = m[1].trim();
      } else if ((m = norm.match(/^銷\s*售：\s*(.*)$/))) {
        if (cur && cur.sell) commit();
        ensure().sell = m[1].trim();
      } else if ((m = line.match(/^[（(]\s*(.+?)\s*[）)]$/))) {
        if (cur && cur.title) commit();
        ensure().title = m[1].trim();
      } else if (/^(建坪|坪數|地坪|主建|權狀|成交|總價|車位|開價|樓層|屋齡)\s*[：:]/.test(norm) || /^\d[\d.,]*\s*(萬|坪)/.test(line)) {
        ensure().extra.push(line);
      } else {
        // 沒冒號的自由行：還沒有案名就當案名
        if (cur && cur.title) { cur.extra.push(line); }
        else { ensure().title = line.replace(/^[「『"']|[」』"']$/g, ''); }
      }
    }
    commit();
    return cases;
  }

  // 案名太長自動縮字（滿版寬約 9.4in = 677pt；全形字寬≈字級 pt）
  function titleFontSize(title) {
    var units = 0;
    for (var i = 0; i < title.length; i++) {
      units += /[⺀-鿿豈-﫿！-｠]/.test(title[i]) ? 1 : 0.55;
    }
    if (units <= 0) units = 1;
    return Math.max(28, Math.min(54, Math.floor(677 / units)));
  }

  // 民國檔名：2026-07-06 → 1150706
  function rocStamp(dateStr) {
    var m = String(dateStr).match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return '';
    return String(Number(m[1]) - 1911) + m[2] + m[3];
  }

  // 版型常數（EMU→吋，取自既有賀榜檔）
  var LAYOUT = { name: 'HEBANG169', width: 10, height: 5.625 };
  var SPEC = {
    bg: { color: 'FF0000', transparency: 25 },              // 紅底 75% 不透明
    he: { x: 0, y: -0.18, w: 10, h: 1.72, size: 96, font: '文鼎中特廣告體' },
    popperR: { x: 7.15, y: 0.169, w: 1.226, h: 1.226 },
    popperL: { x: 1.698, y: 0.169, w: 1.181, h: 1.181, flipH: true },
    mid: { x: 0, y: 1.395, w: 10, h: 2.9, lineSpacing: 70, font: '微軟正黑體', nameSize: 48 },
    band: { x: 0, y: 4.4, w: 10, h: 1.01, size: 54, font: '王漢宗特圓體繁' },
  };

  // 把一批成交塞進 pptxgenjs 實例
  function buildDeck(pptx, cases, popperB64) {
    pptx.defineLayout(LAYOUT);
    pptx.layout = LAYOUT.name;
    var imgData = 'image/png;base64,' + popperB64;

    cases.forEach(function (c) {
      var s = pptx.addSlide();
      s.background = SPEC.bg;
      s.addText('賀成交', {
        x: SPEC.he.x, y: SPEC.he.y, w: SPEC.he.w, h: SPEC.he.h,
        align: 'center', valign: 'middle', bold: true,
        fontSize: SPEC.he.size, fontFace: SPEC.he.font, color: '000000',
      });
      s.addImage({ data: imgData, x: SPEC.popperR.x, y: SPEC.popperR.y, w: SPEC.popperR.w, h: SPEC.popperR.h });
      s.addImage({ data: imgData, x: SPEC.popperL.x, y: SPEC.popperL.y, w: SPEC.popperL.w, h: SPEC.popperL.h, flipH: true });

      var runs = [{
        text: c.title,
        options: { fontSize: titleFontSize(c.title), bold: true, fontFace: SPEC.mid.font, color: '000000', breakLine: true, align: 'center', lineSpacing: SPEC.mid.lineSpacing },
      }];
      if (c.dev) runs.push({
        text: '開發：' + c.dev,
        options: { fontSize: SPEC.mid.nameSize, bold: true, fontFace: SPEC.mid.font, color: '000000', breakLine: true, align: 'center', lineSpacing: SPEC.mid.lineSpacing },
      });
      if (c.sell) runs.push({
        text: '銷售：' + c.sell,
        options: { fontSize: SPEC.mid.nameSize, bold: true, fontFace: SPEC.mid.font, color: '000000', breakLine: true, align: 'center', lineSpacing: SPEC.mid.lineSpacing },
      });
      s.addText(runs, { x: SPEC.mid.x, y: SPEC.mid.y, w: SPEC.mid.w, h: SPEC.mid.h, align: 'center', valign: 'top' });

      s.addText(c.band || bandText(c.type), {
        x: SPEC.band.x, y: SPEC.band.y, w: SPEC.band.w, h: SPEC.band.h,
        align: 'center', valign: 'middle',
        fontSize: SPEC.band.size, fontFace: SPEC.band.font, color: '000000',
      });
    });
    return pptx;
  }

  return {
    parseMessages: parseMessages,
    guessType: guessType,
    bandText: bandText,
    titleFontSize: titleFontSize,
    rocStamp: rocStamp,
    buildDeck: buildDeck,
    TYPES: TYPES,
  };
});
