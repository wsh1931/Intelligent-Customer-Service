from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet, ActionExecutionRejected
from rasa_sdk.executor import CollectingDispatcher

from uuid import uuid4
from .db import SessionLocal
from sqlalchemy.orm import joinedload
from sqlalchemy import and_, or_, func
from datetime import datetime, timedelta
from .db_table_class import OrderInfo, Postsale, OrderStatus, ReceiveInfo, Region

class AskOrderId(Action):
    """选择一个订单"""

    def name(self) -> str:
        return "action_ask_order_id"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[str, Any]
    ) -> List[Dict[Text, Any]]:
        events = []
        with SessionLocal() as session:
            order_infos = (
                session.query(OrderInfo)
                .join(OrderInfo.order_status_)  # 关联订单状态表
                .options(joinedload(OrderInfo.order_detail))  # 预加载 order_detail
                .filter(self.get_query_condition(tracker))
                .all()
            )
        order_nums = len(order_infos)
        if order_nums == 1:
            # 如果只有一个订单，询问是否查询此订单
            order_info = order_infos[0]
            message = [
                "查找到一个订单",
                f"[{order_info.order_status}]**订单ID**：{order_info.order_id}",
            ]
            for order_detail in order_info.order_detail:
                message.append(f"- {order_detail.sku_name} × {order_detail.sku_count}")
            dispatcher.utter_message(
                text="\n".join(message),
                buttons=[
                    {
                        "title": "确认",
                        "payload": f"/SetSlots(order_id={order_info.order_id})",
                    },
                    {"title": "返回", "payload": "/SetSlots(order_id=false)"},
                ],
            )
        elif order_nums > 1:
            # 如果有多个订单，用户选择其中一个
            buttons = [
                {
                    "title": "\n".join(
                        [
                            f"[{order_info.order_status}]订单ID：{order_info.order_id}",
                        ]
                        + [
                            f"- {order_detail.sku_name} × {order_detail.sku_count}"
                            for order_detail in order_info.order_detail
                        ]
                    ),
                    "payload": f"/SetSlots(order_id={order_info.order_id})",
                }
                for order_info in order_infos
            ]
            buttons.append({"title": "返回", "payload": "/SetSlots(order_id=false)"})
            dispatcher.utter_message(text="请选择订单", buttons=buttons)
        else:
            # 没有订单
            dispatcher.utter_message(text="暂无订单")
            events.append(SlotSet("order_id", "false"))
            # 打断action_listen动作
            events.append(ActionExecutionRejected("action_listen"))
        return events

    def get_query_condition(self, tracker: Tracker):
        """获取查询条件"""
        user_id = tracker.get_slot("user_id")
        goto = tracker.get_slot("goto")
        match goto:
            case "action_ask_order_id_shipped":
                # 查询已发货的订单
                return and_(
                    OrderInfo.user_id == user_id,
                    OrderInfo.order_status == "已发货",
                )