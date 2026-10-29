#!/usr/bin/env python3
"""生成样例运营数据库 data/ops.db 与数据字典 data/schema.json。

固定随机种子，可重复运行，结果确定。生成的 ops.db 不入库（见 .gitignore）。

数据里刻意埋了两处「坑」，供演示与评测使用：
  1. 政策 ↔ 数据冲突：制度规定一线城市住宿每晚上限 600 元，
     但销售一部一线城市实际住宿均价高于该标准；
     同理，制度规定 P2 工单首次响应 2 小时，华东区实际平均响应超过 2 小时。
  2. 小样本异常：西北区第三季度仅 3 张订单（且均为大额硬件单），
     客单价会显著高于其他大区，但样本量不足以支撑结论。
"""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "ops.db"
SCHEMA_PATH = BASE_DIR / "schema.json"

RNG = random.Random(20260701)

Q3_START = date(2026, 7, 1)
Q3_END = date(2026, 9, 30)

REGIONS = [
    ("R01", "华北区", "北区"),
    ("R02", "华东区", "东区"),
    ("R03", "华南区", "南区"),
    ("R04", "西南区", "西区"),
    ("R05", "西北区", "西区"),
]

# (product_id, name, line, unit_price_low, unit_price_high, qty_low, qty_high, weight)
PRODUCTS = [
    ("P01", "机架式服务器", "企业硬件", 300_000, 800_000, 1, 3, 8),
    ("P02", "存储阵列", "企业硬件", 180_000, 600_000, 1, 2, 6),
    ("P03", "工作站", "终端", 12_000, 45_000, 2, 10, 16),
    ("P04", "商用笔记本", "终端", 5_000, 15_000, 3, 30, 40),
    ("P05", "显示器", "终端", 800, 3_500, 10, 80, 30),
]

CHANNELS = ["直销", "渠道", "电商"]

DEPARTMENTS = [("销售一部", 40), ("销售二部", 25), ("售前支持部", 20), ("渠道部", 15)]
EXPENSE_TYPES = [("住宿", 40), ("餐饮", 20), ("交通", 25), ("招待", 15)]
PRIORITIES = [("P1", 8), ("P2", 52), ("P3", 40)]

DDL = """
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS fact_expense;
DROP TABLE IF EXISTS fact_ticket;
DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_region;

CREATE TABLE dim_region (
    region_id    TEXT PRIMARY KEY,
    region_name  TEXT NOT NULL,
    region_group TEXT NOT NULL
);

CREATE TABLE dim_product (
    product_id   TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    product_line TEXT NOT NULL
);

CREATE TABLE fact_sales (
    order_id   TEXT PRIMARY KEY,
    order_date TEXT NOT NULL,
    region_id  TEXT NOT NULL REFERENCES dim_region(region_id),
    product_id TEXT NOT NULL REFERENCES dim_product(product_id),
    channel    TEXT NOT NULL,
    quantity   INTEGER NOT NULL,
    amount     REAL NOT NULL
);

CREATE TABLE fact_ticket (
    ticket_id        TEXT PRIMARY KEY,
    order_id         TEXT NOT NULL REFERENCES fact_sales(order_id),
    region_id        TEXT NOT NULL REFERENCES dim_region(region_id),
    priority         TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    first_response_min REAL,
    resolved_hours   REAL,
    satisfaction     REAL
);

CREATE TABLE fact_expense (
    expense_id     TEXT PRIMARY KEY,
    employee_dept  TEXT NOT NULL,
    expense_type   TEXT NOT NULL,
    city_tier      TEXT,
    amount         REAL NOT NULL,
    nights         INTEGER,
    submitted_date TEXT NOT NULL,
    approved_date  TEXT
);

CREATE INDEX idx_sales_region ON fact_sales(region_id);
CREATE INDEX idx_sales_date ON fact_sales(order_date);
CREATE INDEX idx_ticket_region ON fact_ticket(region_id);
CREATE INDEX idx_expense_dept ON fact_expense(employee_dept);
"""

