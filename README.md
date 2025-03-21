# Weather Aggegator API
## Overview
The Weather Aggregator API will serve as a service that gathers weather-related information
from external providers and delivers insights to users. The API is designed to offer more than
basic weather data by providing features such as personalized recommendations, custom alerts,
comparative analysis, and feedback mechanisms through a series of endpoints.
Weather Aggregator API
1. /weather/current: Fetch the current weather for a specified location.
2. /weather/prediction-confidence: Returns a confidence score for a location's forecast.
3. /weather/preferences: View user preferences through subscriptions and most
frequently used location in current weather endpoint.
4. /weather/update-location: Update a user’s location for related weather
updates.
5. /weather/recommendation: Location and weather-based recommendations for clothing
or activities.
6. /weather/suggested-activities: Suggest activities based on the current weather
conditions.
7. /weather/alert/subscribe: Subscribe to premade weather alerts.
8. /weather/custom-alert: Set up available custom alerts for certain weather
conditions.
9. /weather/alert/cancel: Unsubscribe from weather alerts.
10. /weather/alerts: Severe weather alerts for a specific location.
11. /weather/real-time: Fetch real-time weather data for a specific location.
12. /weather/forecast/detailed: A 24 hour weather forecast for the given location for
the current date.
13. /weather/next-7-days: Fetch weather data for the next 7 days for a location.
14. /weather/forecast: A week of weather forecast for a given location.
15. /weather/historical: Retrieve past weather data for a specified date and location.
16. /weather/climate: Returns a climate summary for a location through average
maximum and minimum temperatures as well as average precipitation.
17. /weather/seasonal-changes: Provides seasonal insights by comparing the current
temperature against historical averages, highlighting the temperature change over time.
18. /weather/compare: Compare the weather between two or more locations.
19. /weather/trending: Weather conditions globally based on most page views.
20. /weather/feedback: Allow users to provide and view feedback for weather
predictions.
