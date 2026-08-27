---
title: pack.cathome.tw 搬家後成效體檢 SOP
date: 2026-08-26
tags: [SEO, 排程, 體檢]
---

# pack.cathome.tw 成效體檢 SOP

> 2026-08-26 懶人包站從 `catpawwedding.github.io/lazypack` 搬到自有網域 `pack.cathome.tw`，
> 同時補上品牌結構化資料、llms.txt、sitemap。這份是搬家後的定期體檢流程，
> 由雲端 routine「9/2 pack.cathome.tw 搬家後成效體檢」自動執行。

## 要做的四件事

### 1. 站台健康
用 curl 確認以下網址都回 200：
- `https://pack.cathome.tw/`
- `https://pack.cathome.tw/sitemap.xml`
- `https://pack.cathome.tw/llms.txt`
- `https://pack.cathome.tw/anhao.json`
- `https://pack.cathome.tw/zuke/`
- `https://pack.cathome.tw/inherit-check.html`

另外兩項：
- 首頁 HTML 仍含 `cathome.tw/author/anttow`（品牌實體標記，掉了代表 SEO 白做）
- 舊網址 `https://catpawwedding.github.io/lazypack/inherit-check.html` 仍正確 **301** 到 pack.cathome.tw
  （這條斷掉＝以前發出去的所有懶人包連結全壞，最嚴重）

### 2. 暗號交付鏈（最高優先）
讀 `https://pack.cathome.tw/anhao.json`，取出所有 `type=deliver` 的 `asset` 網址，逐一 curl 確認 200。

🔴 **任何一個掛掉都要在報告最上面用紅字標出來**——那代表粉絲留了暗號卻拿不到東西，
是會直接損失名單的故障，不是小問題。

### 3. 收錄與關鍵字現況
- WebSearch 搜 `site:pack.cathome.tw`，估算 Google 收錄了幾頁、哪些頁被收錄
- 再搜這幾組關鍵字，看喵爸的頁面有沒有出現在結果裡、大約第幾個：
  中壢房仲／中壢專業房仲喵爸／繼承的房子該不該賣／租客篩選檢核表／桃園學區地圖

### 4. 產出報告
寫成 `100_Todo/drafts/YYYY-MM-DD_pack搬家後體檢.md`，結構：
1. 一句話結論（健康／有問題）
2. 站台與暗號鏈檢查表
3. 收錄與關鍵字現況
4. 建議的下一步

寫完 commit + push（commit 訊息用繁體中文，結尾加 `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`）。

## 🔴 限制（照實寫進報告，不要假裝）

雲端 routine **沒有 Google Search Console 的授權**，拿不到真正的排名、曝光、點擊數據。
那部分只能由喵爸在本機對 Claude Code 說一句「**撈GSC**」才查得到。

報告最後一定要寫出這一行提醒。**不要假裝查過 GSC，也不要編造任何數字。**

## 相關

記憶檔：`lazypack-seo-overhaul`、`anhao-delivery-chain-broken`、`gsc-mcp-installed`、`tools-seo-geo-entity`

---

# 第 5 件事：官網地基驗收（2026-08-26 加入）

8/26 修了官網兩個地基問題，9/2 這輪要驗收成效，**這決定喵爸能不能開始寫下一批內容**。

## 背景（給執行的你）

8/26 發現官網 42 篇文章有 9 篇的 canonical 指向 404 的分類網址
（例如 `/category/case/2`），等於那些文章一直在叫 Google 不要收錄自己。
同日一併修好，並把兩個建案頁的網址從 `case_1`／`case_2` 改成語意化網址。

## 要檢查

1. **canonical 全站掃描**：抓 `https://cathome.tw/wp-sitemap-posts-post-1.xml` 的所有 `<loc>`，
   逐頁比對 `rel="canonical"` 是否等於該頁自己的網址（比對前先 unquote、去掉結尾斜線）。
   **應該是 0 篇錯誤**；若又出現錯誤，在報告最上面標紅——代表有東西把設定改回去了。

2. **兩個改名頁面**：
   - `https://cathome.tw/zhongli-dingcang-zhongyuanhui/`（鼎藏中原匯）
   - `https://cathome.tw/taoyuan-zhonglu-yicheng-qianli/`（宜誠謙里）
   確認：回 200、canonical 指自己、標題仍是改後版本、alt 數量沒掉
   （鼎藏應 ≥10 個、宜誠謙里應 ≥23 個）。
   另確認舊網址 `https://cathome.tw/case_1/` 與 `/case_2/` 仍正確 **301** 到新網址。

3. **搜尋收錄狀況**：用 WebSearch 搜 `宜誠謙里`、`鼎藏中原匯`、`鑫富貴`，
   記錄喵爸的頁面有沒有出現、大約第幾個。**8/26 的基準值：宜誠謙里第 10.7 名、鼎藏第 4.9 名。**

## 🔴 報告最後要寫的判斷（這是這輪最重要的產出）

依照上面的結果，明確寫出一句建議：

- **如果 canonical 仍是 0 錯誤、兩頁正常、宜誠謙里排名有往前**
  → 寫：「**地基驗證通過，可以開始寫內容了**。下一步照 Iris 8/26 的優先序：
  ① 鑫富貴專頁（336 曝光、目前完全沒做頁）② 宜誠謙里內容重做
  （要補的是別人沒有的：逐戶實價登錄成交、價格走勢、周邊同級建案比價、施工進度）。」

- **如果排名還沒動**
  → 寫：「地基修好但 Google 還沒重新評估完，**再等一週**，先不要投入寫作。」

- **如果出現新的 canonical 錯誤或頁面異常**
  → 標紅，寫清楚是哪幾篇、指向哪裡，這優先於一切。

**不要自己編排名數字**——查不到就寫查不到。
