# resources/auth.py
from flask_restful import Resource, reqparse
from models import db, User
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity


class UserRegistration(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('username', type=str, required=True, help="Username is required")
        parser.add_argument('password', type=str, required=True, help="Password is required")
        args = parser.parse_args()

        if User.query.filter_by(username=args['username']).first():
            return {"status": "error", "message": "Username already exists."}, 400

        user = User(username=args['username'])
        user.set_password(args['password'])
        db.session.add(user)
        db.session.commit()
        return {"status": "success", "message": "User registered successfully."}, 201


class UserLogin(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('username', type=str, required=True, help="Username is required")
        parser.add_argument('password', type=str, required=True, help="Password is required")
        args = parser.parse_args()

        user = User.query.filter_by(username=args['username']).first()
        if user and user.check_password(args['password']):
            access_token = create_access_token(identity=user.username)
            return {"status": "success", "access_token": access_token}, 200
        return {"status": "error", "message": "Invalid credentials."}, 401


class ProtectedResource(Resource):
    @jwt_required()
    def get(self):
        current_user = get_jwt_identity()
        return {"status": "success", "message": f"Hello, {current_user}!"}, 200
