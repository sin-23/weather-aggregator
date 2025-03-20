# # services/external_api.py
# import requests, re
# from config import Config
# from datetime import date, timedelta, datetime
# import difflib
# from flask import Flask, request, jsonify
# from models import db, Subscription, UserPreference, UserLocation, Feedback, UserSearchHistory, CustomSubscription
# from bs4 import BeautifulSoup
# from flask_jwt_extended import get_jwt_identity, jwt_required
# from collections import Counter
# from sqlalchemy import desc
# import json
#
# # In-memory stores for persistence (for demonstration only)
# user_preferences = {}  # Maps user_id to preferences
# user_locations = {}  # Maps user_id to their location
# feedback_store = {}  # Maps user_id to list of feedback messages
# subscriptions = {}  # Maps (location, alert_type) or (location, condition) to subscription details
#
#
#
#
#
#
