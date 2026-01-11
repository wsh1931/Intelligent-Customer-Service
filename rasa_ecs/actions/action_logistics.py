from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from datetime import datetime
from .db import SessionLocal
from .db_table_class import (
    LogisticsCompany,
    OrderInfo,
    Logistics,
    LogisticsComplaint,
    LogisticsComplaintsRecord,
)
from sqlalchemy.orm import joinedload

class GetLogisticsCompanys(Action):
    """查询支持的快递公司"""

    def name(self) -> str:
        return "action_get_logistics_companys"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[str, Any]
    ) -> List[Dict[Text, Any]]:
        # 获取快递公司列表
        with SessionLocal() as session:
            logistics_companys = session.query(LogisticsCompany).all()
        # 拼接快递公司名称
        logistics_companys = "".join(
            [f"- {i.company_name}\n" for i in logistics_companys]
        )
        # 如果没有快递公司名称
        if logistics_companys == "":
            logistics_companys = "- 无"
        dispatcher.utter_message(f"支持的快递有:\n{logistics_companys}")

        # 发送消息不需要传，当设置slot时，必需在return中传
        return []

class GetLogisticsInfo(Action):
    """查询物流信息"""

    def name(self) -> str:
        return "action_get_logistics_info"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[str, Any]
    ) -> List[Dict[Text, Any]]:
        # 从槽中获取订单ID
        order_id = tracker.get_slot("order_id")
        # 查询订单
        with SessionLocal() as session:
            order_info = (
                session.query(OrderInfo)
                .options(joinedload(OrderInfo.logistics))
                .options(joinedload(OrderInfo.order_detail))
                .filter_by(order_id=order_id)
                .first()
            )
        # 获取订单物流信息
        logistics = order_info.logistics[0]
        message = [f"- **订单ID**：{order_id}"]
        message.extend(
            [
                f"  - {order_detail.sku_name} × {order_detail.sku_count}"
                for order_detail in order_info.order_detail
            ]
        )
        message.append(f"- **物流ID**：{logistics.logistics_id}")
        message.append("- **物流信息**：")
        message.append("  - " + "\n  - ".join(logistics.logistics_tracking.split("\n")))
        dispatcher.utter_message("\n".join(message))
        return [SlotSet("logistics_id", logistics.logistics_id)]