SCHEMA_DOC = {
    "tables": {
        "dim_region": {
            "comment": "大区维度表，一行一个大区",
            "columns": {
                "region_id": "大区编码，主键",
                "region_name": "大区名称，如「华东区」",
                "region_group": "大区所属片区，如「东区」",
            },
        },
        "dim_product": {
            "comment": "产品维度表，一行一个产品",
            "columns": {
                "product_id": "产品编码，主键",
                "product_name": "产品名称，如「机架式服务器」",
                "product_line": "产品线：企业硬件 / 终端",
            },
        },
        "fact_sales": {
            "comment": "销售订单事实表，一行一张订单，覆盖 2026 年第三季度",
            "columns": {
                "order_id": "订单号，主键",
                "order_date": "下单日期，格式 YYYY-MM-DD",
                "region_id": "下单大区，关联 dim_region",
                "product_id": "产品，关联 dim_product",
                "channel": "销售渠道：直销 / 渠道 / 电商",
                "quantity": "数量（台）",
                "amount": "订单金额（元，含税）",
            },
        },
        "fact_ticket": {
            "comment": "售后服务工单事实表，一行一张工单；first_response_min 为首次响应时长（分钟）",
            "columns": {
                "ticket_id": "工单号，主键",
                "order_id": "关联订单号，关联 fact_sales",
                "region_id": "工单所属大区，关联 dim_region",
                "priority": "工单等级：P1 重大故障 / P2 一般故障 / P3 咨询类",
                "created_at": "工单创建时间",
                "first_response_min": "首次响应时长（分钟），自然时间口径",
                "resolved_hours": "解决时长（小时）",
                "satisfaction": "满意度评分，1—5 分",
            },
        },
        "fact_expense": {
            "comment": "费用报销单事实表；住宿类报销的每晚报销金额 = amount / nights",
            "columns": {
                "expense_id": "报销单号，主键",
                "employee_dept": "报销人所属部门",
                "expense_type": "费用类型：住宿 / 餐饮 / 交通 / 招待",
                "city_tier": "城市等级：一线 / 非一线（仅住宿、餐饮类有值）",
                "amount": "报销金额（元）",
                "nights": "住宿晚数（仅住宿类有值，其余为 NULL）",
                "submitted_date": "提交日期",
                "approved_date": "审批通过日期",
            },
        },
    }
}


def weighted_choice(pairs):
    items = [p[0] for p in pairs]
    weights = [p[1] for p in pairs]
    return RNG.choices(items, weights=weights, k=1)[0]


def rand_date(start: date, end: date) -> date:
    return start + timedelta(days=RNG.randint(0, (end - start).days))


def build_sales():
    rows = []
    seq = 0

    for region_id, region_name, _group in REGIONS:
        if region_id == "R05":
            # 小样本埋点：仅 3 张大额硬件单
            for unit_price in (520_000, 590_000, 660_000):
                seq += 1
                rows.append(
                    (
                        f"SO{seq:06d}",
                        rand_date(Q3_START, Q3_END).isoformat(),
                        region_id,
                        "P01",
                        "直销",
                        2,
                        unit_price * 2,
                    )
                )
            continue

        for _ in range(RNG.randint(55, 75)):
            seq += 1
            product = weighted_choice([(p, p[7]) for p in PRODUCTS])
            pid, _name, _line, lo, hi, qlo, qhi = product[:7]
            unit_price = RNG.uniform(lo, hi)
            qty = RNG.randint(qlo, qhi)
            rows.append(
                (
                    f"SO{seq:06d}",
                    rand_date(Q3_START, Q3_END).isoformat(),
                    region_id,
                    pid,
                    weighted_choice([(c, 1) for c in CHANNELS]),
                    qty,
                    round(unit_price * qty, 2),
                )
            )
    return rows


def build_tickets(sales_rows):
    rows = []
    seq = 0
    for order_id, order_date, region_id, _pid, _channel, _qty, _amount in sales_rows:
        prob = 0.50 if region_id == "R02" else 0.35
        if RNG.random() > prob:
            continue
        seq += 1
        priority = weighted_choice(PRIORITIES)

        created = date.fromisoformat(order_date) + timedelta(days=RNG.randint(0, 20))
        if created > Q3_END:
            created = Q3_END

        if region_id == "R02":
            # 冲突埋点：华东区首次响应普遍超过制度要求
            response = {"P1": RNG.uniform(25, 60), "P2": RNG.uniform(150, 260), "P3": RNG.uniform(180, 320)}[priority]
            resolve = {"P1": RNG.uniform(2, 8), "P2": RNG.uniform(10, 40), "P3": RNG.uniform(30, 96)}[priority]
            satisfaction = round(RNG.uniform(3.0, 4.6), 1)
        else:
            response = {"P1": RNG.uniform(8, 28), "P2": RNG.uniform(25, 110), "P3": RNG.uniform(40, 230)}[priority]
            resolve = {"P1": RNG.uniform(1, 5), "P2": RNG.uniform(6, 28), "P3": RNG.uniform(20, 80)}[priority]
            satisfaction = round(RNG.uniform(3.6, 5.0), 1)

        rows.append(
            (
                f"TK{seq:06d}",
                order_id,
                region_id,
                priority,
                created.isoformat(),
                round(response, 1),
                round(resolve, 1),
                satisfaction,
            )
        )
    return rows


