"""SQLite-backed product catalog for AutoSales Engineer Pro."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote_plus

from core.models import Product

DB_PATH = Path(__file__).resolve().parents[1] / "catalog.db"


def _product_source_platform(category: str) -> str:
    return "Lazada" if category in {"networking", "compute", "storage", "cooling"} else "Shopee"


def _product_url(name: str, category: str) -> str:
    keyword = quote_plus(name)
    if _product_source_platform(category) == "Lazada":
        return f"https://www.lazada.com.my/catalog/?q={keyword}"
    return f"https://shopee.com.my/search?keyword={keyword}"


SEED_PRODUCTS: list[dict[str, Any]] = [
    {"id": "prod_net_001", "name": "Cisco SG350-28 Managed Switch", "category": "networking", "price_myr": 2850, "specs": {"ports": 28, "poe": True, "layer": "L3", "throughput": "56Gbps"}, "brand": "Cisco", "available_regions": ["KL", "Penang", "Johor", "nationwide"], "compatible_with": ["prod_net_003", "prod_net_005", "prod_cmp_001"]},
    {"id": "prod_net_002", "name": "Ubiquiti UniFi Dream Machine Pro", "category": "networking", "price_myr": 1950, "specs": {"wan_ports": 1, "lan_ports": 8, "vpn": True, "throughput": "3.5Gbps"}, "brand": "Ubiquiti", "available_regions": ["KL", "Penang", "Johor", "nationwide"], "compatible_with": ["prod_net_003", "prod_net_006"]},
    {"id": "prod_net_003", "name": "Ubiquiti UniFi AP WiFi 6 Pro", "category": "networking", "price_myr": 1100, "specs": {"standard": "WiFi6", "max_clients": 300, "coverage_sqft": 2500, "poe": True}, "brand": "Ubiquiti", "available_regions": ["nationwide"], "compatible_with": ["prod_net_001", "prod_net_002"]},
    {"id": "prod_net_004", "name": "TP-Link TL-SG1024D 24-Port Switch", "category": "networking", "price_myr": 420, "specs": {"ports": 24, "poe": False, "layer": "L2", "throughput": "48Gbps"}, "brand": "TP-Link", "available_regions": ["nationwide"], "compatible_with": ["prod_net_001", "prod_net_002", "prod_net_005"]},
    {"id": "prod_net_005", "name": "Cisco RV345 Dual WAN Router", "category": "networking", "price_myr": 1650, "specs": {"wan_ports": 2, "lan_ports": 16, "vpn": True, "firewall": True}, "brand": "Cisco", "available_regions": ["KL", "Johor", "Penang"], "compatible_with": ["prod_net_001", "prod_net_004"]},
    {"id": "prod_net_006", "name": "Fortinet FortiGate 60F Firewall", "category": "networking", "price_myr": 4200, "specs": {"throughput": "10Gbps", "vpn": True, "ids_ips": True, "users": 200}, "brand": "Fortinet", "available_regions": ["KL", "Penang", "Johor"], "compatible_with": ["prod_net_002", "prod_net_001"]},
    {"id": "prod_net_007", "name": "Ubiquiti EdgeRouter X", "category": "networking", "price_myr": 350, "specs": {"ports": 5, "throughput": "1Gbps", "routing": "advanced"}, "brand": "Ubiquiti", "available_regions": ["nationwide"], "compatible_with": ["prod_net_003", "prod_net_004"]},
    {"id": "prod_net_008", "name": "Netgear ProSAFE GS308E 8-Port", "category": "networking", "price_myr": 280, "specs": {"ports": 8, "poe": False, "layer": "L2", "throughput": "16Gbps"}, "brand": "Netgear", "available_regions": ["nationwide"], "compatible_with": ["prod_net_001", "prod_net_004"]},
    {"id": "prod_cmp_001", "name": "Dell PowerEdge R250 Server", "category": "compute", "price_myr": 9800, "specs": {"cpu": "Xeon E-2334", "ram_gb": 16, "storage_tb": 2, "rack_units": 1}, "brand": "Dell", "available_regions": ["KL", "Penang", "Johor"], "compatible_with": ["prod_sto_001", "prod_sto_004", "prod_net_001"]},
    {"id": "prod_cmp_002", "name": "HP ProLiant MicroServer Gen10 Plus", "category": "compute", "price_myr": 5200, "specs": {"cpu": "Xeon E-2224", "ram_gb": 16, "bays": 4, "form": "tower"}, "brand": "HP", "available_regions": ["KL", "Penang", "Johor", "Sabah", "Sarawak"], "compatible_with": ["prod_sto_001", "prod_sto_002"]},
    {"id": "prod_cmp_003", "name": "Lenovo ThinkCentre M70q Tiny", "category": "compute", "price_myr": 2100, "specs": {"cpu": "i5-12400T", "ram_gb": 8, "ssd_gb": 256, "form": "tiny"}, "brand": "Lenovo", "available_regions": ["nationwide"], "compatible_with": ["prod_dsp_001", "prod_per_001", "prod_per_002"]},
    {"id": "prod_cmp_004", "name": "Intel NUC 13 Pro", "category": "compute", "price_myr": 2800, "specs": {"cpu": "i7-1360P", "ram_gb": 16, "ssd_gb": 512, "thunderbolt": True}, "brand": "Intel", "available_regions": ["KL", "Penang", "Johor"], "compatible_with": ["prod_dsp_002", "prod_per_001"]},
    {"id": "prod_cmp_005", "name": "Dell OptiPlex 7010 Desktop", "category": "compute", "price_myr": 2650, "specs": {"cpu": "i5-13500", "ram_gb": 16, "ssd_gb": 512, "form": "sff"}, "brand": "Dell", "available_regions": ["nationwide"], "compatible_with": ["prod_dsp_001", "prod_per_001", "prod_per_002"]},
    {"id": "prod_cmp_006", "name": "HP EliteDesk 800 G9 Mini", "category": "compute", "price_myr": 3100, "specs": {"cpu": "i7-12700", "ram_gb": 16, "ssd_gb": 512, "vPro": True}, "brand": "HP", "available_regions": ["KL", "Penang", "Johor"], "compatible_with": ["prod_dsp_002", "prod_per_001"]},
    {"id": "prod_cmp_007", "name": "Raspberry Pi 4 Model B 8GB", "category": "compute", "price_myr": 320, "specs": {"cpu": "Cortex-A72", "ram_gb": 8, "gpio": True, "use": "iot_edge"}, "brand": "Raspberry Pi", "available_regions": ["nationwide"], "compatible_with": ["prod_net_007", "prod_net_008"]},
    {"id": "prod_sto_001", "name": "Synology DS923+ NAS 4-bay", "category": "storage", "price_myr": 3450, "specs": {"bays": 4, "max_capacity_tb": 72, "raid": ["0", "1", "5", "6"], "cache": True}, "brand": "Synology", "available_regions": ["KL", "Penang", "Johor"], "compatible_with": ["prod_sto_002", "prod_sto_003", "prod_cmp_001"]},
    {"id": "prod_sto_002", "name": "WD Red Pro 4TB HDD", "category": "storage", "price_myr": 520, "specs": {"capacity_tb": 4, "rpm": 7200, "cache_mb": 256, "nas_optimized": True}, "brand": "Western Digital", "available_regions": ["nationwide"], "compatible_with": ["prod_sto_001", "prod_sto_005", "prod_cmp_002"]},
    {"id": "prod_sto_003", "name": "Seagate IronWolf 6TB HDD", "category": "storage", "price_myr": 680, "specs": {"capacity_tb": 6, "rpm": 7200, "cache_mb": 256, "nas_optimized": True}, "brand": "Seagate", "available_regions": ["nationwide"], "compatible_with": ["prod_sto_001", "prod_sto_005"]},
    {"id": "prod_sto_004", "name": "Samsung 980 Pro 1TB NVMe SSD", "category": "storage", "price_myr": 480, "specs": {"capacity_gb": 1000, "read_mbps": 7000, "write_mbps": 5000, "nvme": True}, "brand": "Samsung", "available_regions": ["nationwide"], "compatible_with": ["prod_cmp_001", "prod_cmp_005", "prod_cmp_006"]},
    {"id": "prod_sto_005", "name": "QNAP TS-453E NAS 4-bay", "category": "storage", "price_myr": 2950, "specs": {"bays": 4, "max_capacity_tb": 72, "hdmi": True, "2p5gbe": True}, "brand": "QNAP", "available_regions": ["KL", "Penang", "Johor", "Sabah"], "compatible_with": ["prod_sto_002", "prod_sto_003"]},
    {"id": "prod_sto_006", "name": "Western Digital 2TB External USB", "category": "storage", "price_myr": 290, "specs": {"capacity_tb": 2, "interface": "USB 3.0", "portable": True}, "brand": "Western Digital", "available_regions": ["nationwide"], "compatible_with": ["prod_cmp_003", "prod_cmp_005", "prod_cmp_007"]},
    {"id": "prod_dsp_001", "name": "Dell P2422H 24\" FHD Monitor", "category": "display", "price_myr": 780, "specs": {"size_inch": 24, "resolution": "1920x1080", "panel": "IPS", "ports": ["HDMI", "DP", "VGA"]}, "brand": "Dell", "available_regions": ["nationwide"], "compatible_with": ["prod_cmp_003", "prod_cmp_005"]},
    {"id": "prod_dsp_002", "name": "LG 27UK850-W 27\" 4K Monitor", "category": "display", "price_myr": 1650, "specs": {"size_inch": 27, "resolution": "3840x2160", "panel": "IPS", "usb_c": True}, "brand": "LG", "available_regions": ["KL", "Penang", "Johor"], "compatible_with": ["prod_cmp_004", "prod_cmp_006"]},
    {"id": "prod_dsp_003", "name": "Samsung 32\" Curved Business Monitor", "category": "display", "price_myr": 1350, "specs": {"size_inch": 32, "resolution": "2560x1440", "panel": "VA", "curved": True}, "brand": "Samsung", "available_regions": ["KL", "Penang", "Johor"], "compatible_with": ["prod_cmp_005", "prod_cmp_006"]},
    {"id": "prod_dsp_004", "name": "BenQ EW2480 24\" Eye-Care Monitor", "category": "display", "price_myr": 720, "specs": {"size_inch": 24, "resolution": "1920x1080", "eye_care": True, "hdr": True}, "brand": "BenQ", "available_regions": ["nationwide"], "compatible_with": ["prod_cmp_003", "prod_cmp_005"]},
    {"id": "prod_per_001", "name": "Logitech MX Keys Business Keyboard", "category": "peripheral", "price_myr": 580, "specs": {"wireless": True, "backlit": True, "multi_device": 3, "layout": "full"}, "brand": "Logitech", "available_regions": ["nationwide"], "compatible_with": ["prod_per_002", "prod_cmp_003", "prod_cmp_005"]},
    {"id": "prod_per_002", "name": "Logitech MX Master 3S Mouse", "category": "peripheral", "price_myr": 420, "specs": {"wireless": True, "dpi": 8000, "multi_device": 3, "silent": True}, "brand": "Logitech", "available_regions": ["nationwide"], "compatible_with": ["prod_per_001", "prod_cmp_003", "prod_cmp_005"]},
    {"id": "prod_per_003", "name": "Logitech C920 HD Pro Webcam", "category": "peripheral", "price_myr": 380, "specs": {"resolution": "1080p", "fps": 30, "autofocus": True, "stereo_mic": True}, "brand": "Logitech", "available_regions": ["nationwide"], "compatible_with": ["prod_per_004", "prod_cmp_003", "prod_cmp_005"]},
    {"id": "prod_per_004", "name": "Jabra Evolve2 55 Wireless Headset", "category": "peripheral", "price_myr": 1250, "specs": {"wireless": True, "anc": True, "battery_hrs": 36, "uc_certified": True}, "brand": "Jabra", "available_regions": ["KL", "Penang", "Johor"], "compatible_with": ["prod_per_003"]},
    {"id": "prod_per_005", "name": "Logitech MeetUp Conference Camera", "category": "peripheral", "price_myr": 3200, "specs": {"fov_deg": 120, "resolution": "4K", "built_in_mic": True, "speakerphone": True}, "brand": "Logitech", "available_regions": ["KL", "Penang", "Johor", "Sabah", "Sarawak"], "compatible_with": ["prod_per_003", "prod_per_004"]},
    {"id": "prod_pwr_001", "name": "APC Smart-UPS 1500VA LCD", "category": "power", "price_myr": 2100, "specs": {"va": 1500, "watts": 1000, "outlets": 8, "lcd": True, "runtime_min": 11}, "brand": "APC", "available_regions": ["nationwide"], "compatible_with": ["prod_cmp_001", "prod_cmp_002", "prod_net_001"]},
    {"id": "prod_pwr_002", "name": "APC Back-UPS Pro 1200VA", "category": "power", "price_myr": 750, "specs": {"va": 1200, "watts": 720, "outlets": 6, "surge_protection": True}, "brand": "APC", "available_regions": ["nationwide"], "compatible_with": ["prod_cmp_003", "prod_cmp_005", "prod_net_004"]},
    {"id": "prod_pwr_003", "name": "CyberPower CP1500EPFCLCD UPS", "category": "power", "price_myr": 980, "specs": {"va": 1500, "watts": 900, "outlets": 8, "pure_sine": True}, "brand": "CyberPower", "available_regions": ["KL", "Penang", "Johor"], "compatible_with": ["prod_cmp_001", "prod_net_001"]},
    {"id": "prod_pwr_004", "name": "Eaton 5PX 1500i UPS", "category": "power", "price_myr": 3200, "specs": {"va": 1500, "watts": 1350, "network_card": True, "hot_swap": True}, "brand": "Eaton", "available_regions": ["KL", "Penang", "Johor"], "compatible_with": ["prod_cmp_001", "prod_sto_001"]},
    {"id": "prod_sft_001", "name": "Microsoft 365 Business Standard (per user/year)", "category": "software_license", "price_myr": 680, "specs": {"users": 1, "apps": ["Word", "Excel", "PowerPoint", "Teams"], "storage_gb": 1000, "email": True}, "brand": "Microsoft", "available_regions": ["nationwide"], "compatible_with": ["prod_cmp_003", "prod_cmp_005", "prod_cmp_006"]},
    {"id": "prod_sft_002", "name": "Microsoft 365 Business Basic (per user/year)", "category": "software_license", "price_myr": 210, "specs": {"users": 1, "apps": ["Teams", "OneDrive"], "web_only": True, "storage_gb": 1000}, "brand": "Microsoft", "available_regions": ["nationwide"], "compatible_with": ["prod_cmp_003", "prod_cmp_005"]},
    {"id": "prod_sft_003", "name": "Veeam Backup Essentials (per year)", "category": "software_license", "price_myr": 4800, "specs": {"vms": 10, "physical_servers": 10, "cloud_backup": True}, "brand": "Veeam", "available_regions": ["KL", "Penang", "Johor"], "compatible_with": ["prod_cmp_001", "prod_sto_001"]},
    {"id": "prod_col_001", "name": "APC NetShelter SX 12U Rack", "category": "cooling", "price_myr": 3800, "specs": {"rack_units": 12, "depth_mm": 900, "cooling": "passive", "lockable": True}, "brand": "APC", "available_regions": ["KL", "Penang", "Johor"], "compatible_with": ["prod_cmp_001", "prod_pwr_001", "prod_pwr_004"]},
    {"id": "prod_col_002", "name": "Noctua NH-U12S CPU Cooler", "category": "cooling", "price_myr": 280, "specs": {"tdp_w": 250, "fans": 1, "noise_db": 22.4, "socket": ["LGA1700", "AM5"]}, "brand": "Noctua", "available_regions": ["nationwide"], "compatible_with": ["prod_cmp_001", "prod_cmp_002"]},
    {"id": "prod_col_003", "name": "Corsair iCUE H100i Elite AIO Cooler", "category": "cooling", "price_myr": 520, "specs": {"radiator_mm": 240, "tdp_w": 300, "rgb": True, "socket": ["LGA1700", "AM5"]}, "brand": "Corsair", "available_regions": ["KL", "Penang", "Johor"], "compatible_with": ["prod_cmp_001"]},
]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create and seed the product catalog if needed."""
    db_exists = DB_PATH.exists()
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price_myr REAL NOT NULL,
                specs TEXT NOT NULL,
                compatible_with TEXT NOT NULL,
                available_regions TEXT NOT NULL,
                in_stock INTEGER NOT NULL,
                brand TEXT NOT NULL,
                url TEXT NOT NULL,
                source_platform TEXT NOT NULL
            )
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if db_exists and count:
            conn.executemany(
                "UPDATE products SET url = :url, source_platform = :source_platform WHERE id = :id",
                [
                    {
                        "id": p["id"],
                        "url": _product_url(p["name"], p["category"]),
                        "source_platform": _product_source_platform(p["category"]),
                    }
                    for p in SEED_PRODUCTS
                ],
            )
            conn.commit()
            return
        conn.execute("DELETE FROM products")
        conn.executemany(
            """
            INSERT INTO products VALUES (
                :id, :name, :category, :price_myr, :specs, :compatible_with,
                :available_regions, :in_stock, :brand, :url, :source_platform
            )
            """,
            [
                {
                    **p,
                    "price_myr": float(p["price_myr"]),
                    "specs": json.dumps(p["specs"]),
                    "compatible_with": json.dumps(p["compatible_with"]),
                    "available_regions": json.dumps(p["available_regions"]),
                    "in_stock": 1,
                    "url": _product_url(p["name"], p["category"]),
                    "source_platform": _product_source_platform(p["category"]),
                }
                for p in SEED_PRODUCTS
            ],
        )
        conn.commit()


