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
    
class AskLogisticsComplaint(Action):
    """询问投诉内容"""

    def name(self) -> str:
        return "action_ask_logistics_complaint"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[str, Any]
    ) -> List[Dict[Text, Any]]:
        # 从槽中获取投诉的物流单号
        logistics_id = tracker.get_slot("logistics_id")
        # 获取物流信息
        with SessionLocal() as session:
            logistics = (
                session.query(Logistics).filter_by(logistics_id=logistics_id).first()
            )
        # 判断物流状态
        logistics_status = "已发货" if logistics.delivered_time is None else "已签收"
        # 获取该状态下可用的投诉信息
        with SessionLocal() as session:
            logistics_complaints = (
                session.query(LogisticsComplaint)
                .filter_by(logistics_status=logistics_status)
                .all()
            )
        buttons = [
            {
                "title": f"{i.logistics_complaint}",
                f"payload": f"/SetSlots(logistics_complaint={i.logistics_complaint})",
            }
            for i in logistics_complaints
        ]
        buttons.extend(
            [
                {"title": "其他", "payload": f"/SetSlots(logistics_complaint=other)"},
                {
                    "title": "取消投诉",
                    "payload": f"/SetSlots(logistics_complaint=false)",
                },
            ]
        )
        dispatcher.utter_message(text="请选择要反馈的问题", buttons=buttons)
        return []

class RecordLogisticsComplaint(Action):
    """记录投诉信息"""

    def name(self) -> str:
        return "action_record_logistics_complaint"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[str, Any]
    ) -> List[Dict[Text, Any]]:
        events = []
        # 从槽中获取投诉的物流ID和投诉内容
        logistics_id = tracker.get_slot("logistics_id")
        logistics_complaint = tracker.get_slot("logistics_complaint")
        # 如果投诉内容为其他，从最新消息中获取
        if logistics_complaint == "other":
            logistics_complaint = tracker.latest_message["text"]
            # 将投诉内容存入槽中
            events.append(SlotSet("logistics_complaint", logistics_complaint))
        dispatcher.utter_message(
            text=f"已收到您反馈的 {logistics_id} 的 {logistics_complaint} 问题，我们会尽快处理"
        )
        # 将投诉信息存入数据库
        with SessionLocal() as session:
            session.add(
                LogisticsComplaintsRecord(
                    logistics_id=logistics_id,
                    logistics_complaint=logistics_complaint,
                    complaint_time=datetime.now(),
                    user_id=tracker.get_slot("user_id"),
                )
            )
            session.commit()
        return events