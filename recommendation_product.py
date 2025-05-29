import requests
import urllib3
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import os
from dotenv import load_dotenv

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

def build_recommendation_data(token=None):
    products = fetch_all_items(os.getenv('PRODUCT_API_URL'), token)
    orders = fetch_all_items(os.getenv('ORDER_API_URL'), token)
    users = fetch_all_items(os.getenv('USER_API_URL'), token)

    user_ids = [u['id'] for u in users]
    product_ids = [p['id'] for p in products]
    user_id_to_index = {uid: i for i, uid in enumerate(user_ids)}
    product_id_to_index = {pid: i for i, pid in enumerate(product_ids)}
    product_map = {p['id']: p for p in products}  # Dùng để tra nhanh thông tin đầy đủ sản phẩm

    num_users = len(user_ids)
    num_products = len(product_ids)
    user_product_matrix = np.zeros((num_users, num_products))

    for order in orders:
        uid = order.get('userId')
        if uid not in user_id_to_index:
            continue
        u_idx = user_id_to_index[uid]
        for item in order.get('orderItems', []):
            pid = item.get('productId')
            if pid not in product_id_to_index:
                continue
            p_idx = product_id_to_index[pid]
            quantity = item.get('quantity', 1)
            user_product_matrix[u_idx, p_idx] += quantity

    user_total_purchases = user_product_matrix.sum(axis=1)
    active_user_indices = np.where(user_total_purchases > 0)[0]
    filtered_matrix = user_product_matrix[active_user_indices]

    if len(active_user_indices) < 2:
        return {}, {}

    scores = []
    K_range = range(2, min(10, len(active_user_indices)))
    for k in K_range:
        kmeans = KMeans(n_clusters=k, random_state=42)
        labels = kmeans.fit_predict(filtered_matrix)
        score = silhouette_score(filtered_matrix, labels)
        scores.append(score)

    best_k = K_range[np.argmax(scores)]
    kmeans = KMeans(n_clusters=best_k, random_state=42)
    clusters = kmeans.fit_predict(filtered_matrix)

    user_clusters = {}
    for idx, cluster_label in zip(active_user_indices, clusters):
        user_id = user_ids[idx]
        user_clusters[user_id] = cluster_label

    cluster_top_products = {}
    for cluster_id in range(best_k):
        cluster_user_indices = [idx for idx, label in zip(active_user_indices, clusters) if label == cluster_id]
        cluster_products_sum = user_product_matrix[cluster_user_indices].sum(axis=0)

        top_indices = cluster_products_sum.argsort()[::-1][:4]
        top_products = [product_map[product_ids[i]] for i in top_indices if cluster_products_sum[i] > 0]

        cluster_top_products[cluster_id] = top_products

    return user_clusters, cluster_top_products