def _row_to_product(row: sqlite3.Row) -> Product:
    data = dict(row)
    data["specs"] = json.loads(data["specs"])
    data["compatible_with"] = json.loads(data["compatible_with"])
    data["available_regions"] = json.loads(data["available_regions"])
    data["in_stock"] = bool(data["in_stock"])
    return Product.model_validate(data)


def search_products(
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    specs_filter: Optional[dict[str, Any]] = None,
    in_stock_only: bool = True,
) -> list[Product]:
    """Search products by category, price, stock, and simple spec equality."""
    init_db()
    clauses: list[str] = []
    params: list[Any] = []
    if category:
        clauses.append("category = ?")
        params.append(category)
    if max_price is not None:
        clauses.append("price_myr <= ?")
        params.append(max_price)
    if min_price is not None:
        clauses.append("price_myr >= ?")
        params.append(min_price)
    if in_stock_only:
        clauses.append("in_stock = 1")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _connect() as conn:
        rows = conn.execute(f"SELECT * FROM products {where} ORDER BY price_myr ASC", params).fetchall()
    products = [_row_to_product(row) for row in rows]
    if specs_filter:
        products = [
            product
            for product in products
            if all(product.specs.get(key) == value for key, value in specs_filter.items())
        ]
    return products


def get_product_by_id(product_id: str) -> Optional[Product]:
    """Return a single product by ID."""
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return _row_to_product(row) if row else None


def get_all_categories() -> list[str]:
    """Return all distinct catalog categories."""
    init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT DISTINCT category FROM products ORDER BY category").fetchall()
    return [row[0] for row in rows]


def get_catalog_stats() -> dict:
    """Return catalog counts and price ranges."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT category, COUNT(*) count, MIN(price_myr) min_price, MAX(price_myr) max_price "
            "FROM products GROUP BY category ORDER BY category"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*), MIN(price_myr), MAX(price_myr) FROM products").fetchone()
    return {
        "total_products": total[0],
        "min_price": total[1],
        "max_price": total[2],
        "categories": {
            row["category"]: {
                "count": row["count"],
                "min_price": row["min_price"],
                "max_price": row["max_price"],
            }
            for row in rows
        },
    }
