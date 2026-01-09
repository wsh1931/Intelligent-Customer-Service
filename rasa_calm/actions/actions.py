from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

class ActionCheckSufficientFunds(Action):
    """检查余额是否充足"""

    def name(self) -> Text:
        return "action_check_sufficient_funds"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        events = []
        # 获取槽位中的余额和转账金额
        balance = tracker.get_slot("balance")
        transfer_amount = tracker.get_slot("amount")
        # 检查余额是否充足
        has_sufficient_funds = transfer_amount <= balance
        # 填充余额是否充足槽位
        events.append(SlotSet("has_sufficient_funds", has_sufficient_funds))
        return events

class ActionTransfer(Action):
    """转账"""
    def name(self) -> Text:
        return "action_transfer"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        # 获取槽位中的余额和转账金额
        balance = tracker.get_slot("balance")
        transfer_amount = tracker.get_slot("amount")
        # 扣除转账金额，并填充到余额槽位
        return [SlotSet("balance", balance - transfer_amount)]