# places.json 字段说明

本地已核实公园数据集 `data/places.json` 的结构。

## 顶层结构

```json
{
  "updatedAt": "2026-11",
  "description": "…",
  "policyNote": "北京市公园条例修订草案……",
  "places": [ /* 数组，每条一个公园 */ ]
}
```

## place 对象字段

| 字段 | 类型 | 含义 | 示例 |
|---|---|---|---|
| `id` | string | 唯一标识 | `place_bj_laoshan` |
| `name` | string | 全名 | 老山城市休闲公园 |
| `shortName` | string | 简称/别名 | 老山 |
| `city` | string | 城市 | 北京 |
| `category` | string | 类型 | 郊野公园 |
| `district` | string | 区/街道 | 石景山区老山街道 |
| `address` | string | 地址 | 石景山区老山南路…… |
| `openTime` | string | 开放时间 | 全天开放 / 6:00 - 21:00 |
| `ruleLevel` | string | 限制级别（枚举，见下） | 需牵绳 |
| `rules` | string | 详细规则（自然语言） | 宠物友好，需牵绳…… |
| `tips` | string | 实用贴士 | 坡度缓，有停车…… |
| `source` | string | 数据来源 | 北京旅游网 visitbeijing.com.cn |
| `official` | bool | 是否官方核实 | true |
| `verifiedAt` | string | 核验日期 | 2026-11 |
| `latitude` / `longitude` | float | 坐标（WGS84） | 39.913563 / 116.218063 |
| `coordEstimated` | bool | 坐标是否估算 | false |
| `routes` | array | 遛狗路线（可空） | 见下 |

## ruleLevel 枚举与判定

| 值 | 能否遛狗 | 说明 |
|---|---|---|
| `需牵绳` | 可（需牵绳） | 宠物友好，牵绳 + 清粪 |
| `需登记` | 可（需登记） | 需养犬登记证 + 疫苗证明 + 免责声明 |
| `限体型` | 可（限小型犬） | 仅限体重 ≤ 某阈值的宠物 |
| `分区管理` | 可（分区） | 按体型分区 |
| `封闭乐园` | 可（封闭乐园） | 封闭式宠物乐园 |
| `柔性管理` | 可（柔性管理） | 工作人员引导，错峰开放 |
| `禁止携犬` | 否 | 明确禁止进入 |

## category 枚举

郊野公园 / 城市公园 / 湿地公园 / 宠物乐园 / 景区

## routes 数组（遛狗路线）

挂在部分公园下，元素字段：

| 字段 | 含义 |
|---|---|
| `id` | 路线唯一标识（如 `route_hcw_1`） |
| `name` | 路线名 |
| `distanceM` | 长度（米） |
| `durationMin` | 预计时长（分钟） |
| `surface` | 路面（柏油路/草坪/土路/塑胶步道…） |
| `level` | 适用犬型（适合中大型犬/小型犬/所有体型…） |
| `start` / `via` / `end` | 起点 / 途经 / 终点 |
| `tips` | 贴士 |

路线是「可执行的走法描述」（起点→途经→终点），不含逐点 GPS 轨迹。

## 来源分级

- `official: true` → 官方核实（政府网、官方旅游网、党媒等），显示「官方核实」。
- `official: false` → 媒体整理（公众号、自媒体聚合），显示「媒体整理」，必须补「规则以园方现场公示为准」。
