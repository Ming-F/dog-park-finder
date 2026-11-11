# 🐕 宠物友好公园查询（Dog Park Finder）— 一个 WorkBuddy Skill

[![Version](https://img.shields.io/badge/version-0.1.0-blue)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![WorkBuddy](https://img.shields.io/badge/WorkBuddy-Skill-6c5ce7)](https://www.workbuddy.cn)

一个 [WorkBuddy](https://www.workbuddy.cn) 技能（skill），让你的个人智能体回答一个简单的问题：

> **「附近哪里能遛狗？有什么限制？」**

给定一个位置（通过 IP 自动定位，或用户口述），智能体会查找附近的公园，并**如实**报告每个公园的开放时间与遛狗限制（需牵绳、需登记、限体型、禁止携犬等）。还能结合**实时天气与当前时间**，当下为你的狗规划一条合适的遛狗路线。

---

## ✨ 功能

- **自动定位用户**：通过 IP 定位（`ip-api.com`）拿到城市，再用 Photon（OSM）逆地理精确到区。无需任何配置。
- **查找附近公园**：与一份**已核实**的宠物友好公园数据集（当前覆盖北京、上海共 38 处）匹配，含每处的规则、开放时间、来源分级。
- **可选全国实时搜索**：配置一个免费的高德或腾讯地图 API key，即可在**任意**中国城市实时搜索公园。
- **规则判定**：把每处地点映射成明确结论——✅ 可遛狗（牵绳/登记/限体型/分区/柔性管理）或 ❌ 禁入，并给出理由与实用建议。
- **合规优先**：绝不编造公园或规则，始终标注来源分级（官方 / 媒体），绝不淡化「禁止携犬」等限制。

---

## 📁 目录结构

```
dog-park-finder/
├── SKILL.md                    # 触发条件 + 用法 + 合规红线 + 实时规划流程
├── README.md                   # 项目说明
├── CHANGELOG.md                # 版本记录
├── LICENSE                     # MIT
├── data/
│   └── places.json             # 已核实公园数据集（唯一数据源）
├── examples/
│   └── demo-conversation.md    # 实战对话示例
├── references/
│   ├── places-schema.md        # 字段说明 & ruleLevel 枚举 & routes 结构
│   └── policy.md               # 各城市养犬/公园政策背景
└── scripts/
    ├── query_parks.py          # 主查询：定位 → 搜索 → 判定 → 降级
    ├── recommend_routes.py     # 遛狗路线推荐（提供材料，供 agent 实时规划）
    ├── weather.py              # 实时天气 + 当前时间（路线规划的「当下」上下文）
    ├── locate.py               # IP 定位 + 逆地理
    ├── setup_key.py            # 地图 key 配置与校验（可选）
    └── export_places.js        # 从 Pet Life 小程序重新导出数据集
```

---

## 📥 下载与安装

### 下载

**方式一：git clone（推荐）**

```bash
git clone https://github.com/Ming-F/dog-park-finder.git
```

**方式二：下载 ZIP**

点击仓库右上角绿色 **Code** 按钮 → **Download ZIP**，解压得到 `dog-park-finder` 文件夹。

### 安装到 WorkBuddy

把下载的 `dog-park-finder` 文件夹复制到用户级 skill 目录：

```bash
mkdir -p ~/.workbuddy/skills
cp -r dog-park-finder ~/.workbuddy/skills/
```

> 若在 Windows，用户级 skill 目录为 `C:\Users\<用户名>\.workbuddy\skills\`。

WorkBuddy 会根据 `SKILL.md` 的 frontmatter 自动发现该技能，无需其他配置。之后直接问：

- 「附近哪里能遛狗？」
- 「朝阳区有什么能带狗的公园？」
- 「狼垡公园能不能带狗？」
- 「推荐一条遛狗路线」

---

## 🧪 直接运行脚本

```bash
# 自动 IP 定位
python3 scripts/query_parks.py

# 指定城市
python3 scripts/query_parks.py --city 上海 --limit 8

# 指定位置 / 区 / 地铁站
python3 scripts/query_parks.py --place "朝阳区"

# 按限制筛选
python3 scripts/query_parks.py --city 北京 --rule 需登记

# 结构化输出（供智能体二次处理）
python3 scripts/query_parks.py --city 上海 --json
```

### 遛狗路线推荐

```bash
# 自动 IP 定位，推荐 3 条最佳遛狗路线
python3 scripts/recommend_routes.py

# 指定城市 / 位置
python3 scripts/recommend_routes.py --city 北京
python3 scripts/recommend_routes.py --place "朝阳区"

# 用户选了某条路线后，排除它继续推荐新的
python3 scripts/recommend_routes.py --exclude route_hcw_1

# 只看某个公园的路线
python3 scripts/recommend_routes.py --park place_bj_laoshan
```

路线结果包含：路线名、所属公园、距离、起点→途经→终点的走法、长度/时长、路面、适用犬型、贴士、该公园规则。

---

## 🗺️ 启用全国实时搜索（可选）

默认零配置即可用（基于本地已核实的北京、上海数据）。若要在**任意**中国城市实时搜索公园，配置一个免费的地图 API key：

```bash
python3 scripts/setup_key.py guide          # 一键申请链接
python3 scripts/setup_key.py amap <key>     # 或：tencent <key>
python3 scripts/setup_key.py status         # 查看配置状态
```

- **高德**：https://lbs.amap.com/dev/#/ — 创建应用 → 添加 Key（服务平台选 **「Web 服务」**）
- **腾讯**：https://lbs.qq.com/dev/console/home — 创建应用 → 添加 key（勾选 **WebService API**）

key 保存在本地 `config.json`（私有，不会被提交）。

---

## 🧾 数据模型

`data/places.json` 中每处公园：

| 字段 | 含义 |
|---|---|
| `name` / `shortName` | 全名 / 别名 |
| `city` / `district` | 城市 / 区 |
| `category` | 郊野公园 / 城市公园 / 湿地公园 / 宠物乐园 / 景区 |
| `openTime` | 开放时间 |
| `ruleLevel` | `需牵绳` / `需登记` / `限体型` / `分区管理` / `封闭乐园` / `柔性管理` / `禁止携犬` |
| `rules` | 详细规则（自然语言） |
| `source` | 数据来源 |
| `official` | `true` = 官方核实，`false` = 媒体整理 |
| `verifiedAt` | 核验日期 |
| `latitude` / `longitude` | 坐标（WGS84） |

完整字段说明见 [`references/places-schema.md`](references/places-schema.md)。

---

## ⚖️ 合规原则

1. 绝不编造公园或规则。
2. 始终标注来源分级；媒体整理来源的规则一律补「以园方现场公示为准」。
3. 绝不淡化限制——「禁止携犬」以及烈性犬/大型犬禁令如实报告。
4. 引用政策时标注日期，并提示政策可能变化。
5. 定位仅用于本次查询，绝不存储用户的精确位置。

---

## 🔄 更新数据集

直接编辑 `data/places.json`，或从 [Pet Life](https://github.com/) 小程序数据源重新导出：

```bash
node scripts/export_places.js /path/to/petlife-circle
```

---

## 📄 许可证

MIT — 见 [LICENSE](LICENSE)。
