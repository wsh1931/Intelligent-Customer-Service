from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.events import UserUtteranceReverted
from rasa_sdk.executor import CollectingDispatcher


class ActionFallBack(Action):

    def name(self) -> Text:
        return "action_fallback"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        intent = tracker.latest_message.get("intent", {}).get("name", "None")
        if intent == "ask_weather":
              dispatcher.utter_message(text="请提供日期或地点吧")
        else:
          dispatcher.utter_message(text=f"你是想{intent}吗，我该做些什么？")
         # 撤销导致回退的用户消息# 撤销最近一次用户消息及其带来的所有对话影响
        return [UserUtteranceReverted()]

