# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Subscription(db.Model):
    __tablename__ = "subscriptions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    alert_type = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'location', 'alert_type', name='unique_subscription'),)


class UserPreference(db.Model):
    __tablename__ = "user_preferences"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), unique=True, nullable=False)
    # Store only top searched locations as JSON (a list of strings)
    top_searches = db.Column(db.JSON, nullable=True)

    def set_preferences(self, top_searches):
        """Stores a list of top searched locations."""
        self.top_searches = top_searches  # expects a list of strings

    def get_preferences(self):
        """Returns a dictionary with only the top searched locations."""
        return {"top_searches": self.top_searches or []}

    def __repr__(self):
        return f"<UserPreference {self.user_id} top_searches:{self.top_searches}>"

class UserSearchHistory(db.Model):
    __tablename__ = "user_search_history"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    search_count = db.Column(db.Integer, default=1)
    last_searched = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'location', name='unique_user_location'),)

    def __repr__(self):
        return f"<UserSearchHistory user:{self.user_id} location:{self.location} count:{self.search_count}>"

class UserLocation(db.Model):
    __tablename__ = "user_locations"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), unique=True, nullable=False)
    location = db.Column(db.String(255), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Feedback(db.Model):
    __tablename__ = "feedback"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)
    feedback = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CustomSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    alert_type = db.Column(db.Integer, nullable=False)
    operator = db.Column(db.String(2), nullable=True)  # For temperature and wind alerts
    threshold = db.Column(db.String(20), nullable=True)  # Numeric threshold or precipitation level
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
