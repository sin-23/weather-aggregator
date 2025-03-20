from models import db, UserSearchHistory, UserPreference, Subscription, CustomSubscription, UserLocation, Feedback
from datetime import datetime
from sqlalchemy import desc
from alert_functions import ALERT_TYPES, ALERT_TYPE_PRECIP, ALERT_TYPE_WIND, ALERT_TYPE_TEMP

def log_user_search(user_id, location):
    """
    Logs a user's search for a given location. If a record for that user and location exists,
    increments the search_count and updates the last_searched timestamp. Otherwise, creates a new record.
    Then updates the user's preferences with the top searched locations.
    """
    record = UserSearchHistory.query.filter_by(user_id=user_id, location=location).first()
    if record:
        record.search_count += 1
        record.last_searched = datetime.utcnow()
    else:
        record = UserSearchHistory(user_id=user_id, location=location, search_count=1)
        db.session.add(record)
    db.session.commit()

    # Update preferences based on the entire search history for this user.
    update_user_preferences_from_history(user_id)

def update_user_preferences_from_history(user_id):
    """
    Retrieves the user's search history from UserSearchHistory, orders the records by search_count descending,
    takes the top 5 locations, and updates (or creates) the UserPreference record accordingly.
    """
    # Query the top 5 search history entries for the user, ordered by frequency.
    search_history = UserSearchHistory.query.filter_by(user_id=user_id) \
        .order_by(desc(UserSearchHistory.search_count)) \
        .limit(5).all()
    # Build a list of locations in descending order of frequency.
    top_locations = [record.location for record in search_history]

    # Update the UserPreference record.
    user_pref = UserPreference.query.filter_by(user_id=user_id).first()
    if user_pref:
        user_pref.top_searches = top_locations
    else:
        user_pref = UserPreference(user_id=user_id, top_searches=top_locations)
        db.session.add(user_pref)
    db.session.commit()

def save_user_preferences(user_id, preferences):
    """
    Saves user preferences in the MySQL database.
    If preferences already exist for the user, they are updated.
    """
    user_pref = UserPreference.query.filter_by(user_id=user_id).first()
    if user_pref:
        user_pref.set_preferences(preferences)
    else:
        user_pref = UserPreference(user_id=user_id)
        user_pref.set_preferences(preferences)
        db.session.add(user_pref)
    db.session.commit()
    return f"Preferences for user {user_id} saved."

def get_user_preferences(user_id):
    """
    Retrieves the user's top searched locations and active subscriptions.
    Active subscriptions include normal subscriptions and custom alerts.
    For custom alerts, a human-readable description is generated.
    """
    # Retrieve top searched locations.
    search_history = UserSearchHistory.query.filter_by(user_id=user_id)\
                      .order_by(desc(UserSearchHistory.search_count)).limit(5).all()
    top_locations = [record.location for record in search_history]

    subscriptions = []

    # Normal subscriptions from Subscription table.
    normal_subs = Subscription.query.filter_by(user_id=user_id).all()
    for sub in normal_subs:
        try:
            alert_num = int(sub.alert_type)
            description = ALERT_TYPES.get(alert_num, "Unknown alert")
        except Exception:
            description = "Unknown alert"
        subscriptions.append({
            "location": sub.location,
            "alert_type": sub.alert_type,
            "description": description
        })

    # Custom subscriptions from CustomSubscription table.
    custom_subs = CustomSubscription.query.filter_by(user_id=user_id).all()
    for sub in custom_subs:
        if sub.alert_type == ALERT_TYPE_TEMP:
            description = f"Temperature {sub.operator} {sub.threshold}°C"
        elif sub.alert_type == ALERT_TYPE_WIND:
            description = f"Wind speed {sub.operator} {sub.threshold} km/h"
        elif sub.alert_type == ALERT_TYPE_PRECIP:
            description = f"Precipitation alert: {sub.threshold}"
        else:
            description = "Unknown custom alert"
        subscriptions.append({
            "location": sub.location,
            "alert_type": f"{sub.alert_type} (custom)",
            "description": description
        })

    return {
        "user_id": user_id,
        "top_searches": top_locations,
        "subscriptions": subscriptions
    }

def get_default_location(user_id, provided_location=None):
    """
    Returns the provided_location if available.
    Otherwise, retrieves the user's preferences and returns the top searched location.
    If no preferences exist, returns None.
    """
    if provided_location:
        return provided_location
    prefs = get_user_preferences(user_id)
    top_searches = prefs.get("top_searches", [])
    if top_searches:
        return top_searches[0]
    return None

def update_user_location(user_id, location):
    """
    Updates a user's location in the MySQL database.
    """
    user_loc = UserLocation.query.filter_by(user_id=user_id).first()
    if user_loc:
        user_loc.location = location
    else:
        user_loc = UserLocation(user_id=user_id, location=location)
        db.session.add(user_loc)
    db.session.commit()
    return f"User {user_id}'s location updated to {location}."

def submit_feedback(user_id, rating, comment=""):
   """
   Stores user feedback (a rating between 1 and 5 and an optional comment) in the database.
   Returns a tuple: (success: bool, message: str)
   """
   try:
       rating = int(rating)
   except ValueError:
       return False, "Rating must be an integer."


   if rating < 1 or rating > 5:
       return False, "Rating must be between 1 and 5."


   fb = Feedback(user_id=user_id, rating=rating, comment=comment)
   db.session.add(fb)
   try:
       db.session.commit()
       return True, f"Feedback from user {user_id} recorded."
   except Exception as e:
       db.session.rollback()
       return False, f"An error occurred: {str(e)}"