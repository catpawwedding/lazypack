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
