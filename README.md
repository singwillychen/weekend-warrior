# 週末戰士 Weekend Warrior — 營運管理平台

進出口運動器材電商的後台管理系統，部署於 QNAP NAS + Docker，透過 Cloudflare Tunnel 遠端存取。

## 功能模組

| 模組 | 說明 | 狀態 |
|------|------|------|
| M1 商品資訊庫 | SKU / 品名 / 售價 / 經銷商價（機密欄位加密） | 🚧 開發中 |
| M2 客戶往來檔 | 聯絡資料 / 報價歷史 / 備註 | 🚧 開發中 |
| M3 掃描槍匯入 | CSV 匯入 / 欄位對應 Mapping | 🚧 開發中 |
| M4 定價計算引擎 | EUR/USD→TWD / 關稅+貨物稅+毛利 / 手動調整 | 🚧 開發中 |
| M5 電商上架發布 | Easy Store API / 多平台模板 | 📋 規劃中 |
| M6 政府報價單 | 填寫表單 / Word & PDF 輸出 | 🚧 開發中 |
| M7 快速查價 | 中/英文/SKU 模糊搜尋 | 🚧 開發中 |

## 技術架構

```
QNAP TS-932PX (ARM64)
└── Container Station (Docker Compose)
    ├── ww_backend    FastAPI (Python 3.11)
    ├── ww_postgres   PostgreSQL 15
    ├── ww_nginx      Nginx (反向代理)
    └── ww_tunnel     Cloudflare Tunnel (遠端存取)
```

## 快速開始

### 前置需求

- QNAP NAS with Container Station 3.0+
- Cloudflare 帳號（免費）+ Tunnel Token
- Open Exchange Rates API Key（免費）

### 部署步驟

```bash
# 1. Clone 專案
git clone https://github.com/YOUR_USERNAME/weekend-warrior.git
cd weekend-warrior

# 2. 建立環境變數檔
cp .env.template .env
# 編輯 .env 填入必要值（DB_PASSWORD, SECRET_KEY, 各 API Key）

# 3. 啟動所有容器
docker compose up -d --build

# 4. 確認狀態
docker compose ps
```

### 本機存取

```
http://NAS_IP:8088
```

### 遠端存取（Cloudflare Tunnel）

```
https://ww.yourdomain.com
```

## 資料夾結構

```
weekend-warrior/
├── docker-compose.yml
├── .env.template          # 環境變數範本（.env 本身不納入版控）
├── .gitignore
├── nginx/
│   └── nginx.conf
├── app/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py            # FastAPI 主程式
└── 週末戰士-部署指南.md
```

## 版本紀錄

| 版本 | 日期 | 說明 |
|------|------|------|
| v0.1.0 | 2026-06-06 | 初始架構：Docker Compose 設定、部署指南 |

## 安全注意事項

- `.env` 含機密資訊，已列入 `.gitignore`，**絕對不推送至 GitHub**
- 資料庫密碼請使用 16 字元以上強密碼
- Cloudflare Tunnel 提供 TLS 加密，無需額外設定 HTTPS
- 機密欄位（經銷商價、毛利率）在資料庫層加密儲存