def build_expenses():
    rows = []
    for i in range(1, 221):
        dept = weighted_choice(DEPARTMENTS)
        etype = weighted_choice(EXPENSE_TYPES)
        tier = "一线" if RNG.random() < 0.45 else "非一线"

        nights = None
        if etype == "住宿":
            nights = RNG.randint(1, 4)
            if dept == "销售一部" and tier == "一线":
                # 冲突埋点：高于制度规定的 600 元/晚上限
                nightly = RNG.uniform(650, 820)
            elif tier == "一线":
                nightly = RNG.uniform(380, 580)
            else:
                nightly = RNG.uniform(300, 440)
            amount = nightly * nights
        elif etype == "餐饮":
            amount = RNG.uniform(100, 400)
        elif etype == "交通":
            amount = RNG.uniform(60, 600)
        else:
            amount = RNG.uniform(500, 3_500)

        submitted = rand_date(Q3_START, Q3_END)
        approved = submitted + timedelta(days=RNG.randint(1, 20))

        rows.append(
            (
                f"BX{i:06d}",
                dept,
                etype,
                tier if etype in ("住宿", "餐饮") else None,
                round(amount, 2),
                nights,
                submitted.isoformat(),
                approved.isoformat(),
            )
        )
    return rows


def main():
    sales_rows = build_sales()
    ticket_rows = build_tickets(sales_rows)
    expense_rows = build_expenses()

    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(DDL)
        conn.executemany("INSERT INTO dim_region VALUES (?, ?, ?)", REGIONS)
        conn.executemany(
            "INSERT INTO dim_product VALUES (?, ?, ?)",
            [(p[0], p[1], p[2]) for p in PRODUCTS],
        )
        conn.executemany("INSERT INTO fact_sales VALUES (?, ?, ?, ?, ?, ?, ?)", sales_rows)
        conn.executemany("INSERT INTO fact_ticket VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ticket_rows)
        conn.executemany("INSERT INTO fact_expense VALUES (?, ?, ?, ?, ?, ?, ?, ?)", expense_rows)
        conn.commit()

        # ---- 自检：埋点必须成立 ----
        cur = conn.cursor()
        regional = cur.execute(
            "SELECT region_id, COUNT(*), ROUND(AVG(amount), 2) "
            "FROM fact_sales GROUP BY region_id ORDER BY region_id"
        ).fetchall()
        nw_count = dict((r[0], r[1]) for r in regional)["R05"]
        assert nw_count == 3, f"西北区应只有 3 单，实际 {nw_count}"

        east_p2 = cur.execute(
            "SELECT ROUND(AVG(first_response_min), 1) FROM fact_ticket "
            "WHERE region_id = 'R02' AND priority = 'P2'"
        ).fetchone()[0]
        assert east_p2 > 120, f"华东区 P2 平均首次响应应超过 120 分钟，实际 {east_p2}"

        nightly = cur.execute(
            "SELECT ROUND(AVG(amount * 1.0 / nights), 2) FROM fact_expense "
            "WHERE employee_dept = '销售一部' AND expense_type = '住宿' AND city_tier = '一线'"
        ).fetchone()[0]
        assert nightly > 600, f"销售一部一线住宿均价应超过 600 元/晚，实际 {nightly}"

        print(f"已生成 {DB_PATH}")
        print(f"  订单 {len(sales_rows)} 张 / 工单 {len(ticket_rows)} 张 / 报销单 {len(expense_rows)} 张")
        print("  各大区订单数与客单价：")
        for region_id, cnt, avg_amount in regional:
            name = dict((r[0], r[1]) for r in REGIONS)[region_id]
            print(f"    {region_id} {name}: {cnt} 单，客单价 {avg_amount:,.2f} 元")
        print(f"  华东区 P2 平均首次响应：{east_p2} 分钟（制度要求 ≤120 分钟）")
        print(f"  销售一部一线住宿均价：{nightly:,.2f} 元/晚（制度要求 ≤600 元/晚）")
    finally:
        conn.close()

    SCHEMA_PATH.write_text(
        json.dumps(SCHEMA_DOC, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"已生成 {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
