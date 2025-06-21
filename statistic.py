import os
from dotenv import load_dotenv
import jwt
import requests
import urllib3
from collections import defaultdict
from dateutil import parser
from datetime import datetime

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_all_items(api_url: str, token: str = None):
    all_items = []
    current_page = 1

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    while True:
        try:
            url = f"{api_url}?pageIndex={current_page}&pageSize=10000"
            response = requests.get(url, headers=headers, verify=False)
            response.raise_for_status()
            data = response.json()
            items = data["data"]["items"]
            all_items.extend(items)
            if current_page >= data["data"]["totalPages"]:
                break
            current_page += 1
        except Exception as e:
            print(f"Lỗi khi gọi API trang {current_page}: {e}")
            break
    return all_items

def get_revenue_statistics(mode="daily", token=None):
    orders = fetch_all_items(os.getenv('ORDER_API_URL'), token)

    if mode not in ("daily", "monthly", "yearly"):
        raise ValueError("Chế độ không hợp lệ. Chọn: 'daily', 'monthly' hoặc 'yearly'.")

    revenue = defaultdict(float)
    order_counts = defaultdict(int)
    canceled_orders = defaultdict(int)
    returned_orders = defaultdict(int)

    # Tổng cộng
    total_orders = 0
    total_canceled = 0
    total_returned = 0

    now = datetime.now()

    for order in orders:
        order_date = order.get("orderDate")
        if not order_date:
            continue

        try:
            dt = parser.isoparse(order_date)
        except ValueError as e:
            print("Lỗi định dạng ngày:", e)
            continue

        if mode == "daily":
            if dt.year != now.year or dt.month != now.month:
                continue
            key = dt.strftime("%Y-%m-%d")
        elif mode == "monthly":
            if dt.year != now.year:
                continue
            key = f"{dt.year}-{dt.month:02d}"
        elif mode == "yearly":
            key = str(dt.year)

        total_price = order.get("totalPrice", 0)
        status = order.get("status", "Unknown")

        if status == "Canceled":
            canceled_orders[key] += 1
            total_canceled += 1
            continue
        elif status in ("Returned", "Exchanged"):
            returned_orders[key] += 1
            total_returned += 1
            continue
        else:
            revenue[key] += total_price
            order_counts[key] += 1
            total_orders += 1

    return {
        "revenue": dict(revenue),
        "order_count": dict(order_counts),
        "canceled_orders": dict(canceled_orders),
        "returned_orders": dict(returned_orders),
        "totals": {
            "orders": total_orders,
            "canceled": total_canceled,
            "returned": total_returned
        }
    }

def get_best_selling_products(top_n=10, mode="daily", token=None):
    orders = fetch_all_items(os.getenv('ORDER_API_URL'), token)
    products = fetch_all_items(os.getenv('PRODUCT_API_URL'), token)

    if mode not in ("daily", "monthly", "yearly"):
        raise ValueError("Mode không hợp lệ. Chọn 'daily', 'monthly' hoặc 'yearly'.")

    product_map = {p["id"]: p for p in products}
    grouped_sales = defaultdict(lambda: defaultdict(int))
    now = datetime.now()

    for order in orders:
        order_date = order.get("orderDate")
        status = order.get("status", "")
        if not order_date or status in ("Canceled", "Returned", "Exchanged"):
            continue

        try:
            dt = parser.isoparse(order_date)
        except ValueError as e:
            print("Lỗi định dạng ngày:", e)
            continue

        if mode == "daily":
            if dt.year != now.year or dt.month != now.month:
                continue
            key = dt.strftime("%Y-%m-%d")
        elif mode == "monthly":
            if dt.year != now.year:
                continue
            key = f"{dt.year}-{dt.month:02d}"
        elif mode == "yearly":
            key = str(dt.year)

        for item in order.get("orderItems", []):
            pid = item.get("productId")
            qty = item.get("quantity", 0)
            grouped_sales[key][pid] += qty

    result = {}
    for time_key, sales in grouped_sales.items():
        sorted_sales = sorted(sales.items(), key=lambda x: x[1], reverse=True)
        top_products = [
            {**product_map[pid], "sold_quantity": qty}
            for pid, qty in sorted_sales[:top_n]
            if pid in product_map
        ]
        result[time_key] = top_products

    return result

""" stats = get_revenue_statistics()

print("==== Thống kê đơn hàng theo tháng ====")
for period in sorted(set(
    list(stats["revenue"].keys()) + 
    list(stats["canceled_orders"].keys()) + 
    list(stats["returned_orders"].keys())
)):
    rev = stats["revenue"].get(period, 0)
    count = stats["order_count"].get(period, 0)
    canceled = stats["canceled_orders"].get(period, 0)
    returned = stats["returned_orders"].get(period, 0)
    print(f"{period}: {rev} VND | {count} đơn hợp lệ | {canceled} huỷ | {returned} trả")

print(f"\nTổng đơn hợp lệ: {stats['total_orders']}")
print(f"Tổng đơn huỷ: {stats['total_canceled']}")
print(f"Tổng đơn trả hàng: {stats['total_returned']}")

result = get_best_selling_products(mode="monthly")

for period, top_items in result.items():
    print(f"\nTop sản phẩm bán chạy ({period}):")
    for p in top_items:
        print(f"- {p['name']} | Số lượng: {p['sold_quantity']}") """