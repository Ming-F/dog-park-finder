#!/usr/bin/env node
// 从小程序 petlife-circle/utils/demo-data.js 抽取 PLACES，生成 data/places.json（skill 种子数据）。
// 用法：node export_places.js [小程序路径] [输出路径]
// 默认：小程序路径 = ../../../Desktop/workbuddy/petlife-circle（相对本脚本所在 scripts/）
//       输出路径 = ../data/places.json
const path = require('path');
const fs = require('fs');

const args = process.argv.slice(2);
const projectDir = args[0] || path.join(process.env.HOME || '~', 'Desktop/workbuddy/petlife-circle');
const outPath = args[1] || path.resolve(__dirname, '../data/places.json');

const demoPath = path.join(projectDir, 'utils/demo-data.js');
if (!fs.existsSync(demoPath)) {
    console.error('找不到小程序数据文件：' + demoPath);
    console.error('请用第一个参数指定小程序根目录。');
    process.exit(1);
}

const demo = require(demoPath);
const seed = demo.buildSeed();

// skill 只保留查询与判定所需的核心字段，去掉小程序渲染专用的字段。
const CORE = [
    'id', 'name', 'shortName', 'city', 'category', 'district', 'address',
    'openTime', 'ruleLevel', 'rules', 'tips', 'source', 'official',
    'verifiedAt', 'latitude', 'longitude', 'coordEstimated'
];

const places = seed.places.map(function (p) {
    const out = {};
    CORE.forEach(function (k) {
        if (p[k] !== undefined && p[k] !== null) {
            out[k] = p[k];
        }
    });
    // 遛狗路线：挂载在公园下的建议路线（起点/途经/终点 + 长度 + 路面 + 适用犬型）。
    out.routes = Array.isArray(p.routes) ? p.routes : [];
    return out;
});

const payload = {
    updatedAt: '2026-11',
    description: '宠物友好公园/地点数据集（含开放时间、遛狗限制、来源分级）。数据来源与核验信息见 references/places-schema.md。',
    policyNote: '北京市公园条例修订草案（2025-11 二审）拟规定：禁止烈性犬、大型犬进入任何公园，禁止携犬进入历史名园；其他公园由管理单位决定是否允许携犬及允许进入的区域、时段。',
    places: places
};

fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, JSON.stringify(payload, null, 2) + '\n', 'utf8');

const cities = {};
places.forEach(function (p) { cities[p.city] = (cities[p.city] || 0) + 1; });
console.log('已导出 ' + places.length + ' 处地点 → ' + outPath);
console.log('城市分布：' + JSON.stringify(cities));
