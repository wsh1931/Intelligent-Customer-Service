from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import requests


def get_weather(location, date):
    index_of_date = 0
    match date:
        case "今天":
            index_of_date = 0
        case "明天":
            index_of_date = 1
        case "后天":
            index_of_date = 2
        case _:
            return "服务故障，最多支持查询三天内的天气"

    url = "https://api.seniverse.com/v3/weather/daily.json"
    result = requests.get(
            url,
            params = {
                'key': 'SE_vE1h0hgPTmQeOO',
                'location': location
            })
    result = result.json()["results"][0]["daily"]
    return f"""{location} {date}的天气：
    白天：{result[index_of_date]["text_day"]}
    夜晚：{result[index_of_date]["text_night"]}
    最高温度：{result[index_of_date]["high"]}℃
    最低温度：{result[index_of_date]["low"]}℃
    降水概率：{result[index_of_date]["precip"]}
    风向：{result[index_of_date]["wind_direction"]}
    风力：{result[index_of_date]["wind_scale"]}级
    湿度：{result[index_of_date]["humidity"]}%
    """


class ActionQueryWeather(Action):

    def name(self) -> Text:
        return "action_weather_form_submit"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        location = tracker.get_slot("location")
        date = tracker.get_slot("date")


        result = get_weather(location, date)
        dispatcher.utter_message(text = result)

        return []
