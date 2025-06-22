from flask import Flask, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, jwt_required, get_jwt
from functools import wraps
from flask_restx import Api, Resource, Namespace, fields
import requests
from recommendation_product import build_recommendation_data
from statistic import get_revenue_statistics, get_best_selling_products
import os

app = Flask(__name__)
CORS(app)

app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
app.config['JWT_DECODE_ISSUER'] = os.getenv('JWT_DECODE_ISSUER')
app.config['JWT_DECODE_AUDIENCE'] = os.getenv('JWT_DECODE_AUDIENCE')

jwt = JWTManager(app)

authorizations = {
    'Bearer Auth': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authorization',
        'description': 'JWT Authorization header using the Bearer scheme. Example: "Bearer {token}"'
    }
}

api = Api(app,
          version='1.0',
          title='Flask API with JWT Auth',
          description='Demo API that validates JWT tokens issued by ASP.NET Core',
          authorizations=authorizations,
          security='Bearer Auth')

ns = Namespace('api', description='API operations', authorizations=authorizations, security='Bearer Auth')
api.add_namespace(ns)

ask_model = ns.model('AskModel', {
    'message': fields.String(required=True, description='Câu hỏi của người dùng')
})

rasa = os.getenv("RASA_API_URL")  # Địa chỉ API của Rasa

def role_required(*roles):
    def wrapper(fn):
        @wraps(fn)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            claims = get_jwt()
            user_role = claims.get("http://schemas.microsoft.com/ws/2008/06/identity/claims/role")

            if not user_role or user_role not in roles:
                return {"msg": "Bạn không có quyền truy cập"}, 403

            return fn(*args, **kwargs)
        return decorated_function
    return wrapper

@ns.route('/ask')
class Ask(Resource):
    @ns.expect(ask_model)
    def post(self):
        data = request.get_json()
        user_message = data.get("message", "")
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        
        if not user_message:
            return {"error": "Bạn chưa nhập câu hỏi"}, 400
        
        payload = {
            "sender": "user123",
            "message": user_message,
            "metadata": {
                "token": token
            }
        }

        response = requests.post(rasa, json=payload)
        if response.status_code == 200:
            try:
                bot_response = response.json()
                messages = []
                for msg in bot_response:
                    if "text" in msg:
                        messages.append(msg["text"])
                    if "image" in msg:
                        messages.append(f'<img src="{msg["image"]}" alt="product image" style="max-width: 200px;" />')
                full_response = "<br>".join(messages)
                return {"response": full_response}
            except ValueError as e:
                return {"error": f"Không thể parse JSON từ Rasa API: {str(e)}"}, 500
        else:
            return {"error": f"Lỗi kết nối tới Rasa API: {response.status_code} - {response.text}"}, 500
        
@ns.route('/recommend-products')
class RecommendProducts(Resource):
    jwt_required()
    def get(self):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        user_clusters, cluster_top_products = build_recommendation_data(token)
        user_id = request.args.get('userId')
        if not user_id or user_id not in user_clusters:
            return {"message": "User không có lịch sử mua hàng hoặc không tồn tại"}, 404
        cluster_id = int(user_clusters[user_id])
        recommended_product_ids = cluster_top_products.get(cluster_id, [])
        return {"recommendedProducts": recommended_product_ids}

@ns.route('/revenue')
class Revenue(Resource):
    @role_required("Admin")
    def get(self):
        mode = request.args.get("mode", "daily")
        start_date = request.args.get("startDate")
        end_date = request.args.get("endDate")
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        try:
            data = get_revenue_statistics(mode=mode, token=token, start_date=start_date, end_date=end_date)
        except ValueError as e:
            return {"error": str(e)}, 400
        return data

@ns.route('/best-sellers')
class BestSellers(Resource):
    @role_required("Admin")
    def get(self):
        mode = request.args.get("mode", "daily")
        start_date = request.args.get("startDate")
        end_date = request.args.get("endDate")
        top_n = int(request.args.get("top_n", 10))
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        try:
            data = get_best_selling_products(top_n=top_n, mode=mode, token=token, start_date=start_date, end_date=end_date)
        except ValueError as e:
            return {"error": str(e)}, 400
        return data

if __name__ == "__main__":
    app.run(debug=True)
