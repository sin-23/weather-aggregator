# auth.py
from flask_restful import Resource, reqparse
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

class UserLogin(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('username', type=str, required=True, help="Username is required")
        parser.add_argument('password', type=str, required=True, help="Password is required")
        args = parser.parse_args()
        # Dummy authentication; replace with actual authentication logic
        if args['username'] == 'admin' and args['password'] == 'password':
            access_token = create_access_token(identity=args['username'])
            return {"status": "success", "access_token": access_token}, 200
        return {"status": "error", "message": "Invalid credentials"}, 401

class ProtectedResource(Resource):
    @jwt_required()
    def get(self):
        current_user = get_jwt_identity()
        return {"status": "success", "message": f"Hello, {current_user}!"}, 200
